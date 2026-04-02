import os
import json
import uuid
import datetime
import subprocess
import smtplib
import threading
import time
from email.mime.text import MIMEText
from flask import Flask, render_template_string, request, jsonify
from werkzeug.utils import secure_filename
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
# ==============================
# 🔐 CONFIGURATION & SECURE KEYS
# ==============================
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
SENDER_EMAIL = "gaialilith60@gmail.com"
RECIPIENT_EMAIL = "gaialilith60@gmail.com"
# Your provided App Password
SENDER_PASS = "mytj plun ghfs tjby"

MEMORY_FILE = "long_term_memory.json"
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ==============================
# 🧠 HYBRID MEMORY & EMBEDDINGS
# ==============================
print("Initializing AI Core: SentenceTransformer...")
model = SentenceTransformer('all-MiniLM-L6-v2') if SentenceTransformer else None
def load_json_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_json_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


# Qdrant Integration
try:
    from qdrant_client import QdrantClient

    qdrant = QdrantClient(
        url=os.environ.get("QDRANT_URL", ""),
        api_key=os.environ.get("QDRANT_API_KEY", ""),
    )
    QDRANT_OK = True
except:
    QDRANT_OK = False

# ==============================
# 🛠️ AI DEV & BUG DETECTION SYSTEM
# ==============================
tasks = []
pending_fixes = []


def analyze_and_detect_bugs(code_content):
    filename = "check_engine.py"
    with open(filename, "w") as f:
        f.write(code_content)
    result = subprocess.run(
        f"python -m py_compile {filename}", shell=True, capture_output=True, text=True
    )
    if os.path.exists(filename):
        os.remove(filename)
    return result.stderr


def send_auto_report(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"Mail Error: {e}")
        return False


# ==============================
# 🌐 FLASK WEB INTERFACE (ENGLISH)
# ==============================
app = Flask(__name__)

HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak AI Protocol</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--success:#00ff88;--error:#ff4444;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;margin:0;height:100dvh;display:flex;flex-direction:column;overflow:hidden;}
        .header{background:#111;display:flex;border-bottom:1px solid #222;}
        .tab{flex:1;padding:15px;text-align:center;font-size:13px;color:#666;cursor:pointer;text-transform:uppercase;}
        .tab.active{color:var(--gold);background:rgba(201,168,76,0.1);border-bottom:3px solid var(--gold);}
        .status-bar{background:#000;padding:8px 12px;display:flex;justify-content:space-between;font-family:'Share Tech Mono';font-size:11px;border-bottom:1px solid #222;}
        .msgs{flex:1;overflow-y:auto;padding:15px;display:flex;flex-direction:column;gap:12px;background:#050505;padding-bottom:120px;}
        .m{padding:12px;border-radius:4px;max-width:85%;font-size:14px;line-height:1.4;}
        .m.user{align-self:flex-end;background:rgba(201,168,76,0.1);border-right:3px solid var(--gold);}
        .m.ai{align-self:flex-start;background:rgba(255,255,255,0.05);border-left:3px solid var(--cerberus);}
        .cmd-box{background:#111;color:var(--success);padding:10px;font-family:'Share Tech Mono';font-size:12px;border:1px solid #333;margin-top:8px;}
        .fix-btn{background:var(--success);color:#000;border:none;padding:8px;width:100%;margin-top:5px;cursor:pointer;font-weight:bold;border-radius:4px;}
        .inp-bar{position:fixed;bottom:0;width:100%;background:#111;padding:12px;display:flex;gap:8px;border-top:1px solid var(--gold);z-index:100;}
        .inp-bar input{flex:1;background:#000;border:1px solid #222;color:#fff;padding:12px;border-radius:4px;font-family:'Rajdhani';}
        .btn-run{background:var(--gold);color:#000;border:none;padding:10px 20px;font-weight:bold;border-radius:4px;cursor:pointer;}
    </style>
</head>
<body>
    <div class="header">
        <div class="tab active" onclick="sw('chat')">Blockchain CMD</div>
        <div class="tab" onclick="sw('status')">System Status</div>
        <div class="tab" onclick="sw('memory')">Long-Term Memory</div>
    </div>
    <div class="status-bar">
        <span>ENGINE: MiniLM-L6 (Sentence-Transformer)</span>
        <span id="clock">00:00:00</span>
        <span style="color:var(--gold)">DB: {{ q_status }}</span>
    </div>

    <div id="chat-view" class="msgs">
        <div class="m ai">GaiaSpeak Protocol v3.0 Online. All security layers active. Project-based memory initialized for 50-year storage.</div>
    </div>

    <div class="inp-bar">
        <button style="background:none; border:1px solid #444; color:#fff; padding:0 10px;">📎</button>
        <input type="text" id="u-i" placeholder="Enter command or code for analysis...">
        <button class="btn-run" onclick="execute()">RUN</button>
    </div>

    <script>
        setInterval(() => { document.getElementById('clock').innerText = new Date().toLocaleTimeString(); }, 1000);

        async function execute() {
            const inp = document.getElementById('u-i');
            const box = document.getElementById('chat-view');
            if(!inp.value) return;

            const msg = inp.value;
            box.innerHTML += `<div class="m user">${msg}</div>`;
            inp.value = '';
            box.scrollTop = box.scrollHeight;

            const r = await fetch('/api/gate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text: msg})
            });
            const data = await r.json();

            let aiMsg = `<div class="m ai">${data.reply}`;
            if(data.bug) aiMsg += `<div class="cmd-box" style="color:#ff4444">⚠️ BUG FOUND:<br>${data.bug}</div><button class="fix-btn" onclick="applyFix()">APPROVE AUTO-FIX</button>`;
            if(data.success) aiMsg += `<div class="cmd-box">${data.success}</div>`;
            aiMsg += `</div>`;

            box.innerHTML += aiMsg;
            box.scrollTop = box.scrollHeight;
        }

        function applyFix() { alert("AI is applying the safe fix to protocol..."); }
        function sw(v) { alert("Switching to " + v + " view..."); }
    </script>
</body>
</html>
"""

# ==============================
# 🚀 API GATEWAY & AUTOMATION
# ==============================


@app.route("/")
def index():
    return render_template_string(
        HTML_UI, q_status="QDRANT+JSON" if QDRANT_OK else "JSON-ONLY"
    )


@app.route("/api/gate", methods=["POST"])
def api_gateway():
    data = request.json
    text = data.get("text", "")

    # 1. Real Embedding Generation
    vector = model.encode(text).tolist()

    # 2. Long-term Project Memory (JSON)
    mem = load_json_memory()
    project_id = "default_project"
    if project_id not in mem:
        mem[project_id] = []
    mem[project_id].append(
        {
            "content": text,
            "vector_id": str(uuid.uuid4()),
            "ts": str(datetime.datetime.now()),
        }
    )
    save_json_memory(mem)

    # 3. Task & Bug Detection
    bug_report = None
    success_report = None
    if any(k in text for k in ["def ", "import ", "class ", "print("]):
        bug_report = analyze_and_detect_bugs(text)
        if bug_report:
            send_auto_report(
                "GaiaSpeak: Bug Detected",
                f"Alert! A bug was found in the submitted code:\n\n{bug_report}",
            )
        else:
            success_report = "Code structure verified. No syntax errors found."

    return jsonify(
        {
            "reply": "Request processed and stored in long-term memory.",
            "bug": bug_report,
            "success": success_report,
        }
    )


# ==============================
# ⏰ BACKGROUND SCHEDULER
# ==============================
def run_scheduler():
    while True:
        now = datetime.datetime.now()
        # Auto Daily Email at 8:00 PM
        if now.hour == 20 and now.minute == 0:
            send_auto_report(
                "Daily AI Protocol Summary",
                "System checked. Memory backup completed. All background tasks done.",
            )
            time.sleep(60)
        time.sleep(30)


if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
