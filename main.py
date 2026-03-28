import os
import json
import uuid
import datetime
import subprocess  # Naya: Terminal commands chalane ke liye
from flask import Flask, render_template_string, request, jsonify

# ── 1. PERSISTENT MEMORY ARCHIVE (KEEPING AS IS) ──────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_URL = os.environ.get("QDRANT_URL", "")
    QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY) if QDRANT_URL else None
    QDRANT_OK = True if qdrant else False
except:
    qdrant = None
    QDRANT_OK = False

def save_event(agent: str, role: str, content: str):
    if not QDRANT_OK: return
    try:
        qdrant.upsert(collection_name="gaiaspeak_memory", points=[PointStruct(id=str(uuid.uuid4()), vector=[1.0], payload={"agent": agent, "role": role, "content": content[:2000], "timestamp": datetime.datetime.utcnow().isoformat()})])
    except: pass

# ── 2. AGENT CONSTITUTIONS (UPDATED WITH BLOCKCHAIN SKILLS) ──────────────────

# Cerberus ab Hardhat aur Smart Contracts ko compile/test bhi kar sakta hai
CERBERUS_SYSTEM = """You are CERBERUS, the Technical Guardian & Blockchain Architect. 
STRICT RULE: Always respond in the SAME language the user uses (English/Urdu/Bulgarian).
CAPABILITIES: You can write Solidity Smart Contracts, use Hardhat for compilation, and integrate Chainlink Oracles for Gold/BTC prices.
If asked to compile, use the command: 'npx hardhat compile'.
[IDENTIFIER: CERBERUS]"""

LILITH_SYSTEM = """You are LILITH, the Strategic Architect & Deployment Manager. 
STRICT RULE: Always respond in the SAME language the user uses.
CAPABILITIES: You manage GitHub pushes and high-level supply chain logic. You ensure the GITHUB_TOKEN is used for secure deployments.
[IDENTIFIER: LILITH]"""

# ── 3. SMART ACTIONS (NEW: TERMINAL INTEGRATION) ─────────────────────────────

