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

# --- OPTIONAL: sentence_transformers (not required to run) ---
try:
    from sentence_transformers import SentenceTransformer
    _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_EMBEDDINGS = True
except Exception:
    _embed_model = None
    HAS_EMBEDDINGS = False

# --- OPTIONAL: schedule (not required to run) ---
try:
    import schedule as _schedule
    HAS_SCHEDULE = True
except ImportError:
    _schedule = None
    HAS_SCHEDULE = False

# --- CONFIGURATION ---
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
SENDER_EMAIL = "gaialilith60@gmail.com"
RECIPIENT_EMAIL = "gaialilith60@gmail.com"
SENDER_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

COLLECTION = "gaiaspeak_memory"
VECTOR_DIM = 384 if HAS_EMBEDDINGS else 1

# --- QDRANT (optional — degrades gracefully if missing) ---
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct,
        Filter, FieldCondition, MatchValue, PayloadSchemaType
    )
    _QDRANT_URL = os.environ.get("QDRANT_URL", "")
    _QDRANT_KEY = os.environ.get("QDRANT_API_KEY", "")
    qdrant = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_KEY) if _QDRANT_URL else None
    QDRANT_OK = bool(qdrant)
except Exception:
    qdrant = None
    QDRANT_OK = False

# --- IN-MEMORY TASK QUEUE ---
tasks_queue = []
pending_fixes = []

# ---- HELPER FUNCTIONS ----

def get_vector(text):
    if HAS_EMBEDDINGS and _embed_model:
        return _embed_model.encode(text).tolist()
    return [1.0]


def ensure_collection():
    if not QDRANT_OK:
        return
    try:
        names = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION not in names:
            qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
            )
        try:
            qdrant.create_payload_index(
                collection_name=COLLECTION,
                field_name="agent",
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception:
            pass
    except Exception:
        pass


def save_event(agent: str, role: str, content: str, event_type: str = "chat"):
    if not QDRANT_OK:
        return
    try:
        qdrant.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=get_vector(content),
                payload={
                    "agent": agent,
                    "role": role,
                    "content": content[:2000],
                    "event_type": event_type,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                }
            )]
        )
    except Exception:
        pass


def get_recent_events(agent: str = None, limit: int = 20):
    if not QDRANT_OK:
        return []
    try:
        f = None
        if agent:
            f = Filter(must=[FieldCondition(key="agent", match=MatchValue(value=agent))])
        results, _ = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=f,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        return [r.payload for r in results]
    except Exception:
        return []


def analyze_uploaded_file(path):
    if path.endswith(".py"):
        r = subprocess.run(
            f"python -m py_compile {path}",
            shell=True, capture_output=True, text=True
        )
        if r.returncode != 0:
            tasks_queue.append({"task": f"Fix {os.path.basename(path)}", "detail": r.stderr, "status": "pending"})
            return r.stderr
    return None


# ---- BACKGROUND THREADS ----

def _task_worker():
    while True:
        for t in tasks_queue:
            if t.get("status") == "pending":
                print(f"[worker] Processing: {t['task']}")
                t["status"] = "done"
        time.sleep(10)


def _scheduler():
    if HAS_SCHEDULE:
        def _daily():
            if not SENDER_PASS:
                return
            body = (
                f"GaiaSpeak Daily Report - {datetime.date.today()}\n"
                f"Tasks: {len(tasks_queue)}\nPending Fixes: {len(pending_fixes)}\nStatus: Online"
            )
            try:
                msg = MIMEText(body)
                msg["Subject"] = "GaiaSpeak Daily Report"
                msg["From"] = SENDER_EMAIL
                msg["To"] = RECIPIENT_EMAIL
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                    s.login(SENDER_EMAIL, SENDER_PASS)
                    s.send_message(msg)
            except Exception:
                pass
        _schedule.every().day.at("20:00").do(_daily)
        while True:
            _schedule.run_pending()
            time.sleep(60)
    else:
        # Fallback: simple time-based check
        while True:
            now = datetime.datetime.now()
            if now.hour == 20 and now.minute == 0:
                time.sleep(61)
            time.sleep(30)


