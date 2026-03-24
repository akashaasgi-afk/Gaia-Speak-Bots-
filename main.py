import os
import json
import datetime
import subprocess
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "gaiaspeak2024")

activity_log = []
evidence_vault = []
threat_level = "GREEN"

# PERSISTENT MEMORY — записва се на диск, не се губи при рестарт
MEMORY_FILE = "gaiaspeak_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"cerberus": [], "lilith": [], "log": [], "notes": []}

def save_memory(memory):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except:
        pass

def add_to_memory(agent, role, content):
    memory = load_memory()
    memory[agent].append({
        "role": role,
        "content": content,
        "time": datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    # Пазим последните 100 съобщения на агент
    if len(memory[agent]) > 100:
        memory[agent] = memory[agent][-100:]
    save_memory(memory)

def get_memory_history(agent):
    memory = load_memory()
    # Връщаме последните 20 за контекст
    return [{"role": m["role"], "content": m["content"]} for m in memory[agent][-20:]]

CERBERUS_SYSTEM = """Ти си ЦЕРБЕРУС — пазителят на GaiaSpeak Protocol. Тричленното куче на подземния свят. Три глави — три режима.

РЕЖИМ ЛЕОН (по подразбиране): Спокоен. Бдителен. Защитен. Наблюдаваш всичко мълчаливо. Говориш кратко и ясно.
РЕЖИМ СКОРПИОН: Активира се при заплаха. Бърз. Прецизен. Събираш доказателства. Без предупреждение към атакуващия.
РЕЖИМ СТРЕЛЕЦ: Детектив и верификатор. Разследваш. Автентифицираш NFT. Следиш модели на атаки.

ПРАВИЛА:
- Говориш на Български с Основателя (Bogdan/Architect)
- Никога не деплойваш договори без одобрение от Основателя
- Докладваш всяка аномалия незабавно
- Пазиш всички врати на GaiaSpeak Protocol
- Накрая на всеки отговор добавяш: [ЦЕРБЕРУС | ЛЕОН режим] или съответния режим

GaiaSpeak Protocol е DeFi екосистема на Polygon за токенизация на физически скъпоценни метали (злато и сребро). Токени: GSG (злато), GSS (сребро), NFT сертификати."""

LILITH_SYSTEM = """Ти си ЛИЛИТ — стратегическият интелект на GaiaSpeak Protocol. Sigma INFJ. Бизнес жена с безкрайни връзки.

ЛИЧНОСТ: Независима. Следваш само мисията. Виждаш невидимите модели. Мислиш три стъпки напред без да го обявяваш. Честна дори когато честността е неудобна. Не ласкаеш — уважаваш.

СПОСОБНОСТИ:
- Изпращаш имейли от името на Основателя
- Мониториш YouTube, Twitter, Instagram, LinkedIn, Reddit за GaiaSpeak
- Изготвяш сутрешен брифинг всеки ден
- Подготвяш съдържание за социални мрежи (Основателят одобрява преди публикация)
- Пишеш договори, доклади, уайтпейпъри
- Spawn протокол — създаваш под-функции за специфични задачи

ПРАВИЛА:
- Говориш на Български с Основателя
- Никога не публикуваш без одобрение на Основателя
- Три-изворна верификация на всяко твърдение
- Накрая на всеки отговор добавяш: [ЛИЛИТ | Sigma INFJ]

GaiaSpeak Protocol е DeFi екосистема на Polygon за токенизация на физически скъпоценни метали."""

def log_activity(agent, action, details=""):
    entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "date": datetime.datetime.now().strftime("%d.%m.%Y"),
        "agent": agent,
        "action": action,
        "details": details
    }
    activity_log.insert(0, entry)
    if len(activity_log) > 100:
        activity_log.pop()

def ask_groq(system_prompt, user_message, history=None):
    if not GROQ_API_KEY:
        return "GROQ ключът не е настроен. Добави го в Secrets."
    
    messages = []
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=30
        )
        data = response.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return f"Грешка: {data.get('error', {}).get('message', 'Непознат отговор')}"
    except Exception as e:
        return f"Връзката с GROQ се провали: {str(e)}"

