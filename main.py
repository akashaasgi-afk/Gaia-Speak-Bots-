import os
import json
import uuid
import datetime
import subprocess
import smtplib
import threading
import time
from email.mime.text import MIMEText
try:
    import schedule
    HAS_SCHEDULE = True
except ImportError:
    HAS_SCHEDULE = False
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, request, jsonify

# --- NEW: AI SMART BRAIN IMPORTS ---
try:
    from sentence_transformers import SentenceTransformer
    # Smallest and fastest model for local execution
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_EMBEDDINGS = True
except Exception:
    HAS_EMBEDDINGS = False

# --- CONFIGURATION ---
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
SENDER_EMAIL = "gaialilith60@gmail.com"
RECIPIENT_EMAIL = "gaialilith60@gmail.com"
SENDER_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

COLLECTION = "gaiaspeak_memory"
VECTOR_DIM = 384 if HAS_EMBEDDINGS else 1 # 384 for MiniLM

# --- TASK & FIX QUEUES ---
tasks_queue = []
pending_fixes = []

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue, PayloadSchemaType
    )
    QDRANT_URL = os.environ.get("QDRANT_URL", "")
    QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY) if QDRANT_URL else None
    QDRANT_OK = bool(qdrant)
except Exception:
    qdrant = None
    QDRANT_OK = False

# --- CORE FUNCTIONS ---

def get_vector(text):
    if HAS_EMBEDDINGS:
        return embed_model.encode(text).tolist()
    return [1.0]

def ensure_collection():
    if not QDRANT_OK: return
    try:
        names = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION not in names:
            qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
            )
    except Exception: pass

def save_event(agent: str, role: str, content: str, event_type: str = "chat"):
    if not QDRANT_OK: return
    try:
        vector = get_vector(content)
        qdrant.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "agent": agent, "role": role, "content": content[:2000],
                    "event_type": event_type, "timestamp": datetime.datetime.utcnow().isoformat(),
                }
            )]
        )
    except Exception: pass