threading.Thread(target=_task_worker, daemon=True).start()
threading.Thread(target=_scheduler, daemon=True).start()

# ---- AI PERSONAS ----
CERBERUS_SYSTEM = (
    f"You are CERBERUS, the Technical Guardian of the GaiaSpeak Protocol. "
    f"Deployed contract: {CONTRACT_ADDRESS}. "
    "When suggesting shell commands wrap them in [CMD]...[/CMD] tags. "
    "STRICT: Reply ONLY in Bulgarian or English."
)
LILITH_SYSTEM = (
    "You are LILITH, Strategist and Deployment Manager of the GaiaSpeak Protocol. "
    "When drafting reports or emails wrap them in [EMAIL]...[/EMAIL] tags. "
    "STRICT: Reply ONLY in Bulgarian or English."
)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---- HTML TEMPLATE ----
HTML = """<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>GaiaSpeak Command Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root{--gold:#C9A84C;--silver:#C0C0C0;--cerberus:#33CCFF;--lilith:#FF33CC;--dark:#080808;--border:#2A2010;--ok:#00ff88;}
        *{box-sizing:border-box;margin:0;padding:0;}
        body{background:var(--dark);color:#eee;font-family:'Rajdhani',sans-serif;height:100dvh;display:flex;flex-direction:column;overflow:hidden;}
        /* HEADER */
        .hdr{background:#111;border-bottom:2px solid var(--border);display:flex;min-height:52px;}
        .tab{flex:1;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#555;text-transform:uppercase;font-size:13px;letter-spacing:1px;padding:10px 4px;border-bottom:3px solid transparent;transition:all .2s;}
        .tab.on{color:var(--gold);background:rgba(201,168,76,.08);border-bottom-color:var(--gold);}
        /* STATUS BAR */
        .sbar{background:#000;color:var(--gold);font-family:'Share Tech Mono';font-size:11px;padding:6px 12px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;}
        .badge{padding:1px 7px;border-radius:3px;font-size:10px;border:1px solid;}
        .b-ok{color:var(--ok);border-color:var(--ok);}
        .b-err{color:#f44;border-color:#f44;}
        /* VIEWS */
        .view{flex:1;overflow:hidden;display:none;}
        .view.on{display:flex;flex-direction:column;}
        /* CHAT */
        .agent-bar{background:#050505;padding:8px 12px;font-size:12px;color:var(--gold);display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--border);}
        .agent-bar select{background:#000;color:#fff;border:1px solid var(--border);padding:4px 8px;font-family:'Rajdhani',sans-serif;font-size:13px;}
        .btn-sm{background:none;border:1px solid var(--gold);color:var(--gold);padding:3px 10px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;font-size:12px;}
        .msgs{flex:1;padding:15px;display:flex;flex-direction:column;gap:10px;overflow-y:auto;background:#050505;padding-bottom:90px;}
        .m{padding:11px 13px;border-radius:5px;max-width:88%;border-left:4px solid var(--gold);background:rgba(255,255,255,.03);font-size:15px;word-break:break-word;white-space:pre-wrap;line-height:1.5;}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,.09);}
        .m.cerberus{border-left-color:var(--cerberus);}
        .m.lilith{border-left-color:var(--lilith);}
        .m.system{border-left-color:#444;font-size:12px;color:#888;font-family:'Share Tech Mono';}
        .act-btn{background:var(--ok);color:#000;border:none;padding:7px;margin-top:9px;cursor:pointer;font-weight:700;width:100%;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:14px;}
        /* INPUT BAR */
        .ibar{position:fixed;bottom:0;width:100%;padding:10px 12px;background:#111;display:flex;gap:8px;border-top:1px solid var(--gold);z-index:50;}
        .ibar input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:11px;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:15px;}
        .ibar input:focus{outline:none;border-color:var(--gold);}
        .btn-run{background:var(--gold);color:#000;border:none;padding:10px 18px;cursor:pointer;font-weight:700;font-size:15px;border-radius:4px;font-family:'Rajdhani',sans-serif;}
        .btn-mic{background:#1a1a1a;border:1px solid var(--gold);color:var(--gold);padding:10px 13px;border-radius:4px;cursor:pointer;font-size:16px;}
        .btn-mic.rec{background:red;color:#fff;animation:pulse 1s infinite;}
        @keyframes pulse{0%{opacity:1}50%{opacity:.4}100%{opacity:1}}
        /* SCROLLABLE VIEWS */
        .scroll-v{flex:1;overflow-y:auto;padding:16px;}
        .card{background:#111;border:1px solid var(--border);border-radius:7px;padding:15px;margin-bottom:14px;}
        .card h3{color:var(--gold);margin-bottom:10px;font-size:16px;letter-spacing:1px;}
        .mem-row{background:#0a0a0a;border:1px solid #1a1a1a;padding:8px 10px;border-radius:4px;margin-bottom:6px;font-family:'Share Tech Mono';font-size:11px;line-height:1.6;}
        /* KEY SCREEN */
        #ks{position:fixed;inset:0;background:var(--dark);display:flex;align-items:center;justify-content:center;z-index:999;}
        .kc{background:#111;border:1px solid var(--gold);border-radius:8px;padding:40px;max-width:420px;width:90%;text-align:center;}
        .kc h2{color:var(--gold);letter-spacing:5px;font-size:22px;margin-bottom:6px;}
        .kc .sub{color:#666;font-size:13px;margin-bottom:24px;}
        .kc input{width:100%;background:#000;border:1px solid var(--border);color:#fff;padding:13px;border-radius:4px;font-size:15px;margin-bottom:8px;}
        .kc input:focus{outline:none;border-color:var(--gold);}
        .kc .hint{font-size:11px;color:#444;margin-bottom:22px;}
        .kc .hint a{color:var(--gold);text-decoration:none;}
        .btn-act{width:100%;background:none;border:2px solid var(--gold);color:var(--gold);padding:13px;cursor:pointer;font-weight:700;font-size:16px;letter-spacing:3px;border-radius:4px;font-family:'Rajdhani',sans-serif;transition:all .2s;}
        .btn-act:hover{background:var(--gold);color:#000;}
        #kerr{color:#f44;font-size:12px;min-height:18px;margin-top:8px;}
    </style>
</head>
<body>

<!-- KEY SCREEN -->
<div id="ks">
    <div class="kc">
        <h2>GAIASPEAK</h2>
        <div class="sub">CERBERUS &middot; LILITH &middot; FOUNDER ONLY</div>
        <input type="password" id="ki" placeholder="gsk_..." autocomplete="off">
        <div class="hint">Ключът остава в браузъра. Никъде не се изпраща.<br>
            Безплатен &ndash; <a href="https://console.groq.com" target="_blank">console.groq.com</a></div>
        <button class="btn-act" onclick="activateKey()">&#9711; АКТИВИРАЙ</button>
        <div id="kerr"></div>
    </div>
</div>

<!-- MAIN -->
<div id="ui" style="display:none;flex-direction:column;height:100dvh;">
    <div class="hdr">
        <div class="tab on" id="tc" onclick="sw('chat')">CMD</div>
        <div class="tab" id="tt" onclick="sw('tasks')">ЗАДАЧИ</div>
        <div class="tab" id="tm" onclick="sw('memory')">ПАМЕТ</div>
        <div class="tab" id="tb" onclick="sw('brief')">СТАТУС</div>
    </div>
    <div class="sbar">
        <span>SLM: <b style="color:#fff">phi-4-mini / llama-3.1-8b</b></span>
        <span id="clk">--:--:--</span>
        <span id="qbadge" class="badge b-err">QDRANT: OFFLINE</span>
    </div>

    <!-- CHAT -->
    <div class="view on" id="v-chat">
        <div class="agent-bar">
            AGENT:
            <select id="agt">
                <option value="cerberus">CERBERUS (Smart Contracts)</option>
                <option value="lilith">LILITH (Deployment)</option>
                <option value="both">BOTH</option>
            </select>
            <button class="btn-sm" id="vtog" onclick="toggleVoice()">VOICE: ON</button>
            <button class="btn-sm" onclick="clearChat()">ИЗЧИСТИ</button>
        </div>
        <div class="msgs" id="mbox">
            <div class="m cerberus">Системата е готова. Contract: <span style="color:var(--ok);font-family:'Share Tech Mono';font-size:12px;">{{ addr }}</span></div>
        </div>
    </div>

    <!-- TASKS -->
    <div class="view" id="v-tasks">
        <div class="scroll-v">
            <div class="card">
                <h3>TASK QUEUE</h3>
                <div id="tlist"><span style="color:#555;font-size:13px;">Няма задачи.</span></div>
            </div>
        </div>
    </div>

    <!-- MEMORY -->
    <div class="view" id="v-memory">
        <div class="scroll-v">
            <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
                <button class="btn-sm" style="border-color:var(--cerberus);color:var(--cerberus);" onclick="loadMem('cerberus')">CERBERUS</button>
                <button class="btn-sm" style="border-color:var(--lilith);color:var(--lilith);" onclick="loadMem('lilith')">LILITH</button>
                <button class="btn-sm" onclick="loadMem('')">ВСИЧКИ</button>
            </div>
            <div id="mlist"><span style="color:#555;font-size:13px;">Изберете агент.</span></div>
        </div>
    </div>

    <!-- BRIEF -->
    <div class="view" id="v-brief">
        <div class="scroll-v">
            <div class="card">
                <h3>RESERVE STATUS</h3>
                <p style="margin:6px 0;font-size:14px;">GOLD (GSG): <span style="color:var(--ok)">LINKED &rarr; {{ addr }}</span></p>
                <p style="margin:6px 0;font-size:14px;">SILVER (GSS): <span style="color:var(--silver)">PENDING</span></p>
            </div>
            <div class="card">
                <h3>SYSTEM INFO</h3>
                <div id="sysinfo" style="font-family:'Share Tech Mono';font-size:12px;color:#aaa;line-height:1.8;">Зареждане...</div>
            </div>
            <div class="card">
                <button onclick="window.open('https://github.com/MuhammadIsmailIsmail/')" style="width:100%;background:none;border:1px solid var(--gold);color:var(--gold);padding:10px;cursor:pointer;font-family:'Rajdhani',sans-serif;font-size:15px;border-radius:4px;">SYNC WITH GITHUB</button>
            </div>
        </div>
    </div>
</div>

<!-- INPUT BAR -->
<div class="ibar" id="ibar" style="display:none;">
    <input type="file" id="fup" style="display:none;" multiple onchange="uploadFiles()">
    <button class="btn-mic" onclick="document.getElementById('fup').click()">&#128206;</button>
    <button class="btn-mic" id="micbtn" onclick="startSpeech()">&#127908;</button>
    <input id="ui-in" placeholder="Команда..." onkeypress="if(event.key==='Enter')send()">
    <button class="btn-run" onclick="send()">RUN</button>
</div>

<script>
    // ---- CONSTANTS (injected server-side) ----
    const CSYS = {{ cerberus_s|tojson }};
    const LSYS = {{ lilith_s|tojson }};
    const MODEL = 'llama-3.1-8b-instant';

    // ---- STATE ----
    let gkey = '';
    let voiceOn = true;

    // ---- CLOCK ----
    setInterval(() => { const e = document.getElementById('clk'); if(e) e.innerText = new Date().toLocaleTimeString(); }, 1000);

    // ---- KEY ACTIVATION ----
    window.addEventListener('DOMContentLoaded', () => {
        try { const k = localStorage.getItem('gsk'); if(k && k.startsWith('gsk_')){ gkey=k; showMain(); } } catch(e){}
    });

    async function activateKey() {
        const key = document.getElementById('ki').value.trim();
        const err = document.getElementById('kerr');
        err.innerText = '';
        if(!key.startsWith('gsk_')){ err.innerText = 'Ключът трябва да започва с gsk_'; return; }
        err.innerText = 'Проверка...';
        try {
            const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
                method:'POST',
                headers:{'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                body:JSON.stringify({model:MODEL, messages:[{role:'user',content:'ping'}], max_tokens:3})
            });
            if(!r.ok){ err.innerText = 'Невалиден ключ ('+r.status+')'; return; }
            gkey = key;
            try{ localStorage.setItem('gsk', key); } catch(e){}
            showMain();
        } catch(e){ err.innerText = 'Грешка: '+e.message; }
    }

    function showMain() {
        document.getElementById('ks').style.display = 'none';
        const ui = document.getElementById('ui');
        ui.style.display = 'flex';
        document.getElementById('ibar').style.display = 'flex';
        checkStatus();
        restoreHistory();
    }

    // ---- STATUS ----
    async function checkStatus() {
        try {
            const d = await (await fetch('/api/status')).json();
            const b = document.getElementById('qbadge');
            b.innerText = d.qdrant ? 'QDRANT: CONNECTED' : 'QDRANT: OFFLINE';
            b.className = 'badge ' + (d.qdrant ? 'b-ok' : 'b-err');
            const si = document.getElementById('sysinfo');
            if(si) si.innerText = 'Model: '+d.model+'\\nCollection: '+d.collection+'\\nQdrant: '+(d.qdrant?'OK':'OFFLINE');
        } catch(e){}
    }

    // ---- VOICE ----
    const SR = (window.SpeechRecognition || window.webkitSpeechRecognition);
    const rec = SR ? new SR() : null;
    if(rec){ rec.continuous = false; rec.interimResults = false; }

    function startSpeech() {
        if(!rec){ alert('Микрофонът не се поддържа в този браузър.'); return; }
        rec.start();
        document.getElementById('micbtn').classList.add('rec');
        rec.onresult = e => { document.getElementById('ui-in').value = e.results[0][0].transcript; document.getElementById('micbtn').classList.remove('rec'); send(); };
        rec.onerror = () => document.getElementById('micbtn').classList.remove('rec');
    }

    function toggleVoice() {
        voiceOn = !voiceOn;
        document.getElementById('vtog').innerText = 'VOICE: '+(voiceOn?'ON':'OFF');
        if(!voiceOn) window.speechSynthesis.cancel();
    }

    function speak(text) {
        if(!voiceOn) return;
        window.speechSynthesis.cancel();
        const clean = text.replace(/\\[.*?\\]/g,'').replace(/<[^>]*>/g,'');
        const u = new SpeechSynthesisUtterance(clean);
        u.lang = /[а-яА-Я]/.test(clean) ? 'bg-BG' : 'en-US';
        window.speechSynthesis.speak(u);
    }

    // ---- HISTORY ----
    function restoreHistory() {
        try {
            const h = JSON.parse(localStorage.getItem('gh') || '[]');
            h.forEach(i => addMsg(i.t, i.r, i.h));
        } catch(e){}
    }

    function saveHistory(t, r, h) {
        try {
            const arr = JSON.parse(localStorage.getItem('gh') || '[]');
            arr.push({t,r,h});
            if(arr.length > 120) arr.splice(0, arr.length-120);
            localStorage.setItem('gh', JSON.stringify(arr));
        } catch(e){}
    }

    function clearChat() {
        try{ localStorage.removeItem('gh'); } catch(e){}
        document.getElementById('mbox').innerHTML = '<div class="m system">Историята е изчистена.</div>';
    }

    // ---- CHAT ----
    async function send() {
        const inp = document.getElementById('ui-in');
        const msg = inp.value.trim();
        const agent = document.getElementById('agt').value;
        if(!msg || !gkey) return;
        inp.value = '';
        addMsg(msg, 'user');
        saveHistory(msg, 'user', false);
        syncMem(agent==='both'?'cerberus':agent, 'user', msg);

        if(agent === 'both') {
            await Promise.all([callAgent('cerberus', msg), callAgent('lilith', msg)]);
        } else {
            await callAgent(agent, msg);
        }
    }

    async function callAgent(agent, msg) {
        const sys = agent==='cerberus' ? CSYS : LSYS;
        try {
            const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
                method:'POST',
                headers:{'Authorization':'Bearer '+gkey,'Content-Type':'application/json'},
                body:JSON.stringify({model:MODEL, messages:[{role:'system',content:sys},{role:'user',content:msg}]})
            });
            if(!r.ok){ addMsg('API грешка: '+r.status, 'system'); return; }
            const d = await r.json();
            const txt = d.choices[0].message.content;
            processReply(txt, agent);
            speak(txt);
            syncMem(agent, 'assistant', txt);
        } catch(e){ addMsg('Грешка: '+e.message, 'system'); }
    }

    function processReply(txt, agent) {
        let html = txt;
        const cm = txt.match(/\\[CMD\\](.*?)\\[\\/CMD\\]/s);
        if(cm) html += '<br><button class="act-btn" data-cmd="'+cm[1].replace(/"/g,'&quot;')+'" onclick="runCmd(this)">APPROVE &amp; RUN: '+cm[1]+'</button>';
        if(txt.includes('[EMAIL]')) html += '<br><button class="act-btn" style="background:var(--lilith);color:#fff;" data-enc="'+btoa(encodeURIComponent(txt))+'" onclick="sendEmail(this)">ИЗПРАТИ ДОКЛАД</button>';
        addMsg(html, agent, true);
        saveHistory(html, agent, true);
    }

    function addMsg(txt, role, isHtml=false) {
        const box = document.getElementById('mbox');
        const d = document.createElement('div');
        d.className = 'm '+role;
        if(isHtml) d.innerHTML = txt; else d.innerText = txt;
        box.appendChild(d);
        box.scrollTop = box.scrollHeight;
    }

    // ---- SERVER ACTIONS ----
    async function runCmd(btn) {
        const cmd = btn.getAttribute('data-cmd');
        addMsg('Изпълняване: '+cmd, 'system');
        try {
            const r = await fetch('/api/execute', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:cmd})});
            const d = await r.json();
            addMsg(d.output || d.error || 'Готово.', 'system');
        } catch(e){ addMsg('Грешка: '+e.message, 'system'); }
    }

    async function sendEmail(btn) {
        const content = decodeURIComponent(atob(btn.getAttribute('data-enc')));
        addMsg('Изпращане на доклад...', 'system');
        try {
            const r = await fetch('/api/send_email', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});
            const d = await r.json();
            addMsg(d.ok ? 'Докладът е изпратен.' : 'Грешка: '+d.error, 'system');
        } catch(e){ addMsg('Грешка: '+e.message, 'system'); }
    }

    async function uploadFiles() {
        const files = document.getElementById('fup').files;
        const fd = new FormData();
        for(const f of files) fd.append('files[]', f);
        addMsg('Анализ на файловете...', 'system');
        try {
            const r = await fetch('/api/upload', {method:'POST', body:fd});
            const d = await r.json();
            if(d.bugs && d.bugs.length) {
                d.bugs.forEach(b => { if(b.error) addMsg('БАГ в '+b.file+': '+b.error, 'system'); else addMsg('Файл OK: '+b.file, 'system'); });
            }
        } catch(e){ addMsg('Грешка: '+e.message, 'system'); }
    }

    // ---- MEMORY ----
    async function syncMem(agent, role, content) {
        try { await fetch('/api/memory/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,role,content,event_type:'chat'})}); } catch(e){}
    }

    async function loadMem(agent) {
        const list = document.getElementById('mlist');
        list.innerHTML = '<span style="color:#555;font-size:13px;">Зареждане...</span>';
        try {
            const url = agent ? '/api/memory/recent?agent='+agent+'&limit=40' : '/api/memory/recent?limit=40';
            const d = await (await fetch(url)).json();
            if(!d.events || !d.events.length){ list.innerHTML='<span style="color:#555;font-size:13px;">Няма записи.</span>'; return; }
            list.innerHTML = '';
            d.events.slice().reverse().forEach(ev => {
                const el = document.createElement('div');
                el.className = 'mem-row';
                const ac = ev.agent==='cerberus' ? 'var(--cerberus)' : 'var(--lilith)';
                el.innerHTML = '<span style="color:'+ac+'">['+(ev.agent||'?').toUpperCase()+']</span> '
                    +'<span style="color:#555">'+(ev.timestamp||'').substring(0,19)+'</span> '
                    +'<span style="color:#666">['+( ev.event_type||'chat')+']</span><br>'
                    +'<span style="color:#bbb">'+(ev.content||'').substring(0,220)+'</span>';
                list.appendChild(el);
            });
        } catch(e){ list.innerHTML='<span style="color:#f44">Грешка: '+e.message+'</span>'; }
    }

    // ---- TASKS ----
    async function loadTasks() {
        try {
            const d = await (await fetch('/api/tasks')).json();
            const list = document.getElementById('tlist');
            if(!d.tasks || !d.tasks.length){ list.innerHTML='<span style="color:#555;font-size:13px;">Няма задачи.</span>'; return; }
            list.innerHTML = d.tasks.map(t=>'<div class="mem-row"><b style="color:var(--gold)">['+t.status+']</b> '+t.task+'</div>').join('');
        } catch(e){}
    }

    // ---- VIEW SWITCH ----
    const VIEWS = {chat:'v-chat', tasks:'v-tasks', memory:'v-memory', brief:'v-brief'};
    const TABS  = {chat:'tc', tasks:'tt', memory:'tm', brief:'tb'};
    function sw(name) {
        Object.keys(VIEWS).forEach(k => {
            const v = document.getElementById(VIEWS[k]);
            const t = document.getElementById(TABS[k]);
            if(v) v.className = 'view'+(k===name?' on':'');
            if(t) t.className = 'tab'+(k===name?' on':'');
        });
        if(name==='tasks') loadTasks();
        if(name==='brief') checkStatus();
    }
</script>
</body>
</html>"""

