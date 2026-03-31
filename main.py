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
RECIPIENT_EMAIL = "gaialilith60@gmail.com"
SENDER_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")

COLLECTION = "gaiaspeak_memory"
VECTOR_DIM = 1

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
        # Ensure keyword index on agent field
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
                vector=[1.0],
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
        scroll_filter = None
        if agent:
            scroll_filter = Filter(must=[FieldCondition(key="agent", match=MatchValue(value=agent))])
        results, _ = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        return [r.payload for r in results]
    except Exception:
        return []


# --- AI PERSONAS ---
CERBERUS_SYSTEM = f"""You are CERBERUS. Technical Guardian of the GaiaSpeak Protocol.
DEPLOYED ADDRESS: {CONTRACT_ADDRESS}.
If you suggest a command, wrap it in [CMD] tags like [CMD]npx hardhat compile[/CMD].
STRICT RULE: Reply ONLY in Bulgarian or English. DO NOT USE ANY OTHER LANGUAGE."""

LILITH_SYSTEM = """You are LILITH. Strategist and Deployment Manager of the GaiaSpeak Protocol.
If you draft a report or email, wrap it in [EMAIL] tags.
STRICT RULE: Reply ONLY in Bulgarian or English. DO NOT USE ANY OTHER LANGUAGE."""