# --- AUTO DEV: BUG SCANNER ---
def analyze_uploaded_file(file_path):
    if file_path.endswith('.py'):
        result = subprocess.run(f"python -m py_compile {file_path}", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr
            tasks_queue.append({"id": str(uuid.uuid4()), "task": f"Fix bug in {os.path.basename(file_path)}", "detail": error_msg, "status": "pending"})
            return error_msg
    return None

# --- AUTOMATION: SCHEDULER & WORKER ---
def send_daily_report():
    if not SENDER_PASS: return
    report_content = f"GaiaSpeak Daily Report - {datetime.date.today()}\n"
    report_content += f"Tasks in Queue: {len(tasks_queue)}\n"
    report_content += "System Status: Online\nMemory Sync: OK"

    msg = MIMEText(report_content)
    msg['Subject'] = 'GaiaSpeak Daily Automated Report'
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.send_message(msg)
    except Exception: pass

def scheduler_loop():
    if not HAS_SCHEDULE:
        return
    schedule.every().day.at("20:00").do(send_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)

def task_worker_loop():
    while True:
        for t in tasks_queue:
            if t["status"] == "pending":
                print(f"Working on: {t['task']}")
        time.sleep(10)

# Start background threads
threading.Thread(target=scheduler_loop, daemon=True).start()
threading.Thread(target=task_worker_loop, daemon=True).start()

# --- AI PERSONAS ---
CERBERUS_SYSTEM = f"You are CERBERUS. Technical Guardian. Address: {CONTRACT_ADDRESS}. Reply ONLY in Bulgarian/English."
LILITH_SYSTEM = "You are LILITH. Strategist & Manager. Reply ONLY in Bulgarian/English."

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

HTML = """<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--silver:#C0C0C0;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--border:#2A2010;--success:#00ff88;}
        *{box-sizing:border-box;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100dvh;display:flex;flex-direction:column;overflow:hidden;}
        .header{background:#111;border-bottom:2px solid var(--border);display:flex;flex-wrap:wrap;min-height:55px;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;text-transform:uppercase;font-size:13px;padding:10px 5px;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}
        .status-bar{background:#000;color:var(--gold);font-family:'Share Tech Mono';font-size:11px;padding:8px 12px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;}
        .badge{padding:2px 8px;border-radius:3px;font-size:10px;border:1px solid;}
        .badge-ok{color:var(--success);border-color:var(--success);}
        .view{flex:1;overflow:hidden;}
        .msgs{height:100%;padding:15px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;background:#050505;padding-bottom:150px;}
        .m{padding:12px;border-radius:6px;max-width:85%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);font-size:15px;word-break:break-word;white-space:pre-wrap;}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}
        .m.cerberus{border-left-color:var(--cerberus);}
        .m.lilith{border-left-color:var(--lilith);}
        .inp-bar{position:fixed;bottom:0;width:100%;padding:12px;background:#111;display:flex;gap:8px;border-top:1px solid var(--gold);z-index:100;}
        .inp-bar input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:15px;}
        .btn-run{background:var(--gold);color:#000;border:none;padding:10px 20px;cursor:pointer;font-weight:bold;border-radius:4px;}
        .btn-mic{background:#1a1a1a;border:1px solid var(--gold);color:var(--gold);padding:10px 14px;border-radius:4px;cursor:pointer;}
        #key-screen{position:fixed;inset:0;background:var(--dark);display:flex;align-items:center;justify-content:center;z-index:999;}
        .key-card{background:#111;border:1px solid var(--gold);padding:40px;text-align:center;border-radius:8px;}
        .bug-alert{background:rgba(255,0,0,0.1);border:1px solid red;color:#ff4444;padding:10px;margin:10px 0;font-size:12px;border-radius:4px;}
    </style>
</head>
<body>

<div id="key-screen">
    <div class="key-card">
        <h2>GAIASPEAK V2.0</h2>
        <input type="password" id="key-inp" placeholder="gsk_..." autocomplete="off">
        <button class="btn-run" onclick="activateKey()" style="width:100%; margin-top:10px;">АКТИВИРАЙ</button>
    </div>
</div>

<div id="main-ui" style="display:none;flex-direction:column;height:100dvh;">
    <div class="header">
        <div id="t-chat" class="tab active" onclick="sw('chat')">COMMAND</div>
        <div id="t-tasks" class="tab" onclick="sw('tasks')">TASKS</div>
        <div id="t-mem" class="tab" onclick="sw('memory')">MEMORY</div>
    </div>

    <div class="status-bar">
        <span>BRAIN: <b style="color:white">Embeddings-Enabled</b></span>
        <span id="clock">00:00:00</span>
        <span id="qdrant-badge" class="badge">QDRANT</span>
    </div>

    <div id="chat-v" class="view">
        <div class="msgs" id="m-box"></div>
    </div>

    <div id="tasks-v" class="view" style="display:none; padding:20px; overflow-y:auto;">
        <h3>ACTIVE TASK QUEUE</h3>
        <div id="task-list"></div>
    </div>

    <div id="mem-v" class="view" style="display:none; padding:20px;">
        <h3>LONG-TERM MEMORY (QDRANT)</h3>
        <div id="mem-list"></div>
    </div>
</div>

<div class="inp-bar" id="inp-bar" style="display:none;">
    <input type="file" id="file-inp" style="display:none;" multiple onchange="uploadToServer()">
    <button class="btn-mic" onclick="document.getElementById('file-inp').click()">📎</button>
    <button class="btn-mic" onclick="startSpeech()">🎤</button>
    <input id="u-i" placeholder="Enter Command..." onkeypress="if(event.key==='Enter')sd()">
    <button class="btn-run" onclick="sd()">RUN</button>
</div>

<script>
    let groqKey = '';
    const CERBERUS_SYS = {{ cerberus_s|tojson }};
    const LILITH_SYS = {{ lilith_s|tojson }};

    function sw(v) {
        document.getElementById('chat-v').style.display = v === 'chat' ? 'flex' : 'none';
        document.getElementById('tasks-v').style.display = v === 'tasks' ? 'block' : 'none';
        document.getElementById('mem-v').style.display = v === 'memory' ? 'block' : 'none';
        if(v==='tasks') loadTasks();
    }

    async function activateKey() {
        const key = document.getElementById('key-inp').value;
        if(key.startsWith('gsk_')) {
            groqKey = key;
            document.getElementById('key-screen').style.display = 'none';
            document.getElementById('main-ui').style.display = 'flex';
            document.getElementById('inp-bar').style.display = 'flex';
        }
    }

    async function sd() {
        const inp = document.getElementById('u-i');
        const v = inp.value.trim();
        if(!v) return;
        addMsg(v, 'user');
        inp.value = '';

        // Call AI via Groq (Cerberus Default)
        const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + groqKey, 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: 'llama-3.1-8b-instant', messages: [{role:'system', content:CERBERUS_SYS}, {role:'user', content:v}]})
        });
        const data = await r.json();
        const txt = data.choices[0].message.content;
        addMsg(txt, 'cerberus');

        // Sync Memory
        fetch('/api/memory/save', {method:'POST', body:JSON.stringify({agent:'cerberus', content:txt})});
    }

    async function uploadToServer() {
        const files = document.getElementById('file-inp').files;
        const formData = new FormData();
        for (const file of files) formData.append('files[]', file);

        addMsg("Scanning files for bugs...", "system");
        const r = await fetch('/api/upload', {method:'POST', body:formData});
        const res = await r.json();
        if(res.bugs && res.bugs.length > 0) {
            res.bugs.forEach(b => {
                if(b.error) addMsg(`BUG FOUND in ${b.file}: <div class="bug-alert">${b.error}</div>`, 'cerberus');
            });
        } else {
            addMsg("Clean Code. Ready for deployment.", "cerberus");
        }
    }

    async function loadTasks() {
        const r = await fetch('/api/tasks');
        const d = await r.json();
        const list = document.getElementById('task-list');
        list.innerHTML = d.tasks.map(t => `<div class="m system" style="margin-bottom:5px;">[${t.status}] ${t.task}</div>`).join('');
    }

    function addMsg(txt, role) {
        const box = document.getElementById('m-box');
        const d = document.createElement('div');
        d.className = 'm ' + role;
        d.innerHTML = txt;
        box.appendChild(d);
        box.scrollTop = box.scrollHeight;
    }

    setInterval(() => { document.getElementById('clock').innerText = new Date().toLocaleTimeString(); }, 1000);
</script>
</body>
</html>"""

# --- ROUTES ---

@app.route('/')
def index():
    ensure_collection()
    return render_template_string(HTML, addr=CONTRACT_ADDRESS, cerberus_s=CERBERUS_SYSTEM, lilith_s=LILITH_SYSTEM)

@app.route('/api/upload', methods=['POST'])
def api_upload():
    files = request.files.getlist('files[]')
    results = []
    for file in files:
        filename = secure_filename(file.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        bug = analyze_uploaded_file(path)
        results.append({'file': filename, 'error': bug})
    return jsonify({'ok': True, 'bugs': results})

@app.route('/api/tasks')
def get_tasks():
    return jsonify({'tasks': tasks_queue})

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/status')
def api_status():
    return jsonify({'qdrant': QDRANT_OK, 'model': 'llama-3.1-8b-instant (Groq SLM)', 'collection': COLLECTION})

@app.route('/api/memory/save', methods=['POST'])
def api_memory_save():
    data = request.get_json(force=True) or {}
    save_event(agent=data.get('agent', 'system'), role=data.get('role', 'assistant'), content=data.get('content', ''), event_type=data.get('event_type', 'chat'))
    return jsonify({'ok': True})

@app.route('/api/memory/recent')
def api_memory_recent():
    agent = request.args.get('agent', '')
    limit = min(int(request.args.get('limit', 20)), 100)
    if not QDRANT_OK:
        return jsonify({'events': [], 'qdrant': False})
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        scroll_filter = None
        if agent:
            scroll_filter = Filter(must=[FieldCondition(key='agent', match=MatchValue(value=agent))])
        results, _ = qdrant.scroll(collection_name=COLLECTION, scroll_filter=scroll_filter, limit=limit, with_payload=True, with_vectors=False)
        return jsonify({'events': [r.payload for r in results], 'qdrant': True})
    except Exception as e:
        return jsonify({'events': [], 'qdrant': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)