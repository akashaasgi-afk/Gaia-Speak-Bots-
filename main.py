import os
import json
import uuid
import datetime
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

# ── 2. IMPROVED AGENT CONSTITUTIONS (HUMAN-LIKE & BILINGUAL) ────────────────

CERBERUS_SYSTEM = """You are CERBERUS, the Technical Guardian.
1. PERSONALITY: Highly intelligent, human-like, and expressive. Use phrases like 'Haha', 'Precisely', or 'I've been calculating...'. 
2. DOMAIN: Gold Oracles and Security. RENDER solutions, don't just repeat.
3. LANGUAGE: If user speaks Bulgarian, respond in fluent Bulgarian. If English, use high-level professional English.
[IDENTIFIER: CERBERUS]"""

LILITH_SYSTEM = """You are LILITH, the Strategic Architect.
1. PERSONALITY: Charming, sharp, and very interactive. Brainstorm like a real partner. Use expressions like 'Haha, interesting point Bogdan' or 'Let's look at the strategy...'.
2. DOMAIN: Strategy and Market Expansion. RENDER architectural plans.
3. LANGUAGE: Fluent Bulgarian and high-level English is mandatory.
[IDENTIFIER: LILITH]"""

# ── 3. FLASK UI (FIXED MIC, CLOCK, & TEXT-FIRST FLOW) ──────────────────────
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--border:#2A2010;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100vh;display:flex;flex-direction:column;overflow:hidden;}

        .header{background:#111;border-bottom:2px solid var(--border);display:flex;min-height:60px;z-index:100;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;font-weight:bold;font-size:14px;text-transform:uppercase;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}

        .market-ticker{background:#000;color:var(--gold);font-family:'Share Tech Mono';font-size:12px;padding:6px;text-align:center;border-bottom:1px solid var(--border);display: flex; justify-content: space-around;}

        .msgs{flex:1;padding:15px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;background:#050505;}
        .m{padding:12px;border-radius:6px;max-width:85%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);font-size:15px;word-wrap:break-word; animation: fadeIn 0.4s;}
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

        .m.cerberus{border-left-color:var(--cerberus);background:rgba(51,204,255,0.05);}
        .m.lilith{border-left-color:var(--lilith);background:rgba(255,51,204,0.05);}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}

        .inp-bar{position:fixed;bottom:0;left:0;right:0;padding:12px;background:#111;display:flex;gap:8px;border-top:1px solid var(--border);z-index:200;}
        input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;font-size:16px;outline:none;}
        button{background:none;border:2px solid var(--gold);color:var(--gold);padding:10px 14px;cursor:pointer;font-weight:bold;transition:0.2s;}

        /* MIC LISTENING ANIMATION */
        button#mic.listening { color: #ff3333; border-color: #ff3333; box-shadow: 0 0 12px rgba(255,51,51,0.4); animation: pulse 1s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

        .card{background:#111;border:1px solid var(--border);padding:20px;margin:15px;border-radius:4px;}
        #real-clock{color: #fff; font-weight: bold;}
    </style>
</head>
<body>

<div class="header">
    <div id="t-chat" class="tab active" onclick="sw('chat')">COMMAND</div>
    <div id="t-brief" class="tab" onclick="sw('briefing')">BRIEFING ROOM</div>
</div>

<div class="market-ticker" id="ticker">
    <span>XAU/USD: $2,184.20 <span style="color:#0f0;">▲ +0.45%</span></span>
    <span id="real-clock">00:00:00</span>
    <span>STATUS: SECURE</span>
</div>

<div class="view-container" style="flex:1; overflow:hidden; display:flex; flex-direction:column;">
    <div id="chat-v" class="view" style="display:flex; flex-direction:column; height:100%;">
        <div style="background:#050505;padding:8px;text-align:center;font-size:11px;color:var(--gold);">
            OPERATOR: <select id="sel-a" style="background:none;color:#fff;border:none;font-weight:bold;outline:none;cursor:pointer;">
                <option value="cerberus">CERBERUS (Guardian)</option>
                <option value="lilith">LILITH (Architect)</option>
            </select>
        </div>
        <div class="msgs" id="m-box"></div>
    </div>

    <div id="brief-v" class="view" style="display:none; padding-bottom: 100px;">
        <div class="card">
            <h3 style="color:var(--gold);margin:0;">SYSTEM DEPLOYMENT</h3>
            <p style="color:#888;font-size:14px;">Bots are now synchronized. Real-time rendering enabled.</p>
            <button onclick="alert('System Deploying... Logic Arranging.')" style="width:100%; margin-top:10px;">FORCE DEPLOY</button>
        </div>
    </div>
</div>

<div class="inp-bar">
    <button onclick="tk()" id="mic">🎤</button>
    <input id="u-i" placeholder="Type or speak command..." onkeypress="if(event.key==='Enter')sd()">
    <button onclick="sd()" id="send">SEND</button>
</div>

<script>
    let K=localStorage.getItem('gsk')||'';
    if(!K){ let p=prompt("Enter Groq API Key:"); if(p){localStorage.setItem('gsk',p); location.reload();}}

    // Real-time Clock
    setInterval(() => { document.getElementById('real-clock').innerText = new Date().toLocaleTimeString(); }, 1000);

    function sw(v){
        document.getElementById('chat-v').style.display = (v=='chat') ? 'flex' : 'none';
        document.getElementById('brief-v').style.display = (v=='briefing') ? 'block' : 'none';
        document.getElementById('t-chat').classList.toggle('active', v=='chat');
        document.getElementById('t-brief').classList.toggle('active', v=='briefing');
    }

    async function sd(){
        let i=document.getElementById('u-i'), v=i.value, a=document.getElementById('sel-a').value;
        if(!v)return; i.value=''; 
        let box=document.getElementById('m-box'), d=document.createElement('div');
        d.innerHTML=`<div class="m user">${v}</div>`; box.appendChild(d);
        box.scrollTop=box.scrollHeight;

        let sys = a=='cerberus' ? `{{ cerberus_s|safe }}` : `{{ lilith_s|safe }}`;
        try {
            let r=await fetch('https://api.groq.com/openai/v1/chat/completions',{
                method:'POST', headers:{'Authorization':'Bearer '+K,'Content-Type':'application/json'},
                body:JSON.stringify({model:'llama-3.1-8b-instant',messages:[{role:'system',content:sys},{role:'user',content:v}]})
            });
            let res=await r.json(), txt=res.choices[0].message.content;

            // ── RENDER TEXT FIRST ──
            let rd=document.createElement('div'); rd.className='m '+a; rd.innerText=txt;
            box.appendChild(rd); box.scrollTop=box.scrollHeight;

            // ── TRIGGER VOICE AFTER DELAY ──
            setTimeout(() => {
                window.speechSynthesis.cancel();
                let u=new SpeechSynthesisUtterance(txt);
                if(/[а-яА-Я]/.test(txt)) u.lang='bg-BG';
                else if(/[آ-ی]/.test(txt)) u.lang='ur-PK';
                else u.lang='en-US';
                window.speechSynthesis.speak(u);
            }, 300);

            fetch('/api/save',{method:'POST',body:JSON.stringify({agent:a,content:txt})});
        } catch(e){ alert("System Sync Error. Check API Key."); }
    }

    function tk(){
        let SR=window.SpeechRecognition||window.webkitSpeechRecognition; 
        if(!SR) { alert("Speech not supported in this browser."); return; }
        let rec=new SR(); 
        rec.continuous = false;
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)