import os
import json
import uuid
import datetime
import subprocess
import smtplib
from email.mime.text import MIMEText
from flask import Flask, render_template_string, request, jsonify

# --- CONFIGURATION ---
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
SENDER_EMAIL = "gaialilith60@gmail.com"
# RECIPIENT_EMAIL bhi wahi hai taake Bogdan ko inbox mein miley
RECIPIENT_EMAIL = "gaialilith60@gmail.com" 
# Replit Secrets (🔒) mein 'GMAIL_APP_PASSWORD' ke naam se save karein
SENDER_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")

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
        qdrant.upsert(
            collection_name="gaiaspeak_memory",
            points=[PointStruct(id=str(uuid.uuid4()), vector=[1.0], payload={
                "agent": agent, "role": role, "content": content[:2000],
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })]
        )
    except: pass

CERBERUS_SYSTEM = f"""You are CERBERUS. Technical Guardian. DEPLOYED ADDRESS: {CONTRACT_ADDRESS}. 
If you suggest a command, wrap it in [CMD] tags, e.g., [CMD]npx hardhat test[/CMD]. Always reply in Urdu/English mix as per user style."""

LILITH_SYSTEM = f"""You are LILITH. Deployment Manager. 
If you draft a report or email, wrap it in [EMAIL] tags. The system will automatically send it to {RECIPIENT_EMAIL}."""

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak Command Center v2.0</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--border:#2A2010;--success:#00ff88;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100dvh;display:flex;flex-direction:column;overflow:hidden;}
        .header{background:#111;border-bottom:2px solid var(--border);display:flex;min-height:55px;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;text-transform:uppercase;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}
        .msgs{flex:1;padding:15px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;background:#050505;padding-bottom:120px;}
        .m{padding:12px;border-radius:6px;max-width:90%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);font-size:15px;word-break:break-word;}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}
        .action-btn{background:var(--success);color:#000;border:none;padding:8px;margin-top:10px;cursor:pointer;font-weight:bold;width:100%;border-radius:4px;}
        .inp-bar{position:fixed;bottom:0;width:100%;padding:15px;background:#111;display:flex;gap:8px;border-top:2px solid var(--gold);box-sizing:border-box;}
        input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;}
        button.exec{background:var(--gold);color:#000;border:none;padding:10px 20px;cursor:pointer;font-weight:bold;}
    </style>
</head>
<body onload="initMemory()">
    <div class="header">
        <div id="t-chat" class="tab active" onclick="sw('chat')">BLOCKCHAIN CMD</div>
        <div id="t-brief" class="tab" onclick="sw('briefing')">NETWORK STATUS</div>
    </div>
    <div class="msgs" id="m-box"></div>
    <div class="inp-bar">
        <select id="sel-a" style="background:#000;color:var(--gold);border:1px solid var(--border);border-radius:4px;">
            <option value="cerberus">CERB</option>
            <option value="lilith">LILI</option>
        </select>
        <input id="u-i" placeholder="Command..." onkeypress="if(event.key==='Enter')sd()">
        <button class="exec" onclick="sd()">RUN</button>
        <button onclick="exportData()" style="background:none;border:1px solid #444;color:#888;font-size:10px;">EXP</button>
    </div>

    <script>
        async function sd(){
            let i=document.getElementById('u-i'), v=i.value, a=document.getElementById('sel-a').value;
            if(!v)return; i.value='';
            addMsg(v, 'user');

            let sys = a=='cerberus' ? `{{ cerberus_s|safe }}` : `{{ lilith_s|safe }}`;
            try {
                let r=await fetch('https://api.groq.com/openai/v1/chat/completions',{
                    method:'POST', headers:{'Authorization':'Bearer '+localStorage.getItem('gsk'),'Content-Type':'application/json'},
                    body:JSON.stringify({ model:'llama-3.1-8b-instant', messages:[{role:'system',content:sys},{role:'user',content:v}] })
                });
                let res=await r.json(), txt=res.choices[0].message.content;
                processResponse(txt, a);
            } catch(e){ console.error(e); }
        }

        function processResponse(txt, agent) {
            let html = txt;
            if(txt.includes('[CMD]')){
                let cmd = txt.match(/\[CMD\](.*?)\[\/CMD\]/)[1];
                html += `<button class="action-btn" onclick="runCmd('${cmd}')">APPROVE & RUN: ${cmd}</button>`;
            }
            if(txt.includes('[EMAIL]')){
                html += `<button class="action-btn" style="background:var(--lilith)" onclick="sendMail('${btoa(txt)}')">SEND REPORT TO BOGDAN</button>`;
            }
            addMsg(html, agent, true);
        }

        function addMsg(txt, role, isHtml=false){
            let box=document.getElementById('m-box'), d=document.createElement('div');
            d.className='m '+role;
            isHtml ? d.innerHTML=txt : d.innerText=txt;
            box.appendChild(d); box.scrollTop=box.scrollHeight;
        }

        async function runCmd(cmd){
            addMsg("Executing: " + cmd, 'system');
            let r = await fetch('/api/execute', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd})});
            let res = await r.json();
            addMsg(res.output || res.error, 'system');
        }

        async function sendMail(encodedContent){
            addMsg("Lilith is dispatching the report...", 'system');
            let r = await fetch('/api/send_email', {
                method:'POST', 
                headers:{'Content-Type':'application/json'}, 
                body:JSON.stringify({content: atob(encodedContent)})
            });
            let res = await r.json();
            if(res.ok) addMsg("Report sent successfully to gaialilith60@gmail.com", 'system');
            else addMsg("Error: " + res.error, 'system');
        }

        function exportData(){
            let blob = new Blob([document.getElementById('m-box').innerText], {type:'text/plain'});
            let a = document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='GaiaReport.txt'; a.click();
        }
        function sw(v){ /* Tab switching logic */ }
        function initMemory(){ /* Load history */ }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, addr=CONTRACT_ADDRESS, cerberus_s=CERBERUS_SYSTEM, lilith_s=LILITH_SYSTEM)

@app.route("/api/execute", methods=["POST"])
def execute():
    cmd = request.json.get('command')
    try:
        if not cmd.startswith(('npx hardhat', 'git')): return jsonify({"error": "Unauthorized command"})
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return jsonify({"output": result.decode()})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/send_email", methods=["POST"])
def send_email():
    content = request.json.get('content')
    try:
        msg = MIMEText(content)
        msg['Subject'] = f"GaiaSpeak Mission Report - {datetime.datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)