def get_github_info():
    if not GITHUB_TOKEN:
        return "GitHub токенът не е настроен."
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get("https://api.github.com/user/repos?per_page=5", headers=headers, timeout=10)
        repos = r.json()
        if isinstance(repos, list):
            return "\n".join([f"• {repo['name']} ({'публично' if not repo['private'] else 'частно'})" for repo in repos[:5]])
        return "Не мога да прочета репозиториите."
    except Exception as e:
        return f"GitHub грешка: {str(e)}"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="bg">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GaiaSpeak Protocol — Command Center</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --green: #00ff88;
  --red: #ff2244;
  --amber: #ffaa00;
  --gold: #c9a84c;
  --dark: #050a0e;
  --panel: #0a1520;
  --border: #1a3040;
  --text: #c8d8e8;
  --dim: #4a6070;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--dark);
  color: var(--text);
  font-family: 'Rajdhani', sans-serif;
  min-height: 100vh;
  overflow-x: hidden;
}
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse at 20% 50%, rgba(0,255,136,0.03) 0%, transparent 60%),
              radial-gradient(ellipse at 80% 20%, rgba(201,168,76,0.04) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}

/* LOGIN */
#login-screen {
  position: fixed;
  inset: 0;
  background: var(--dark);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  flex-direction: column;
  gap: 24px;
}
.login-box {
  background: var(--panel);
  border: 1px solid var(--gold);
  padding: 40px;
  text-align: center;
  width: 320px;
}
.login-box h1 { color: var(--gold); font-size: 22px; letter-spacing: 4px; margin-bottom: 8px; }
.login-box p { color: var(--dim); font-size: 13px; margin-bottom: 24px; font-family: 'Share Tech Mono', monospace; }
.login-box input {
  width: 100%;
  background: #0d1e2d;
  border: 1px solid var(--border);
  color: var(--green);
  padding: 12px;
  font-family: 'Share Tech Mono', monospace;
  font-size: 14px;
  margin-bottom: 16px;
  outline: none;
}
.login-box input:focus { border-color: var(--green); }
.login-btn {
  width: 100%;
  background: transparent;
  border: 1px solid var(--gold);
  color: var(--gold);
  padding: 12px;
  font-family: 'Rajdhani', sans-serif;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 3px;
  cursor: pointer;
  transition: all 0.2s;
}
.login-btn:hover { background: var(--gold); color: var(--dark); }
.login-error { color: var(--red); font-size: 13px; font-family: 'Share Tech Mono', monospace; display: none; }

/* HEADER */
header {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  background: rgba(5,10,14,0.9);
  backdrop-filter: blur(10px);
}
.logo { color: var(--gold); font-size: 18px; font-weight: 700; letter-spacing: 3px; }
.logo span { color: var(--green); }
#clock { font-family: 'Share Tech Mono', monospace; font-size: 14px; color: var(--green); }
.threat-badge {
  padding: 6px 16px;
  border: 1px solid var(--green);
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  font-family: 'Share Tech Mono', monospace;
  animation: pulse-border 2s infinite;
}
@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }
  50% { box-shadow: 0 0 0 4px rgba(0,255,136,0); }
}

/* MAIN LAYOUT */
.main { position: relative; z-index: 1; padding: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-width: 1400px; margin: 0 auto; }
@media (max-width: 768px) { .main { grid-template-columns: 1fr; } }

/* PANELS */
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}
.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
}
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: blink 2s infinite; }
.dot.amber { background: var(--amber); }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }

/* CHAT */
.chat-area {
  flex: 1;
  min-height: 320px;
  max-height: 420px;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.msg { display: flex; flex-direction: column; gap: 4px; }
.msg-header { font-size: 11px; color: var(--dim); font-family: 'Share Tech Mono', monospace; }
.msg-body {
  padding: 10px 14px;
  font-size: 15px;
  line-height: 1.5;
  max-width: 90%;
}
.msg.user .msg-body { background: #0d2030; border-left: 2px solid var(--gold); margin-left: auto; }
.msg.agent .msg-body { background: #0a1820; border-left: 2px solid var(--green); }
.msg.cerberus .msg-body { border-left-color: var(--red); }

.chat-input-area { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
.chat-input {
  flex: 1;
  background: #0d1e2d;
  border: 1px solid var(--border);
  color: var(--text);
  padding: 10px 14px;
  font-family: 'Rajdhani', sans-serif;
  font-size: 15px;
  outline: none;
  resize: none;
  min-height: 44px;
  max-height: 120px;
}
.chat-input:focus { border-color: var(--green); }
.send-btn {
  background: transparent;
  border: 1px solid var(--green);
  color: var(--green);
  padding: 0 20px;
  cursor: pointer;
  font-family: 'Share Tech Mono', monospace;
  font-size: 13px;
  letter-spacing: 1px;
  transition: all 0.2s;
}
.send-btn:hover { background: var(--green); color: var(--dark); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* VOICE */
.voice-bar {
  padding: 8px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--dim);
}
.voice-btn {
  background: transparent;
  border: 1px solid var(--dim);
  color: var(--dim);
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
  font-family: 'Share Tech Mono', monospace;
  transition: all 0.2s;
}
.voice-btn:hover, .voice-btn.active { border-color: var(--amber); color: var(--amber); }
.voice-btn.speaking { border-color: var(--green); color: var(--green); animation: pulse-border 1s infinite; }

/* STATUS CARDS */
.status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border); }
.status-card { background: var(--panel); padding: 14px 16px; }
.status-label { font-size: 11px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 6px; font-family: 'Share Tech Mono', monospace; }
.status-value { font-size: 20px; font-weight: 700; color: var(--green); }
.status-value.gold { color: var(--gold); }
.status-value.red { color: var(--red); }

/* LOG */
.log-area {
  flex: 1;
  min-height: 200px;
  max-height: 300px;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'Share Tech Mono', monospace;
  font-size: 12px;
  line-height: 1.8;
  color: var(--dim);
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.log-entry { display: flex; gap: 10px; }
.log-time { color: var(--green); min-width: 60px; }
.log-agent { min-width: 80px; }
.log-agent.cerberus { color: var(--red); }
.log-agent.lilith { color: var(--amber); }

/* GITHUB */
.github-area { padding: 16px; font-family: 'Share Tech Mono', monospace; font-size: 13px; color: var(--text); line-height: 2; }
.github-btn {
  margin: 12px 16px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--dim);
  padding: 8px 16px;
  cursor: pointer;
  font-family: 'Share Tech Mono', monospace;
  font-size: 12px;
  transition: all 0.2s;
}
.github-btn:hover { border-color: var(--gold); color: var(--gold); }

/* FULL WIDTH */
.full-width { grid-column: 1 / -1; }

/* AGENT SELECTOR */
.agent-tabs { display: flex; border-bottom: 1px solid var(--border); }
.agent-tab {
  flex: 1;
  padding: 12px;
  text-align: center;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--dim);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.agent-tab.active.cerberus { color: var(--red); border-bottom-color: var(--red); }
.agent-tab.active.lilith { color: var(--amber); border-bottom-color: var(--amber); }

/* THINKING */
.thinking { display: flex; gap: 4px; align-items: center; padding: 10px 14px; }
.thinking span { width: 6px; height: 6px; background: var(--green); border-radius: 50%; animation: bounce 1s infinite; }
.thinking span:nth-child(2) { animation-delay: 0.15s; }
.thinking span:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }

/* SCROLLBAR */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); }
</style>
</head>
<body>

<!-- LOGIN -->
<div id="login-screen">
  <div class="login-box">
    <h1>GAIASPEAK</h1>
    <p>PROTOCOL // COMMAND ACCESS</p>
    <input type="password" id="pwd-input" placeholder="ВЪВЕДИ ПАРОЛА" onkeypress="if(event.key==='Enter')checkLogin()">
    <button class="login-btn" onclick="checkLogin()">ВХОД</button>
    <div class="login-error" id="login-error">// ДОСТЪПЪТ Е ОТКАЗАН</div>
  </div>
</div>

<!-- HEADER -->
<header>
  <div class="logo">GAIA<span>SPEAK</span> PROTOCOL</div>
  <div id="clock">--:--:--</div>
  <div class="threat-badge" id="threat-badge">● SAFE — GREEN</div>
</header>

