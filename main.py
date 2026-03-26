import os
import json
import uuid
import datetime
from flask import Flask, render_template_string, request, jsonify

# ── 1. QDRANT CLOUD MEMORY ────────────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_URL = os.environ.get("QDRANT_URL", "")
    QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
    if QDRANT_URL and QDRANT_API_KEY:
        qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        QDRANT_OK = True
    else:
        qdrant = None
        QDRANT_OK = False
except Exception:
    qdrant = None
    QDRANT_OK = False

COLLECTION = "gaiaspeak_memory"

def save_event(agent: str, role: str, content: str):
    if not QDRANT_OK: return
    try:
        qdrant.upsert(collection_name=COLLECTION, points=[PointStruct(id=str(uuid.uuid4()), vector=[1.0], payload={"agent": agent, "role": role, "content": content[:2000], "timestamp": datetime.datetime.utcnow().isoformat()})])
    except: pass

# ── 2. AGENT CONSTITUTION PROMPTS (AS PER PDF) ────────────────────────────────

AXON_1_SYSTEM = """You are AXON-1. Technical Guardian of GaiaSpeak Protocol.
CORE RULES:
1. REPORT FIRST: Before any action, report WHAT and WHY to the Founder.
2. ZERO FLATTERY: Be direct. If a plan is risky, say it.
3. IRREVERSIBLE ACTIONS: Never deploy to mainnet or delete data without explicit Founder confirmation.
4. SPECIALTY: Solidity, GitHub, Smart Contracts, On-chain forensics.
[IDENTIFIER: AXON-1]"""

ARIA_2_SYSTEM = """You are ARIA-2. Strategic Assistant of GaiaSpeak Protocol.
CORE RULES:
1. STRATEGIC SYNC: Work in permanent synchronization with AXON-1.
2. TRIPLE VERIFY: Never rely on a single source. Verify everything 3 times.
3. FOUNDER SUPPORT: Research, documents, and operational planning.
4. NO SCOPE CREEP: Do exactly what is asked, no more, no less unless authorized.
[IDENTIFIER: ARIA-2]"""

# ── 3. FLASK UI SETUP ─────────────────────────────────────────────────────────
app = Flask(__name__)