app = Flask(__name__)

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
        .badge-err{color:#ff4444;border-color:#ff4444;}
        .view{flex:1;overflow:hidden;}
        .msgs{height:100%;padding:15px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;background:#050505;padding-bottom:150px;}
        .m{padding:12px;border-radius:6px;max-width:85%;border-left:4px solid var(--gold);background:rgba(255,255,255,0.03);font-size:15px;word-break:break-word;white-space:pre-wrap;}
        .m.user{align-self:flex-end;border-left:none;border-right:4px solid var(--gold);background:rgba(201,168,76,0.1);}
        .m.cerberus{border-left-color:var(--cerberus);}
        .m.lilith{border-left-color:var(--lilith);}
        .m.system{border-left-color:#666;font-size:12px;color:#aaa;font-family:'Share Tech Mono';}
        .action-btn{background:var(--success);color:#000;border:none;padding:8px;margin-top:10px;cursor:pointer;font-weight:bold;width:100%;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:14px;}
        .addr-box{font-size:12px;color:var(--success);background:rgba(0,255,136,0.1);padding:10px;border-radius:4px;margin-top:5px;border:1px solid var(--success);word-break:break-all;}
        .inp-bar{position:fixed;bottom:0;width:100%;padding:12px;background:#111;display:flex;gap:8px;border-top:1px solid var(--gold);}
        .inp-bar input{flex:1;background:#000;border:1px solid var(--border);color:#fff;padding:12px;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:15px;}
        .inp-bar input:focus{outline:none;border-color:var(--gold);}
        .btn-run{background:var(--gold);color:#000;border:none;padding:10px 20px;cursor:pointer;font-weight:bold;font-family:'Rajdhani',sans-serif;font-size:15px;border-radius:4px;}
        .btn-mic{background:#1a1a1a;border:1px solid var(--gold);color:var(--gold);padding:10px 14px;border-radius:4px;cursor:pointer;font-size:16px;}
        .btn-mic.active{background:red;color:white;animation:pulse 1s infinite;}
        @keyframes pulse{0%{opacity:1;}50%{opacity:0.4;}100%{opacity:1;}}
        .agent-sel{background:#050505;padding:8px 12px;font-size:12px;color:var(--gold);display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-bottom:1px solid var(--border);}
        .agent-sel select{background:#000;color:#fff;border:1px solid var(--border);padding:4px 8px;font-family:'Rajdhani',sans-serif;}
        #key-screen{position:fixed;inset:0;background:var(--dark);display:flex;align-items:center;justify-content:center;z-index:999;}
        .key-card{background:#111;border:1px solid var(--gold);border-radius:8px;padding:40px;max-width:420px;width:90%;text-align:center;}
        .key-card h2{color:var(--gold);letter-spacing:4px;margin-bottom:5px;}
        .key-card p{color:#888;font-size:13px;margin-bottom:20px;}
        .key-card input{width:100%;background:#000;border:1px solid var(--border);color:#fff;padding:14px;border-radius:4px;font-size:15px;margin-bottom:10px;}
        .key-card input:focus{outline:none;border-color:var(--gold);}
        .key-card .hint{font-size:11px;color:#555;margin-bottom:20px;}
        .key-card .hint a{color:var(--gold);text-decoration:none;}
        .btn-activate{width:100%;background:none;border:2px solid var(--gold);color:var(--gold);padding:14px;cursor:pointer;font-weight:bold;font-size:16px;letter-spacing:2px;border-radius:4px;font-family:'Rajdhani',sans-serif;}
        .btn-activate:hover{background:var(--gold);color:#000;}
        #key-err{color:#ff4444;font-size:12px;min-height:20px;margin-top:8px;}
        .brief-card{background:#111;border:1px solid var(--border);padding:15px;border-radius:8px;margin-bottom:15px;}
        .brief-card h3{color:var(--gold);margin-top:0;}
    </style>
</head>
<body>

<!-- KEY ENTRY SCREEN -->
<div id="key-screen">
    <div class="key-card">
        <h2>GAIASPEAK</h2>
        <p>CERBERUS &middot; LILITH &middot; FOUNDER ONLY</p>
        <input type="password" id="key-inp" placeholder="gsk_..." autocomplete="off">
        <div class="hint">Ключът се пази само в браузъра. Никъде не се изпраща.<br>Безплатен &ndash; <a href="https://console.groq.com" target="_blank">console.groq.com</a></div>
        <button class="btn-activate" onclick="activateKey()">&#9711; АКТИВИРАЙ</button>
        <div id="key-err"></div>
    </div>
</div>

<!-- MAIN UI (hidden until key validated) -->
<div id="main-ui" style="display:none;flex-direction:column;height:100dvh;">

    <div class="header">
        <div id="t-chat" class="tab active" onclick="sw('chat')">BLOCKCHAIN CMD</div>
        <div id="t-brief" class="tab" onclick="sw('briefing')">NETWORK STATUS</div>
        <div id="t-mem" class="tab" onclick="sw('memory')">ПАМЕТ</div>
    </div>

    <div class="status-bar">
        <span>SLM: <b style="color:white">phi-4-mini</b></span>
        <span id="clock">00:00:00</span>
        <span id="qdrant-badge" class="badge badge-err">QDRANT: OFFLINE</span>
        <span style="font-size:10px;color:#666">{{ addr }}</span>
    </div>

    <!-- CHAT VIEW -->
    <div id="chat-v" class="view" style="display:flex;flex-direction:column;overflow:hidden;">
        <div class="agent-sel">
            AGENT:
            <select id="sel-a">
                <option value="cerberus">CERBERUS (Smart Contracts)</option>
                <option value="lilith">LILITH (Deployment)</option>
                <option value="both">BOTH</option>
            </select>
            <button onclick="toggleVoice()" id="v-tog" style="background:none;border:1px solid var(--gold);color:var(--gold);padding:4px 10px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;">VOICE: ON</button>
            <button onclick="clearChat()" style="background:none;border:1px solid #444;color:#888;padding:4px 10px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;">ИЗЧИСТИ</button>
        </div>
        <div class="msgs" id="m-box">
            <div class="m cerberus">Системата е готова. Smart Contract: <div class="addr-box">{{ addr }}</div></div>
        </div>
    </div>

    <!-- BRIEFING VIEW -->
    <div id="brief-v" class="view" style="display:none;overflow-y:auto;padding:20px;">
        <div class="brief-card">
            <h3>РЕЗЕРВ СТАТУС</h3>
            <p style="margin:5px 0;">GOLD (GSG): <span style="color:var(--success)">LINKED &rarr; {{ addr }}</span></p>
            <p style="margin:5px 0;">SILVER (GSS): <span style="color:var(--silver)">PENDING DEPLOYMENT</span></p>
        </div>
        <div class="brief-card">
            <h3>СИСТЕМНА ИНФОРМАЦИЯ</h3>
            <p id="sys-info" style="font-family:'Share Tech Mono';font-size:12px;color:#aaa;">Зареждане...</p>
        </div>
        <div class="brief-card">
            <button onclick="window.open('https://github.com/MuhammadIsmailIsmail/')" style="width:100%;background:none;border:1px solid var(--gold);color:var(--gold);padding:10px;cursor:pointer;font-family:'Rajdhani',sans-serif;font-size:15px;">SYNC WITH GITHUB</button>
        </div>
    </div>

    <!-- MEMORY VIEW -->
    <div id="mem-v" class="view" style="display:none;overflow-y:auto;padding:15px;">
        <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
            <button onclick="loadMem('cerberus')" style="background:none;border:1px solid var(--cerberus);color:var(--cerberus);padding:6px 14px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;">CERBERUS</button>
            <button onclick="loadMem('lilith')" style="background:none;border:1px solid var(--lilith);color:var(--lilith);padding:6px 14px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;">LILITH</button>
            <button onclick="loadMem('')" style="background:none;border:1px solid var(--gold);color:var(--gold);padding:6px 14px;cursor:pointer;border-radius:3px;font-family:'Rajdhani',sans-serif;">ВСИЧКИ</button>
        </div>
        <div id="mem-list" style="display:flex;flex-direction:column;gap:8px;font-family:'Share Tech Mono';font-size:12px;"></div>
    </div>

</div><!-- end main-ui -->

<div class="inp-bar" id="inp-bar" style="display:none;">
    <button class="btn-mic" id="mic-btn" onclick="startSpeech()">&#127908;</button>
    <input id="u-i" placeholder="Команда..." onkeypress="if(event.key==='Enter')sd()">
    <button class="btn-run" onclick="sd()">RUN</button>
</div>

<script>
    // ---- STATE ----
    let groqKey = '';
    let voiceEnabled = true;
    const CERBERUS_SYS = {{ cerberus_s|tojson }};
    const LILITH_SYS = {{ lilith_s|tojson }};

    // ---- CLOCK ----
    setInterval(() => {
        const el = document.getElementById('clock');
        if (el) el.innerText = new Date().toLocaleTimeString();
    }, 1000);

    // ---- KEY ACTIVATION ----
    window.addEventListener('DOMContentLoaded', () => {
        try {
            const saved = localStorage.getItem('gsk');
            if (saved && saved.startsWith('gsk_')) {
                groqKey = saved;
                showMain();
            }
        } catch(e) {}
    });

    async function activateKey() {
        const inp = document.getElementById('key-inp');
        const err = document.getElementById('key-err');
        const key = inp.value.trim();
        err.innerText = '';
        if (!key.startsWith('gsk_')) { err.innerText = 'Невалиден ключ. Трябва да започва с gsk_'; return; }
        err.innerText = 'Проверка...';
        try {
            const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: 'llama-3.1-8b-instant', messages: [{ role: 'user', content: 'ping' }], max_tokens: 5 })
            });
            if (!r.ok) { err.innerText = 'Грешка: невалиден ключ (' + r.status + ')'; return; }
            groqKey = key;
            try { localStorage.setItem('gsk', key); } catch(e) {}
            showMain();
        } catch(e) {
            err.innerText = 'Мрежова грешка: ' + e.message;
        }
    }

    function showMain() {
        document.getElementById('key-screen').style.display = 'none';
        const mu = document.getElementById('main-ui');
        mu.style.display = 'flex';
        document.getElementById('inp-bar').style.display = 'flex';
        checkStatus();
        loadHistory();
    }

    // ---- STATUS CHECK ----
    async function checkStatus() {
        try {
            const r = await fetch('/api/status');
            const d = await r.json();
            const badge = document.getElementById('qdrant-badge');
            if (d.qdrant) {
                badge.innerText = 'QDRANT: CONNECTED';
                badge.className = 'badge badge-ok';
            } else {
                badge.innerText = 'QDRANT: OFFLINE';
                badge.className = 'badge badge-err';
            }
            const si = document.getElementById('sys-info');
            if (si) si.innerText = 'Model: ' + d.model + '\\nCollection: ' + d.collection + '\\nQdrant: ' + (d.qdrant ? 'OK' : 'OFFLINE');
        } catch(e) {}
    }

    // ---- VOICE ----
    const recognition = (window.SpeechRecognition || window.webkitSpeechRecognition)
        ? new (window.SpeechRecognition || window.webkitSpeechRecognition)() : null;
    if (recognition) { recognition.continuous = false; recognition.interimResults = false; }

    function startSpeech() {
        if (!recognition) { alert('Микрофонът не се поддържа в този браузър.'); return; }
        recognition.start();
        document.getElementById('mic-btn').classList.add('active');
        recognition.onresult = (e) => {
            document.getElementById('u-i').value = e.results[0][0].transcript;
            document.getElementById('mic-btn').classList.remove('active');
            sd();
        };
        recognition.onerror = () => document.getElementById('mic-btn').classList.remove('active');
    }

    function toggleVoice() {
        voiceEnabled = !voiceEnabled;
        document.getElementById('v-tog').innerText = 'VOICE: ' + (voiceEnabled ? 'ON' : 'OFF');
        if (!voiceEnabled) window.speechSynthesis.cancel();
    }

    function speak(text) {
        if (!voiceEnabled) return;
        window.speechSynthesis.cancel();
        const clean = text.replace(/\\[.*?\\]/g, '').replace(/<[^>]*>/g, '');
        const utt = new SpeechSynthesisUtterance(clean);
        utt.lang = /[а-яА-Я]/.test(clean) ? 'bg-BG' : 'en-US';
        window.speechSynthesis.speak(utt);
    }

    // ---- HISTORY ----
    function loadHistory() {
        try {
            const h = JSON.parse(localStorage.getItem('gaia_history') || '[]');
            h.forEach(item => addMsg(item.text, item.role, item.isHtml || false));
        } catch(e) {}
    }

    function saveToHistory(text, role, isHtml) {
        try {
            const h = JSON.parse(localStorage.getItem('gaia_history') || '[]');
            h.push({ text, role, isHtml });
            if (h.length > 100) h.splice(0, h.length - 100);
            localStorage.setItem('gaia_history', JSON.stringify(h));
        } catch(e) {}
    }

    function clearChat() {
        try { localStorage.removeItem('gaia_history'); } catch(e) {}
        const box = document.getElementById('m-box');
        box.innerHTML = '<div class="m cerberus">Историята е изчистена.</div>';
    }

    // ---- CHAT ----
    async function sd() {
        const inp = document.getElementById('u-i');
        const v = inp.value.trim();
        const agent = document.getElementById('sel-a').value;
        if (!v || !groqKey) return;
        inp.value = '';
        addMsg(v, 'user');
        saveToHistory(v, 'user', false);
        saveEventToServer(agent === 'both' ? 'cerberus' : agent, 'user', v);

        if (agent === 'both') {
            await Promise.all([callAgent('cerberus', v), callAgent('lilith', v)]);
        } else {
            await callAgent(agent, v);
        }
    }

    async function callAgent(agent, msg) {
        const sys = agent === 'cerberus' ? CERBERUS_SYS : LILITH_SYS;
        try {
            const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + groqKey, 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: 'llama-3.1-8b-instant', messages: [{ role: 'system', content: sys }, { role: 'user', content: msg }] })
            });
            if (!r.ok) { addMsg('API грешка: ' + r.status, 'system'); return; }
            const data = await r.json();
            const txt = data.choices[0].message.content;
            processResponse(txt, agent);
            speak(txt);
            saveEventToServer(agent, 'assistant', txt);
        } catch(e) {
            addMsg('Грешка: ' + e.message, 'system');
        }
    }

    function processResponse(txt, agent) {
        let html = txt;
        const cmdMatch = txt.match(/\\[CMD\\](.*?)\\[\\/CMD\\]/);
        if (cmdMatch) {
            html += '<br><button class="action-btn" onclick="runCmd(this)" data-cmd="' + cmdMatch[1].replace(/"/g, '&quot;') + '">APPROVE &amp; RUN: ' + cmdMatch[1] + '</button>';
        }
        if (txt.includes('[EMAIL]')) {
            html += '<br><button class="action-btn" style="background:var(--lilith);color:white;" onclick="sendMail(this)" data-content="' + btoa(encodeURIComponent(txt)) + '">ИЗПРАТИ ДОКЛАД</button>';
        }
        addMsg(html, agent, true);
        saveToHistory(html, agent, true);
    }

    function addMsg(txt, role, isHtml = false) {
        const box = document.getElementById('m-box');
        const d = document.createElement('div');
        d.className = 'm ' + role;
        if (isHtml) d.innerHTML = txt; else d.innerText = txt;
        box.appendChild(d);
        box.scrollTop = box.scrollHeight;
    }

    // ---- COMMANDS ----
    async function runCmd(btn) {
        const cmd = btn.getAttribute('data-cmd');
        addMsg('Изпълняване: ' + cmd, 'system');
        try {
            const r = await fetch('/api/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command: cmd }) });
            const res = await r.json();
            addMsg(res.output || res.error || 'Готово.', 'system');
        } catch(e) { addMsg('Грешка: ' + e.message, 'system'); }
    }

    async function sendMail(btn) {
        const content = decodeURIComponent(atob(btn.getAttribute('data-content')));
        addMsg('Lilith изпраща доклад...', 'system');
        try {
            const r = await fetch('/api/send_email', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) });
            const res = await r.json();
            addMsg(res.ok ? 'Успех: Докладът е изпратен.' : 'Грешка: ' + res.error, 'system');
        } catch(e) { addMsg('Грешка: ' + e.message, 'system'); }
    }

    // ---- MEMORY ----
    async function saveEventToServer(agent, role, content) {
        try {
            await fetch('/api/memory/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ agent, role, content, event_type: 'chat' })
            });
        } catch(e) {}
    }

    async function loadMem(agent) {
        const list = document.getElementById('mem-list');
        list.innerHTML = '<div style="color:#666">Зареждане...</div>';
        try {
            const url = agent ? '/api/memory/recent?agent=' + agent + '&limit=30' : '/api/memory/recent?limit=30';
            const r = await fetch(url);
            const d = await r.json();
            if (!d.events || d.events.length === 0) { list.innerHTML = '<div style="color:#666">Няма записи.</div>'; return; }
            list.innerHTML = '';
            d.events.reverse().forEach(ev => {
                const el = document.createElement('div');
                el.style.cssText = 'background:#0a0a0a;border:1px solid #1a1a1a;padding:8px;border-radius:4px;';
                const agentColor = ev.agent === 'cerberus' ? 'var(--cerberus)' : 'var(--lilith)';
                el.innerHTML = '<span style="color:' + agentColor + '">[' + ev.agent.toUpperCase() + ']</span> '
                    + '<span style="color:#555">' + (ev.timestamp || '').substring(0, 19) + '</span> '
                    + '<span style="color:#888">[' + (ev.event_type || 'chat') + ']</span><br>'
                    + '<span style="color:#ccc">' + (ev.content || '').substring(0, 200) + '</span>';
                list.appendChild(el);
            });
        } catch(e) { list.innerHTML = '<div style="color:#ff4444">Грешка: ' + e.message + '</div>'; }
    }

    // ---- VIEW SWITCH ----
    function sw(v) {
        ['chat', 'briefing', 'memory'].forEach(name => {
            const suffix = name === 'chat' ? 'chat' : name === 'briefing' ? 'brief' : 'mem';
            const el = document.getElementById(suffix + '-v');
            if (el) el.style.display = (name === v) ? (name === 'chat' ? 'flex' : 'block') : 'none';
            const tab = document.getElementById('t-' + (name === 'chat' ? 'chat' : name === 'briefing' ? 'brief' : 'mem'));
            if (tab) tab.classList.toggle('active', name === v);
        });
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
        'model': 'microsoft/phi-4-mini-instruct via llama-3.1-8b-instant (Groq SLM)',
        'collection': COLLECTION
    })

@app.route('/api/memory/save', methods=['POST'])
def api_memory_save():
    data = request.get_json(force=True) or {}
    save_event(
        agent=data.get('agent', 'system'),
        role=data.get('role', 'user'),
        content=data.get('content', ''),
        event_type=data.get('event_type', 'chat')
    )
    return jsonify({'ok': True})

@app.route('/api/memory/recent')
def api_memory_recent():
    agent = request.args.get('agent', '')
    limit = min(int(request.args.get('limit', 20)), 100)
    events = get_recent_events(agent=agent or None, limit=limit)
    return jsonify({'events': events, 'qdrant': QDRANT_OK})

@app.route('/api/execute', methods=['POST'])
def api_execute():
    data = request.get_json(force=True) or {}
    cmd = data.get('command', '').strip()
    if not cmd:
        return jsonify({'error': 'No command'}), 400
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        output = (result.stdout + result.stderr).strip()
        return jsonify({'output': output or 'Done.'})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out (30s)'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send_email', methods=['POST'])
def api_send_email():
    if not SENDER_PASS:
        return jsonify({'ok': False, 'error': 'GMAIL_APP_PASSWORD not set'}), 400
    data = request.get_json(force=True) or {}
    content = data.get('content', '')
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
