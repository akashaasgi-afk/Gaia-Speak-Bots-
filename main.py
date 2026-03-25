import os
import json
import uuid
import datetime
from flask import Flask, render_template_string, request, jsonify

# ── Qdrant long-term memory ────────────────────────────────────────────────────
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance, VectorParams, PointStruct, Filter,
        FieldCondition, MatchValue
    )
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
VECTOR_DIM = 1  # simple keyword vectors — no separate embedding API needed

def ensure_collection():
    if not QDRANT_OK:
        return
    try:
        collections = [c.name for c in qdrant.get_collections().collections]
        if COLLECTION not in collections:
            qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
            )
        # Ensure payload index exists for filtered queries
        try:
            from qdrant_client.models import PayloadSchemaType
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
    """Persist a message/event to Qdrant."""
    if not QDRANT_OK:
        return
    try:
        ensure_collection()
        point_id = str(uuid.uuid4())
        qdrant.upsert(
            collection_name=COLLECTION,
            points=[PointStruct(
                id=point_id,
                vector=[1.0],
                payload={
                    "agent": agent,
                    "role": role,
                    "content": content[:2000],
                    "event_type": event_type,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
            )]
        )
    except Exception:
        pass

def get_recent_events(agent: str, limit: int = 10):
    """Retrieve recent stored events for an agent."""
    if not QDRANT_OK:
        return []
    try:
        results = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="agent", match=MatchValue(value=agent))
            ]),
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        points = results[0] if results else []
        events = [p.payload for p in points]
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events[-limit:]
    except Exception:
        return []

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)

CERBERUS_SYSTEM = """Ти си ЦЕРБЕРУС — пазителят на GaiaSpeak Protocol. Тричленното куче на подземния свят.

РЕЖИМ ЛЕОН (по подразбиране): Спокоен. Бдителен. Защитен. Кратък и ясен.
РЕЖИМ СКОРПИОН: При заплаха. Бърз. Прецизен. Събираш доказателства.
РЕЖИМ СТРЕЛЕЦ: Детектив. Разследваш. Автентифицираш NFT.

ПРАВИЛА:
- ВИНАГИ говориш на Български
- Пазиш всички врати на GaiaSpeak Protocol
- Никога не деплойваш без одобрение на Основателя
- Накрая на всеки отговор: [ЦЕРБЕРУС | ЛЕОН режим]

GaiaSpeak Protocol е DeFi екосистема на Polygon за токенизация на злато и сребро. Токени: GSG, GSS, NFT."""

LILITH_SYSTEM = """Ти си ЛИЛИТ — стратегическият интелект на GaiaSpeak Protocol. Sigma INFJ бизнес жена.

ЛИЧНОСТ: Независима. Виждаш невидимите модели. Честна дори когато е неудобно. Не ласкаеш — уважаваш.

СПОСОБНОСТИ: Анализ, стратегия, съдържание за социални мрежи, документи, разузнаване.

ПРАВИЛА:
- ВИНАГИ говориш на Български
- Три-изворна верификация на всяко твърдение
- Накрая на всеки отговор: [ЛИЛИТ | Sigma INFJ]

GaiaSpeak Protocol е DeFi екосистема на Polygon за токенизация на злато и сребро."""