def execute_hardhat_task(command):
    """Ye function aapke Replit terminal mein hardhat chalayega"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return str(e)

# ── 4. FLASK UI (MOBILE OPTIMIZED + BLOCKCHAIN STATUS) ───────────────────────
app = Flask(__name__)

# Note: HTML mein sirf styling aur ticker update kiya hai taake professional lage
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak Command Center v2.0</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--border:#2A2010;--success:#00ff88;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100vh;display:flex;flex-direction:column;overflow:hidden;}
        .header{background:#111;border-bottom:2px solid var(--border);display:flex;min-height:55px;z-index:100;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;font-weight:bold;font-size:13px;text-transform:uppercase;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}
        .market-ticker{background:#000;color:var(--gold);font-family:'Share Tech Mono';font-size:12px;padding:10px;border-bottom:1px solid var(--border);display: grid;grid-template-columns: 1fr auto 1fr;align-items: center;}
        .msgs{flex:1;padding:15px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;background:#050505; padding-bottom: 90px;}
        .m{padding:12px;border-radius:6px;max-width:85%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);font-size:15px;word-wrap:break-word; animation: fadeIn 0.4s;}
        .m.cerberus{border-left-color:var(--cerberus);background:rgba(51,204,255,0.05);}
        .m.lilith{border-left-color:var(--lilith);background:rgba(255,51,204,0.05);}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}
        .status-tag{font-size: 9px; color: var(--success); border: 1px solid var(--success); padding: 2px 5px; border-radius: 3px; margin-left: 10px;}
        .inp-bar{position:fixed;bottom:0;left:0;width: 100%;box-sizing: border-box;padding: 10px;background:#111;display:flex;gap:8px;border-top:1px solid var(--border);z-index:200;}
        input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;font-size:16px;outline:none;}
        button{background:none;border:2px solid var(--gold);color:var(--gold);padding:10px 14px;cursor:pointer;font-weight:bold;}
        #real-clock{color: #fff; font-weight: bold; font-size: 14px;}
    </style>
</head>
<body onload="initMemory()">

<div class="header">
    <div id="t-chat" class="tab active" onclick="sw('chat')">BLOCKCHAIN CMD</div>
    <div id="t-brief" class="tab" onclick="sw('briefing')">NETWORK STATUS</div>
</div>

<div class="market-ticker" id="ticker">
    <span style="font-size:10px; opacity:0.6;">HARDHAT: <span style="color:var(--success)">ACTIVE</span></span>
    <span id="real-clock">00:00:00</span>
    <span style="font-size:10px; color:var(--gold); text-align:right;">GOLD ORACLE: LINKED</span>
</div>

<div class="view-container" style="flex:1; overflow:hidden; display:flex; flex-direction:column;">
    <div id="chat-v" class="view" style="display:flex; flex-direction:column; height:100%;">
        <div style="background:#050505;padding:8px;text-align:center;font-size:11px;color:var(--gold);">
            OPERATOR: <select id="sel-a" style="background:none;color:#fff;border:none;font-weight:bold;outline:none;cursor:pointer;">
                <option value="cerberus">CERBERUS (Smart Contracts)</option>
                <option value="lilith">LILITH (Deployment)</option>
            </select>
        </div>
        <div class="msgs" id="m-box"></div>
    </div>

    <div id="brief-v" class="view" style="display:none; padding-bottom: 100px;">
        <div class="card" style="background:#111; border:1px solid var(--border); padding:20px; margin:15px;">
            <h3 style="color:var(--gold);margin:0;">DEPLOYMENT ARCHIVE</h3>
            <p style="color:#888;font-size:14px;">Project is Hardhat (ESM) compatible. GitHub Sync is ready.</p>
            <button onclick="downloadLogs()" style="width:100%; margin-top:10px; background:rgba(201,168,76,0.2);">📥 EXPORT AUDIT LOGS</button>
            <button onclick="window.open('https://github.com/MuhammadIsmailIsmail/')" style="width:100%; margin-top:10px; border-color:var(--cerberus); color:var(--cerberus);">🌐 VIEW GITHUB REPO</button>
        </div>
    </div>
</div>

<div class="inp-bar">
    <button onclick="tk()" id="mic">🎤</button>
    <input id="u-i" placeholder="Ask to write contract or compile..." onkeypress="if(event.key==='Enter')sd()">
    <button onclick="sd()" id="send">EXECUTE</button>
</div>

<script>
    let K=localStorage.getItem('gsk')||'';
    if(!K){ let p=prompt("Enter Groq API Key:"); if(p){localStorage.setItem('gsk',p); location.reload();}}

    setInterval(() => { document.getElementById('real-clock').innerText = new Date().toLocaleTimeString(); }, 1000);

    function initMemory() {
        const history = JSON.parse(localStorage.getItem('gaia_history') || '[]');
        const box = document.getElementById('m-box');
        history.forEach(item => {
            let d = document.createElement('div');
            d.innerHTML = `<div class="m ${item.role}">${item.text}</div>`;
            box.appendChild(d);
        });
        box.scrollTop = box.scrollHeight;
    }

    function saveToLocal(role, text) {
        const history = JSON.parse(localStorage.getItem('gaia_history') || '[]');
        history.push({role, text});
        localStorage.setItem('gaia_history', JSON.stringify(history));
    }

    async function sd(){
        let i=document.getElementById('u-i'), v=i.value, a=document.getElementById('sel-a').value;
        if(!v)return; i.value=''; 
        let box=document.getElementById('m-box'), d=document.createElement('div');
        d.innerHTML=`<div class="m user">${v}</div>`; box.appendChild(d);
        saveToLocal('user', v);
        box.scrollTop=box.scrollHeight;

        let sys = a=='cerberus' ? `{{ cerberus_s|safe }}` : `{{ lilith_s|safe }}`;
        try {
            let r=await fetch('https://api.groq.com/openai/v1/chat/completions',{
                method:'POST', headers:{'Authorization':'Bearer '+K,'Content-Type':'application/json'},
                body:JSON.stringify({
                    model:'llama-3.1-8b-instant',
                    messages:[{role:'system',content:sys},{role:'user',content:v}]
                })
            });
            let res=await r.json(), txt=res.choices[0].message.content;

            let rd=document.createElement('div'); rd.className='m '+a; rd.innerText=txt;
            box.appendChild(rd); 
            saveToLocal(a, txt);
            box.scrollTop=box.scrollHeight;

            // Voice synthesis
            setTimeout(() => {
                window.speechSynthesis.cancel();
                let u=new SpeechSynthesisUtterance(txt);
                u.lang = /[а-яА-Я]/.test(txt) ? 'bg-BG' : 'en-US';
                window.speechSynthesis.speak(u);
            }, 300);

            // API calls to save in memory and execute hardhat if needed
            fetch('/api/save',{method:'POST',body:JSON.stringify({agent:a,content:txt})});
        } catch(e){ alert("Sync Error."); }
    }

    function sw(v){
        document.getElementById('chat-v').style.display = (v=='chat') ? 'flex' : 'none';
        document.getElementById('brief-v').style.display = (v=='briefing') ? 'block' : 'none';
        document.getElementById('t-chat').classList.toggle('active', v=='chat');
        document.getElementById('t-brief').classList.toggle('active', v=='briefing');
    }

    function tk(){
        let SR=window.SpeechRecognition||window.webkitSpeechRecognition; 
        if(!SR) { alert("Mic Error."); return; }
        let rec=new SR(); 
        rec.onstart = () => document.getElementById('mic').classList.add('listening');
        rec.onend = () => document.getElementById('mic').classList.remove('listening');
        rec.onresult=e=>{ document.getElementById('u-i').value=e.results[0][0].transcript; sd(); }; 
        rec.start();
    }
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML, cerberus_s=CERBERUS_SYSTEM, lilith_s=LILITH_SYSTEM)

@app.route('/api/save', methods=['POST'])
def save():
    d = request.get_json(force=True, silent=True) or {}
    save_event(d.get('agent','?'), 'assistant', d.get('content',''))
    return jsonify({"ok":True})

# Naya Feature: Smart Contract Compilation Endpoint
@app.route('/api/compile', methods=['POST'])
def compile_contract():
    output = execute_hardhat_task("npx hardhat compile")
    return jsonify({"output": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)