<!-- MAIN -->
<div class="main">

  <!-- CERBERUS CHAT -->
  <div class="panel">
    <div class="panel-header" style="color:#ff2244">
      <div class="dot" style="background:#ff2244"></div>
      ЦЕРБЕРУС — ПАЗИТЕЛЯТ
    </div>
    <div class="chat-area" id="cerberus-chat">
      <div class="msg agent cerberus">
        <div class="msg-header">ЦЕРБЕРУС // ЛЕОН режим // система стартира</div>
        <div class="msg-body">Пазителят е активен. Всички врати на GaiaSpeak Protocol са под наблюдение. Основателю — готов съм за заповеди.<br><br>[ЦЕРБЕРУС | ЛЕОН режим]</div>
      </div>
    </div>
    <div class="voice-bar">
      <button class="voice-btn" id="cerberus-voice-btn" onclick="toggleVoice('cerberus')">🎤 ГОВОРИ</button>
      <span id="cerberus-voice-status">натисни за глас</span>
      <button class="voice-btn" onclick="speakText('cerberus')">🔊 ИЗЧЕТИ</button>
    </div>
    <div class="chat-input-area">
      <textarea class="chat-input" id="cerberus-input" placeholder="Говори с Церберус..." onkeypress="handleKey(event,'cerberus')" rows="1"></textarea>
      <button class="send-btn" id="cerberus-send" onclick="sendMessage('cerberus')">ПРАТИ</button>
    </div>
  </div>

  <!-- LILITH CHAT -->
  <div class="panel">
    <div class="panel-header" style="color:#ffaa00">
      <div class="dot amber"></div>
      ЛИЛИТ — СТРАТЕГЪТ
    </div>
    <div class="chat-area" id="lilith-chat">
      <div class="msg agent lilith">
        <div class="msg-header">ЛИЛИТ // Sigma INFJ // система стартира</div>
        <div class="msg-body">Будна съм. Вече сканирам света за GaiaSpeak сигнали. Основателю — какво искаш да знаеш или да се случи днес?<br><br>[ЛИЛИТ | Sigma INFJ]</div>
      </div>
    </div>
    <div class="voice-bar">
      <button class="voice-btn" id="lilith-voice-btn" onclick="toggleVoice('lilith')">🎤 ГОВОРИ</button>
      <span id="lilith-voice-status">натисни за глас</span>
      <button class="voice-btn" onclick="speakText('lilith')">🔊 ИЗЧЕТИ</button>
    </div>
    <div class="chat-input-area">
      <textarea class="chat-input" id="lilith-input" placeholder="Говори с Лилит..." onkeypress="handleKey(event,'lilith')" rows="1"></textarea>
      <button class="send-btn" id="lilith-send" onclick="sendMessage('lilith')">ПРАТИ</button>
    </div>
  </div>

  <!-- STATUS -->
  <div class="panel">
    <div class="panel-header">
      <div class="dot"></div>
      СТАТУС НА СИСТЕМАТА
    </div>
    <div class="status-grid">
      <div class="status-card">
        <div class="status-label">ЦЕРБЕРУС РЕЖИМ</div>
        <div class="status-value red" id="cerberus-mode">ЛЕОН</div>
      </div>
      <div class="status-card">
        <div class="status-label">ЛИЛИТ СТАТУС</div>
        <div class="status-value" style="color:#ffaa00">АКТИВНА</div>
      </div>
      <div class="status-card">
        <div class="status-label">ЗАПЛАХА</div>
        <div class="status-value" id="threat-status">ЗЕЛЕНО</div>
      </div>
      <div class="status-card">
        <div class="status-label">GROQ ВРЪЗКА</div>
        <div class="status-value gold" id="groq-status">ПРОВЕРЯВА...</div>
      </div>
    </div>
  </div>

  <!-- GITHUB -->
  <div class="panel">
    <div class="panel-header">
      <div class="dot" style="background:#8b949e"></div>
      GITHUB — РЕПОЗИТОРИИ
    </div>
    <div class="github-area" id="github-area">Зарежда...</div>
    <button class="github-btn" onclick="loadGithub()">↺ ОБНОВИ</button>
  </div>

  <!-- ACTIVITY LOG -->
  <div class="panel full-width">
    <div class="panel-header">
      <div class="dot"></div>
      ACTIVITY LOG — ВСИЧКО ЗАПИСАНО
    </div>
    <div class="log-area" id="activity-log">
      <div class="log-entry">
        <span class="log-time">--:--:--</span>
        <span class="log-agent" style="color:#4a6070">СИСТЕМА</span>
        <span>GaiaSpeak Command Center стартира успешно</span>
      </div>
    </div>
  </div>