# ---- FLASK ROUTES ----

@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/')
def index():
    ensure_collection()
    return render_template_string(
        HTML,
        addr=CONTRACT_ADDRESS,
        cerberus_s=CERBERUS_SYSTEM,
        lilith_s=LILITH_SYSTEM
    )


@app.route('/api/status')
def api_status():
    return jsonify({
        'qdrant': QDRANT_OK,
        'model': 'llama-3.1-8b-instant (Groq / phi-4-mini class)',
        'collection': COLLECTION,
        'embeddings': HAS_EMBEDDINGS,
    })


@app.route('/api/memory/save', methods=['POST'])
def api_memory_save():
    d = request.get_json(force=True) or {}
    save_event(
        agent=d.get('agent', 'system'),
        role=d.get('role', 'user'),
        content=d.get('content', ''),
        event_type=d.get('event_type', 'chat')
    )
    return jsonify({'ok': True})


@app.route('/api/memory/recent')
def api_memory_recent():
    agent = request.args.get('agent', '')
    limit = min(int(request.args.get('limit', 20)), 100)
    events = get_recent_events(agent=agent or None, limit=limit)
    return jsonify({'events': events, 'qdrant': QDRANT_OK})


@app.route('/api/tasks')
def api_tasks():
    return jsonify({'tasks': tasks_queue})


@app.route('/api/upload', methods=['POST'])
def api_upload():
    results = []
    for f in request.files.getlist('files[]'):
        fname = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        f.save(path)
        err = analyze_uploaded_file(path)
        results.append({'file': fname, 'error': err})
    return jsonify({'ok': True, 'bugs': results})


@app.route('/api/execute', methods=['POST'])
def api_execute():
    d = request.get_json(force=True) or {}
    cmd = d.get('command', '').strip()
    if not cmd:
        return jsonify({'error': 'No command'}), 400
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return jsonify({'output': (r.stdout + r.stderr).strip() or 'Done.'})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout (30s)'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/send_email', methods=['POST'])
def api_send_email():
    if not SENDER_PASS:
        return jsonify({'ok': False, 'error': 'GMAIL_APP_PASSWORD not configured'}), 400
    d = request.get_json(force=True) or {}
    content = d.get('content', '')
    try:
        msg = MIMEText(content)
        msg['Subject'] = 'GaiaSpeak Protocol Report'
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.send_message(msg)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