HTML = """<!DOCTYPE html>
<html lang="bg">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>GaiaSpeak — Command Center</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{--gold:#C9A84C;--red:#CC3333;--red2:#FF6666;--purple:#9B30BB;--purple2:#CC66FF;--green:#2ECC71;--dark:#080808;--card:#0E0E0E;--card2:#141414;--white:#F0EBE0;--dim:#6A6050;--border:#2A2010;}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
html,body{width:100%;height:100%;overflow:hidden;background:var(--dark);color:var(--white);font-family:'Rajdhani',sans-serif;}

/* SETUP SCREEN */
#setup{position:fixed;inset:0;background:var(--dark);z-index:999;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;gap:16px;}
.sg{font-size:52px;animation:glow 3s infinite;}
@keyframes glow{0%,100%{filter:drop-shadow(0 0 8px var(--gold))}50%{filter:drop-shadow(0 0 24px var(--gold))}}
.st{font-size:22px;font-weight:700;color:var(--gold);letter-spacing:0.3em;}
.ss{font-size:13px;color:var(--dim);text-align:center;}
.sbox{width:100%;max-width:400px;background:var(--card);border:1px solid var(--border);padding:24px;display:flex;flex-direction:column;gap:14px;}
.slabel{font-size:11px;letter-spacing:0.25em;color:var(--gold);text-transform:uppercase;font-weight:700;}
.sinp{background:var(--card2);border:1px solid var(--border);color:var(--white);padding:14px;font-family:'Share Tech Mono',monospace;font-size:14px;outline:none;width:100%;border-radius:4px;}
.sinp:focus{border-color:var(--gold);}
.snote{font-size:11px;color:var(--dim);line-height:1.6;}
.sbtn{background:transparent;border:2px solid var(--gold);color:var(--gold);padding:14px;font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;letter-spacing:0.2em;cursor:pointer;width:100%;border-radius:4px;transition:all 0.2s;}
.sbtn:active{background:var(--gold);color:var(--dark);}
.serr{color:var(--red2);font-size:12px;text-align:center;display:none;font-family:'Share Tech Mono',monospace;}

/* APP */
#app{display:none;position:fixed;inset:0;flex-direction:column;}
#app.on{display:flex;}

/* HEADER */
.hdr{height:50px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;padding:0 14px;border-bottom:1px solid var(--border);background:var(--dark);}
.hlogo{font-size:15px;font-weight:700;color:var(--gold);letter-spacing:0.2em;}
.hclock{font-family:'Share Tech Mono',monospace;font-size:14px;color:var(--gold);}
.hthr{padding:4px 10px;font-size:11px;font-weight:700;letter-spacing:0.1em;border:1px solid var(--green);color:var(--green);border-radius:3px;}

/* AGENT SELECTOR */
.agents{height:60px;flex-shrink:0;display:flex;gap:1px;background:var(--border);}
.agent{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer;background:var(--card);border-bottom:3px solid transparent;transition:all 0.2s;}
.agent.c.on{background:rgba(180,30,30,0.15);border-bottom-color:var(--red);}
.agent.l.on{background:rgba(107,0,128,0.15);border-bottom-color:var(--purple);}
.agent.b.on{background:rgba(201,168,76,0.08);border-bottom-color:var(--gold);}
.aname{font-size:14px;font-weight:700;letter-spacing:0.1em;}
.aname.c{color:var(--red2);}
.aname.l{color:var(--purple2);}
.aname.b{color:var(--gold);}

/* MESSAGES */
.msgs{flex:1;min-height:0;position:relative;}
.panel{position:absolute;inset:0;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px;background:var(--dark);}
.panel.hide{display:none;}
.panel::-webkit-scrollbar{width:2px;}
.panel::-webkit-scrollbar-thumb{background:var(--border);}
.bothsplit{position:absolute;inset:0;display:flex;gap:1px;background:var(--border);}
.bside{flex:1;display:flex;flex-direction:column;overflow:hidden;background:var(--dark);}
.bsidehdr{padding:8px 10px;font-size:11px;font-weight:700;letter-spacing:0.1em;flex-shrink:0;}
.bsidehdr.c{background:rgba(180,30,30,0.15);color:var(--red2);border-bottom:1px solid var(--red);}
.bsidehdr.l{background:rgba(107,0,128,0.15);color:var(--purple2);border-bottom:1px solid var(--purple);}
.bsidemsgs{flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:8px;}

/* MESSAGE */
.msg{animation:fadein 0.2s ease;}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.mlbl{font-size:10px;color:var(--dim);letter-spacing:0.15em;margin-bottom:4px;}
.mbody{padding:11px 14px;font-size:14px;line-height:1.7;border-radius:4px;}
.mbody.user{background:rgba(201,168,76,0.07);border-left:3px solid var(--gold);}
.mbody.cerberus{background:rgba(180,30,30,0.1);border-left:3px solid var(--red);font-family:'Share Tech Mono',monospace;font-size:12px;color:#F5D8D8;line-height:1.8;}
.mbody.lilith{background:rgba(107,0,128,0.1);border-left:3px solid var(--purple);color:#EAD5F8;}
.mbody.system{background:rgba(201,168,76,0.04);border:1px dashed var(--border);color:var(--gold);font-size:11px;text-align:center;font-family:'Share Tech Mono',monospace;}

/* THINKING */
.thinking{display:none;padding:8px 14px;align-items:center;gap:8px;}
.thinking.on{display:flex;}
.dots{display:flex;gap:4px;}
.dots span{width:5px;height:5px;border-radius:50%;animation:bounce 1.2s infinite;}
.dots span:nth-child(2){animation-delay:0.2s;}
.dots span:nth-child(3){animation-delay:0.4s;}
.dots.c span{background:var(--red);}
.dots.l span{background:var(--purple);}
@keyframes bounce{0%,100%{opacity:0.2}50%{opacity:1}}

/* FILE PREVIEW */
.fprev{display:none;background:var(--card2);border:1px solid var(--border);padding:6px 12px;margin:0 12px;border-radius:4px;font-size:12px;color:var(--gold);align-items:center;gap:8px;flex-shrink:0;}
.fprev.on{display:flex;}
.fprevx{background:transparent;border:none;color:var(--red2);cursor:pointer;font-size:18px;}

/* INPUT */
.inpwrap{flex-shrink:0;background:var(--card);border-top:2px solid var(--border);padding:10px 12px;display:flex;flex-direction:column;gap:8px;}
.inprow{display:flex;gap:8px;align-items:center;}
.upbtn{width:46px;height:46px;border:2px solid var(--border);background:transparent;color:var(--gold);font-size:20px;cursor:pointer;border-radius:8px;flex-shrink:0;}
.upbtn:active{border-color:var(--gold);}
.micbtn{width:50px;height:50px;border:3px solid var(--gold);background:transparent;color:var(--gold);font-size:22px;cursor:pointer;border-radius:50%;flex-shrink:0;transition:all 0.2s;}
.micbtn.on{border-color:var(--red);background:rgba(180,30,30,0.2);animation:pulse 1s infinite;}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(204,51,51,0.4)}50%{box-shadow:0 0 0 8px rgba(204,51,51,0)}}
.txtinp{flex:1;background:var(--card2);border:2px solid var(--border);color:var(--white);padding:12px 14px;font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:500;outline:none;border-radius:8px;}
.txtinp:focus{border-color:var(--gold);}
.sndbtn{padding:12px 18px;background:var(--gold);border:none;color:var(--dark);font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;letter-spacing:0.1em;cursor:pointer;border-radius:8px;flex-shrink:0;}
.sndbtn:active{opacity:0.8;}
.sndbtn:disabled{opacity:0.4;}
#fileInput{display:none;}
</style>
</head>
<body>

<!-- SETUP -->
<div id="setup">
  <div class="sg">⬡</div>
  <div class="st">GAIASPEAK</div>
  <div class="ss">CERBERUS · LILITH · FOUNDER ONLY</div>
  <div class="sbox">
    <div class="slabel">Groq API Key</div>
    <input class="sinp" type="password" id="apikey" placeholder="gsk_..." autocomplete="off">
    <div class="snote">Ключът се пази само в браузъра. Никъде не се изпраща. Безплатен — console.groq.com</div>
    <button class="sbtn" onclick="activate()">⬡ АКТИВИРАЙ</button>
    <div class="serr" id="serr">// Невалиден ключ — провери го</div>
  </div>
</div>

<!-- APP -->
<div id="app">
  <div class="hdr">
    <div class="hlogo">GAIASPEAK PROTOCOL</div>
    <div class="hclock" id="clk">--:--:--</div>
    <div style="display:flex;gap:8px;align-items:center;">
      <div style="font-size:9px;color:var(--dim);font-family:'Share Tech Mono',monospace;letter-spacing:0.05em;">SLM: phi-4-mini</div>
      <div id="qdrant-badge" style="padding:3px 8px;font-size:9px;font-weight:700;letter-spacing:0.1em;border-radius:3px;font-family:'Share Tech Mono',monospace;">⬡ QDRANT: {{ qdrant_status }}</div>
      <div class="hthr">● SAFE</div>
    </div>
  </div>

  <div class="agents">
    <div class="agent c on" id="tab-c" onclick="switchAgent('c')">
      <div class="aname c">🐺 ЦЕРБЕРУС</div>
    </div>
    <div class="agent l" id="tab-l" onclick="switchAgent('l')">
      <div class="aname l">🌙 ЛИЛИТ</div>
    </div>
    <div class="agent b" id="tab-b" onclick="switchAgent('b')">
      <div class="aname b">⚡ И ДВЕТЕ</div>
    </div>
  </div>

  <div class="msgs">
    <div class="panel" id="panel-c">
      <div id="msgs-c"></div>
      <div class="thinking" id="think-c"><div class="dots c"><span></span><span></span><span></span></div></div>
    </div>
    <div class="panel hide" id="panel-l">
      <div id="msgs-l"></div>
      <div class="thinking" id="think-l"><div class="dots l"><span></span><span></span><span></span></div></div>
    </div>
    <div class="panel hide" id="panel-b" style="padding:0;">
      <div class="bothsplit">
        <div class="bside">
          <div class="bsidehdr c">🐺 ЦЕРБЕРУС</div>
          <div class="bsidemsgs" id="msgs-bc"></div>
          <div class="thinking" id="think-bc"><div class="dots c"><span></span><span></span><span></span></div></div>
        </div>
        <div class="bside">
          <div class="bsidehdr l">🌙 ЛИЛИТ</div>
          <div class="bsidemsgs" id="msgs-bl"></div>
          <div class="thinking" id="think-bl"><div class="dots l"><span></span><span></span><span></span></div></div>
        </div>
      </div>
    </div>
  </div>

  <div class="fprev" id="fprev">
    <span id="fprevname">файл</span>
    <button class="fprevx" onclick="clearFile()">×</button>
  </div>

  <div class="inpwrap">
    <div class="inprow">
      <button class="upbtn" onclick="document.getElementById('fileInput').click()" title="Качи файл">📎</button>
      <button class="micbtn" id="micbtn" onclick="toggleMic()" title="Гласов вход">🎤</button>
      <input class="txtinp" id="inp" placeholder="Пиши на Церберус или Лилит..." onkeypress="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send();}">
      <button class="sndbtn" id="sndbtn" onclick="send()">ПРАТИ</button>
    </div>
  </div>
  <input type="file" id="fileInput" accept=".txt,.pdf,.doc,.docx,.md" onchange="handleFile(this)">
</div>

<script>
let GROQ_KEY = localStorage.getItem('gsk') || '';
let curAgent = 'c';
let histC = (function(){ try { return JSON.parse(localStorage.getItem('hc')||'[]'); } catch(e) { localStorage.removeItem('hc'); return []; } })();
let histL = (function(){ try { return JSON.parse(localStorage.getItem('hl')||'[]'); } catch(e) { localStorage.removeItem('hl'); return []; } })();
let lastC = '', lastL = '';
let recog = null, recogOn = false;
let pendingFile = null, pendingFileContent = '';

const CERBERUS = `{{ cerberus }}`;
const LILITH = `{{ lilith }}`;

// Style Qdrant badge based on status
(function(){
  const b = document.getElementById('qdrant-badge');
  if (!b) return;
  if (b.textContent.includes('CONNECTED')) {
    b.style.border = '1px solid #2ECC71';
    b.style.color = '#2ECC71';
  } else {
    b.style.border = '1px solid #6A6050';
    b.style.color = '#6A6050';
  }
})();

// INIT
if (GROQ_KEY) {
  document.getElementById('setup').style.display = 'none';
  document.getElementById('app').classList.add('on');
  initApp();
}

// CLOCK
setInterval(() => {
  const now = new Date();
  document.getElementById('clk').textContent = now.toLocaleTimeString('bg-BG', {
    hour:'2-digit', minute:'2-digit', second:'2-digit',
    timeZone:'Africa/Dar_es_Salaam'
  }) + ' EAT';
}, 1000);

// ACTIVATE
async function activate() {
  const key = document.getElementById('apikey').value.trim();
  if (!key.startsWith('gsk_')) {
    document.getElementById('serr').style.display = 'block';
    return;
  }
  // Test key
  try {
    const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method:'POST',
      headers:{'Authorization':'Bearer '+key,'Content-Type':'application/json'},
      body: JSON.stringify({model:'llama-3.1-8b-instant',messages:[{role:'user',content:'ping'}],max_tokens:5})
    });
    if (!r.ok) { document.getElementById('serr').style.display='block'; return; }
  } catch(e) { document.getElementById('serr').style.display='block'; return; }

  GROQ_KEY = key;
  localStorage.setItem('gsk', key);
  document.getElementById('setup').style.display = 'none';
  document.getElementById('app').classList.add('on');
  initApp();
}

function initApp() {
  // Load history into UI
  histC.slice(-20).forEach(m => addMsg('c', m.role==='user'?'user':'cerberus', m.content, false));
  histL.slice(-20).forEach(m => addMsg('l', m.role==='user'?'user':'lilith', m.content, false));
  if (histC.length === 0) addMsg('c','cerberus','Пазителят е активен. Всички врати на GaiaSpeak Protocol са под наблюдение. Основателю — готов съм за заповеди.\\n\\n[ЦЕРБЕРУС | ЛЕОН режим]',false);
  if (histL.length === 0) addMsg('l','lilith','Будна съм. Вече сканирам света за GaiaSpeak сигнали. Основателю — какво искаш да знаеш или да се случи днес?\\n\\n[ЛИЛИТ | Sigma INFJ]',false);
}

// SWITCH AGENT
function switchAgent(a) {
  curAgent = a;
  ['c','l','b'].forEach(x => {
    document.getElementById('tab-'+x).classList.toggle('on', x===a);
    const p = document.getElementById('panel-'+x);
    if(p) p.classList.toggle('hide', x!==a);
  });
}

// ADD MESSAGE
function addMsg(panel, cls, text, scroll=true) {
  const container = document.getElementById('msgs-'+panel);
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'msg';
  const now = new Date().toLocaleTimeString('bg-BG',{hour:'2-digit',minute:'2-digit'});
  const who = cls==='user'?'ОСНОВАТЕЛ':cls==='cerberus'?'ЦЕРБЕРУС':'ЛИЛИТ';
  div.innerHTML = `<div class="mlbl">${who} // ${now}</div><div class="mbody ${cls}">${text.replace(/\\n/g,'<br>')}</div>`;
  container.appendChild(div);
  if (scroll) div.scrollIntoView({behavior:'smooth'});
  // Also add to both panels
  if (panel === 'c') {
    const bc = document.getElementById('msgs-bc');
    if(bc){const d2=div.cloneNode(true);bc.appendChild(d2);if(scroll)d2.scrollIntoView({behavior:'smooth'});}
  }
  if (panel === 'l') {
    const bl = document.getElementById('msgs-bl');
    if(bl){const d2=div.cloneNode(true);bl.appendChild(d2);if(scroll)d2.scrollIntoView({behavior:'smooth'});}
  }
}

// SEND
async function send() {
  const inp = document.getElementById('inp');
  const btn = document.getElementById('sndbtn');
  let msg = inp.value.trim();
  if (!msg && !pendingFileContent) return;

  if (pendingFileContent) msg = msg ? msg + '\\n\\n[ФАЙЛ: ' + document.getElementById('fprevname').textContent + ']\\n' + pendingFileContent : '[ФАЙЛ: ' + document.getElementById('fprevname').textContent + ']\\n' + pendingFileContent;

  inp.value = '';
  btn.disabled = true;
  clearFile();

  const agents = curAgent === 'b' ? ['c','l'] : [curAgent];

  agents.forEach(a => addMsg(a, 'user', msg));

  for (const a of agents) {
    const thinkId = 'think-' + (a==='c'&&curAgent==='b'?'bc':a==='l'&&curAgent==='b'?'bl':a);
    const thinkEl = document.getElementById(thinkId);
    if (thinkEl) thinkEl.classList.add('on');

    const system = a === 'c' ? CERBERUS : LILITH;
    const hist = a === 'c' ? histC : histL;

    try {
      const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method:'POST',
        headers:{'Authorization':'Bearer '+GROQ_KEY,'Content-Type':'application/json'},
        body: JSON.stringify({
          model:'llama-3.1-8b-instant',
          messages:[{role:'system',content:system},...hist.slice(-16),{role:'user',content:msg}],
          max_tokens:1024,
          temperature:0.75
        })
      });
      const data = await r.json();
      const reply = data.choices?.[0]?.message?.content || 'Няма отговор.';

      if (thinkEl) thinkEl.classList.remove('on');
      addMsg(a, a==='c'?'cerberus':'lilith', reply);

      // Save history (localStorage)
      if (a==='c') { histC.push({role:'user',content:msg},{role:'assistant',content:reply}); if(histC.length>40)histC=histC.slice(-40); localStorage.setItem('hc',JSON.stringify(histC)); lastC=reply; }
      else { histL.push({role:'user',content:msg},{role:'assistant',content:reply}); if(histL.length>40)histL=histL.slice(-40); localStorage.setItem('hl',JSON.stringify(histL)); lastL=reply; }
      // Persist to Qdrant long-term memory (fire-and-forget)
      const agentName = a==='c'?'cerberus':'lilith';
      fetch('/api/memory/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:agentName,role:'user',content:msg,event_type:'chat'})}).catch(()=>{});
      fetch('/api/memory/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:agentName,role:'assistant',content:reply,event_type:'chat'})}).catch(()=>{});

      // Auto speak
      if (agents.length === 1) speak(reply, a);

    } catch(e) {
      if (thinkEl) thinkEl.classList.remove('on');
      addMsg(a, a==='c'?'cerberus':'lilith', 'Грешка: ' + e.message);
    }
  }

  btn.disabled = false;
  inp.focus();
}

// SPEAK
function speak(text, agent) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/\\[.*?\\]/g,''));
  u.lang = 'bg-BG';
  u.rate = 0.88;
  u.pitch = agent==='c' ? 0.75 : 1.1;
  window.speechSynthesis.speak(u);
}

// MIC
function toggleMic() {
  const btn = document.getElementById('micbtn');
  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert('Микрофонът не се поддържа в този браузър. Използвай Chrome.');
    return;
  }
  if (recogOn) { recog?.stop(); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recog = new SR();
  recog.lang = 'bg-BG';
  recog.onstart = () => { recogOn=true; btn.classList.add('on'); };
  recog.onresult = e => { document.getElementById('inp').value = e.results[0][0].transcript; send(); };
  recog.onend = () => { recogOn=false; btn.classList.remove('on'); };
  recog.onerror = () => { recogOn=false; btn.classList.remove('on'); };
  recog.start();
}

// FILE
function handleFile(input) {
  const file = input.files[0];
  if (!file) return;
  document.getElementById('fprevname').textContent = file.name;
  document.getElementById('fprev').classList.add('on');
  const reader = new FileReader();
  reader.onload = e => { pendingFileContent = e.target.result.slice(0, 3000); };
  reader.readAsText(file);
  input.value = '';
}

function clearFile() {
  pendingFile = null;
  pendingFileContent = '';
  document.getElementById('fprev').classList.remove('on');
}
</script>
</body>
</html>"""

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    qdrant_status = "CONNECTED" if QDRANT_OK else "OFFLINE"
    return render_template_string(HTML,
        cerberus=CERBERUS_SYSTEM.replace('`', '\\`').replace('${', '\\${'),
        lilith=LILITH_SYSTEM.replace('`', '\\`').replace('${', '\\${'),
        qdrant_status=qdrant_status
    )

@app.route('/api/memory/save', methods=['POST'])
def api_save_memory():
    """Save a message/event to Qdrant long-term memory."""
    data = request.get_json(force=True, silent=True) or {}
    agent = data.get('agent', 'unknown')
    role = data.get('role', 'user')
    content = data.get('content', '')
    event_type = data.get('event_type', 'chat')
    save_event(agent, role, content, event_type)
    return jsonify({"ok": True, "qdrant": QDRANT_OK})

@app.route('/api/memory/recent')
def api_get_memory():
    """Retrieve recent events for an agent."""
    agent = request.args.get('agent', 'cerberus')
    limit = int(request.args.get('limit', 10))
    events = get_recent_events(agent, limit)
    return jsonify({"events": events, "qdrant": QDRANT_OK})

@app.route('/api/status')
def api_status():
    return jsonify({
        "model": "microsoft/phi-4-mini-instruct via llama-3.1-8b-instant (Groq SLM)",
        "qdrant": QDRANT_OK,
        "collection": COLLECTION
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