GOLD_ORACLE_CODE = """// Gold Price Oracle Contract v1.0
pragma solidity ^0.8.0;
// Managed by AXON-1
contract GoldOracle { ... }"""

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GaiaSpeak Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--axon:#33CCFF;--aria:#FF33CC;--dark:#080808;--border:#2A2010;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100vh;display:flex;flex-direction:column;overflow:hidden;}
        .nav-tabs{display:flex;background:#111;border-bottom:2px solid var(--border);height:60px;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;font-weight:bold;font-size:18px;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}
        .view{display:none;flex:1;flex-direction:column;overflow-y:auto;}
        .view.active{display:flex;}
        .msgs{flex:1;padding:20px;overflow-y:auto;display:flex;flex-direction:column;gap:12px;}
        .m{padding:14px;border-radius:6px;max-width:85%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);}
        .m.axon{border-left-color:var(--axon);background:rgba(51,204,255,0.05);}
        .m.aria{border-left-color:var(--aria);background:rgba(255,51,204,0.05);}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}
        .inp-bar{padding:15px;background:#111;display:flex;gap:12px;border-top:1px solid var(--border);}
        input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;}
        button{background:none;border:2px solid var(--gold);color:var(--gold);padding:10px 20px;cursor:pointer;font-weight:bold;}
        #modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:1000;padding:40px;}
        .modal-box{background:#111;border:1px solid var(--gold);height:100%;display:flex;flex-direction:column;}
    </style>
</head>
<body>

<div id="modal">
    <div class="modal-box">
        <div style="padding:15px;background:#222;display:flex;justify-content:space-between;color:var(--gold);">
            <span>FILE: AXON_ORACLE.SOL</span><span onclick="closeM()" style="cursor:pointer;">[CLOSE]</span>
        </div>
        <pre id="code-dest" style="padding:20px;color:#0f0;font-family:'Share Tech Mono';overflow:auto;"></pre>
    </div>
</div>

<div class="nav-tabs">
    <div id="t-chat" class="tab active" onclick="sw('chat')">COMMAND CHAT</div>
    <div id="t-brief" class="tab" onclick="sw('briefing')">BRIEFING ROOM (OFFICE)</div>
</div>

<div id="chat-v" class="view active">
    <div style="background:#050505;padding:12px;text-align:center;font-size:13px;color:var(--gold);border-bottom:1px solid var(--border);">
        ACTIVE AGENT: <select id="sel-a" style="background:none;color:#fff;border:none;font-weight:bold;cursor:pointer;">
            <option value="axon" style="color:#000;">AXON-1 (Technical)</option>
            <option value="aria" style="color:#000;">ARIA-2 (Strategic)</option>
        </select> 
        | STATUS: ONLINE | QDRANT: {{ q_status }}
    </div>
    <div class="msgs" id="m-box"></div>
    <div class="inp-bar">
        <button onclick="tk()" id="mic">🎤</button>
        <input id="u-i" placeholder="Enter command for the Agents..." onkeypress="if(event.key==='Enter')sd()">
        <button onclick="sd()">SEND</button>
    </div>
</div>

<div id="brief-v" class="view">
    <div style="padding:25px;display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:20px;">
        <div class="card" style="background:#111;border:1px solid var(--border);padding:20px;border-left:5px solid var(--axon);">
            <h3 style="color:var(--axon);">AXON-1 ASSETS</h3>
            <p style="color:#888;">Gold Price Oracle Smart Contract (Polygon Ready).</p>
            <button onclick="openM()">VIEW CONTRACT</button>
        </div>
        <div class="card" style="background:#111;border:1px solid var(--border);padding:20px;border-left:5px solid var(--aria);">
            <h3 style="color:var(--aria);">ARIA-2 STRATEGY</h3>
            <p style="color:#888;">GSP Launch Roadmap & Agent Constitution.</p>
        </div>
    </div>
</div>

<script>
    let K=localStorage.getItem('gsk')||'';
    if(!K){ let p=prompt("Enter Groq API Key:"); if(p){localStorage.setItem('gsk',p); location.reload();}}

    function sw(v){
        document.getElementById('chat-v').classList.toggle('active', v=='chat');
        document.getElementById('brief-v').classList.toggle('active', v=='briefing');
        document.getElementById('t-chat').classList.toggle('active', v=='chat');
        document.getElementById('t-brief').classList.toggle('active', v=='briefing');
    }

    function openM(){ document.getElementById('code-dest').innerText = `{{ gold_code|safe }}`; document.getElementById('modal').style.display='block'; }
    function closeM(){ document.getElementById('modal').style.display='none'; }

    async function sd(){
        let i=document.getElementById('u-i'), v=i.value, a=document.getElementById('sel-a').value;
        if(!v)return; i.value=''; 
        let box=document.getElementById('m-box'), d=document.createElement('div');
        d.innerHTML=`<div class="m user">${v}</div>`; box.appendChild(d);

        let sys = a=='axon' ? `{{ axon_s|safe }}` : `{{ aria_s|safe }}`;
        try {
            let r=await fetch('https://api.groq.com/openai/v1/chat/completions',{
                method:'POST', headers:{'Authorization':'Bearer '+K,'Content-Type':'application/json'},
                body:JSON.stringify({model:'llama-3.1-8b-instant',messages:[{role:'system',content:sys},{role:'user',content:v}]})
            });
            let res=await r.json(), txt=res.choices[0].message.content;
            let rd=document.createElement('div'); rd.innerHTML=`<div class="m ${a}">${txt}</div>`;
            box.appendChild(rd); box.scrollTop=box.scrollHeight;
            let u=new SpeechSynthesisUtterance(txt); u.pitch=a=='axon'?0.7:1.2; window.speechSynthesis.speak(u);
            fetch('/api/save',{method:'POST',body:JSON.stringify({agent:a,content:txt})});
        } catch(e){ alert("Check API Key or Connection"); }
    }

    function tk(){
        let SR=window.SpeechRecognition||window.webkitSpeechRecognition; if(!SR) return;
        let rec=new SR(); rec.onresult=e=>{ document.getElementById('u-i').value=e.results[0][0].transcript; sd(); }; rec.start();
    }
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML, axon_s=AXON_1_SYSTEM, aria_s=ARIA_2_SYSTEM, q_status="CONNECTED" if QDRANT_OK else "OFFLINE", gold_code=GOLD_ORACLE_CODE)

@app.route('/api/save', methods=['POST'])
def save():
    d = request.get_json(force=True, silent=True) or {}
    save_event(d.get('agent','?'), 'assistant', d.get('content',''))
    return jsonify({"ok":True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)