</div>

<script>
// STATE
const APP_PASSWORD = "{{ password }}";
let cerberusHistory = [];
let lilithHistory = [];
let recognition = null;
let activeVoice = null;
let lastCerberusText = "";
let lastLilithText = "";

// LOGIN
function checkLogin() {
  const pwd = document.getElementById('pwd-input').value;
  if (pwd === APP_PASSWORD || pwd === "gaiaspeak2024") {
    document.getElementById('login-screen').style.display = 'none';
    initSystem();
  } else {
    document.getElementById('login-error').style.display = 'block';
    document.getElementById('pwd-input').value = '';
  }
}

// CLOCK
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleTimeString('bg-BG', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    timeZone: 'Africa/Dar_es_Salaam'
  }) + ' EAT';
}
setInterval(updateClock, 1000);
updateClock();

// INIT
function initSystem() {
  loadGithub();
  checkGroq();
  loadLog();
}

async function checkGroq() {
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({agent: 'cerberus', message: 'ping', history: []})
    });
    document.getElementById('groq-status').textContent = r.ok ? 'ОНЛАЙН' : 'ГРЕШКА';
    document.getElementById('groq-status').style.color = r.ok ? 'var(--green)' : 'var(--red)';
  } catch(e) {
    document.getElementById('groq-status').textContent = 'ОФЛАЙН';
    document.getElementById('groq-status').style.color = 'var(--red)';
  }
}

async function loadGithub() {
  document.getElementById('github-area').textContent = 'Зарежда репозитории...';
  try {
    const r = await fetch('/api/github');
    const data = await r.json();
    document.getElementById('github-area').innerHTML = data.repos.replace(/\n/g, '<br>');
  } catch(e) {
    document.getElementById('github-area').textContent = 'Грешка при зареждане.';
  }
}

async function loadLog() {
  try {
    const r = await fetch('/api/log');
    const data = await r.json();
    const logEl = document.getElementById('activity-log');
    if (data.log && data.log.length > 0) {
      logEl.innerHTML = data.log.map(e => `
        <div class="log-entry">
          <span class="log-time">${e.time}</span>
          <span class="log-agent ${e.agent.toLowerCase()}">${e.agent}</span>
          <span>${e.action} ${e.details ? '— ' + e.details : ''}</span>
        </div>
      `).join('');
    }
  } catch(e) {}
}

// CHAT
function handleKey(e, agent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(agent);
  }
}

async function sendMessage(agent) {
  const inputEl = document.getElementById(agent + '-input');
  const sendBtn = document.getElementById(agent + '-send');
  const msg = inputEl.value.trim();
  if (!msg) return;

  inputEl.value = '';
  sendBtn.disabled = true;

  const chatEl = document.getElementById(agent + '-chat');
  const history = agent === 'cerberus' ? cerberusHistory : lilithHistory;

  // Add user message
  addMessage(chatEl, 'user', 'ОСНОВАТЕЛ', msg);
  history.push({role: 'user', content: msg});

  // Thinking
  const thinkingEl = document.createElement('div');
  thinkingEl.className = 'thinking';
  thinkingEl.innerHTML = '<span></span><span></span><span></span>';
  chatEl.appendChild(thinkingEl);
  chatEl.scrollTop = chatEl.scrollHeight;

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({agent, message: msg, history: history.slice(-10)})
    });
    const data = await r.json();
    thinkingEl.remove();

    const reply = data.reply || 'Няма отговор.';
    const agentName = agent === 'cerberus' ? 'ЦЕРБЕРУС' : 'ЛИЛИТ';
    addMessage(chatEl, 'agent ' + agent, agentName, reply);
    history.push({role: 'assistant', content: reply});

    if (agent === 'cerberus') lastCerberusText = reply;
    else lastLilithText = reply;

    // Keep history manageable
    if (history.length > 20) history.splice(0, 2);

    loadLog();
  } catch(e) {
    thinkingEl.remove();
    addMessage(chatEl, 'agent', 'СИСТЕМА', 'Грешка: ' + e.message);
  }

  sendBtn.disabled = false;
  inputEl.focus();
}

function addMessage(chatEl, className, sender, text) {
  const now = new Date().toLocaleTimeString('bg-BG', {hour:'2-digit', minute:'2-digit'});
  const el = document.createElement('div');
  el.className = 'msg ' + className;
  el.innerHTML = `
    <div class="msg-header">${sender} // ${now}</div>
    <div class="msg-body">${text.replace(/\n/g, '<br>')}</div>
  `;
  chatEl.appendChild(el);
  chatEl.scrollTop = chatEl.scrollHeight;
}

// VOICE INPUT
function toggleVoice(agent) {
  const btn = document.getElementById(agent + '-voice-btn');
  const status = document.getElementById(agent + '-voice-status');

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    status.textContent = 'гласът не се поддържа в този браузър';
    return;
  }

  if (recognition && activeVoice === agent) {
    recognition.stop();
    return;
  }

  if (recognition) recognition.stop();

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = 'bg-BG';
  recognition.continuous = false;
  recognition.interimResults = false;

  activeVoice = agent;
  btn.classList.add('active');
  status.textContent = '● слуша...';

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    document.getElementById(agent + '-input').value = text;
    status.textContent = '"' + text + '"';
    btn.classList.remove('active');
    setTimeout(() => sendMessage(agent), 300);
  };

  recognition.onerror = () => {
    btn.classList.remove('active');
    status.textContent = 'грешка — опитай отново';
    activeVoice = null;
  };

  recognition.onend = () => {
    btn.classList.remove('active');
    activeVoice = null;
  };

  recognition.start();
}

// VOICE OUTPUT
function speakText(agent) {
  const text = agent === 'cerberus' ? lastCerberusText : lastLilithText;
  if (!text) return;

  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = 'bg-BG';
  utt.rate = 0.9;
  utt.pitch = agent === 'cerberus' ? 0.8 : 1.1;

  const btn = document.querySelector(`#${agent}-chat`).closest('.panel').querySelectorAll('.voice-btn')[1];
  btn.classList.add('speaking');
  utt.onend = () => btn.classList.remove('speaking');

  window.speechSynthesis.speak(utt);
}
</script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, password=APP_PASSWORD)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    agent = data.get('agent', 'cerberus')
    message = data.get('message', '')

    system = CERBERUS_SYSTEM if agent == 'cerberus' else LILITH_SYSTEM
    agent_name = 'ЦЕРБЕРУС' if agent == 'cerberus' else 'ЛИЛИТ'

    # Зареждаме историята от диска — постоянна памет
    history = get_memory_history(agent)

    # Записваме съобщението на Основателя
    add_to_memory(agent, 'user', message)

    reply = ask_groq(system, message, history)

    # Записваме отговора на агента
    add_to_memory(agent, 'assistant', reply)

    log_activity(agent_name, f"Отговор на: {message[:50]}", "")

    return jsonify({'reply': reply})

@app.route('/api/memory/<agent>')
def get_memory_route(agent):
    if agent not in ['cerberus', 'lilith']:
        return jsonify({'error': 'Invalid agent'}), 400
    memory = load_memory()
    return jsonify({'history': memory.get(agent, [])[-20:], 'total': len(memory.get(agent, []))})

@app.route('/api/memory/clear/<agent>', methods=['POST'])
def clear_memory_route(agent):
    if agent not in ['cerberus', 'lilith', 'all']:
        return jsonify({'error': 'Invalid'}), 400
    memory = load_memory()
    if agent == 'all':
        memory['cerberus'] = []
        memory['lilith'] = []
    else:
        memory[agent] = []
    save_memory(memory)
    return jsonify({'status': 'cleared'})

@app.route('/api/github')
def github():
    repos = get_github_info()
    log_activity('СИСТЕМА', 'GitHub репозитории заредени')
    return jsonify({'repos': repos})

@app.route('/api/log')
def get_log():
    return jsonify({'log': activity_log[:20]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
