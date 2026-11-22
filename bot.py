import os
import json
import random
import string
import asyncio
import aiohttp
from aiohttp import web
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
# Pon aquí la URL pública que te dé Render (ej. https://onrender.com)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

# ==============================================================================
# SECCIÓN PERSONALIZABLE: AQUÍ PUEDES AGREGAR TUS PROPIAS PALABRAS Y PREFIJOS OG
# ==============================================================================
PALABRAS_OG_CUSTOM = [
    "bond", "king", "dark", "cold", "fire", "soul", "void", "zero", "wolf", "lion",
    "star", "moon", "rain", "wind", "snow", "gold", "jade", "ruby", "onyx", "neon",
    "nova", "apex", "zeno", "echo", "flux", "haze", "mist", "dusk", "dawn", "fury",
    "ghost", "frost", "storm", "blade", "drift", "viper", "venom", "chaos", "night",
    # Agrega tus palabras abajo entre comillas y separadas por coma:
    "vibe", "flow", "rare", "pure", "myth", "rune", "grim", "doom"
]

PREFIJOS_CUSTOM = ["x", "z", "v", "k", "q", "im", "el", "mr", "dr"]
# ==============================================================================

# --- INTERFAZ VISUAL DE LA MINI APP (HTML + CSS + JS) ---
HTML_MINI_APP = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>TG OG Hunter</title>
<script src="https://telegram.org"></script>
<style>
  :root {
    --bg: #0f1115;
    --card: #181b22;
    --accent: #3b82f6;
    --accent-hover: #2563eb;
    --text: #f3f4f6;
    --muted: #9ca3af;
    --green: #10b981;
    --red: #ef4444;
    --yellow: #f59e0b;
  }
  * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); margin: 0; padding: 16px; padding-bottom: 40px; }
  .header { text-align: center; margin-bottom: 18px; }
  .header h1 { font-size: 20px; margin: 0 0 4px 0; letter-spacing: 0.5px; }
  .header p { font-size: 12px; color: var(--muted); margin: 0; }
  
  .tabs { display: flex; gap: 6px; margin-bottom: 16px; background: var(--card); padding: 5px; border-radius: 12px; }
  .tab { flex: 1; padding: 10px 6px; border: none; background: transparent; color: var(--muted); font-weight: 600; font-size: 13px; border-radius: 8px; cursor: pointer; transition: 0.2s; }
  .tab.active { background: var(--accent); color: white; }

  .card { background: var(--card); border-radius: 14px; padding: 14px; margin-bottom: 14px; border: 1px solid #262a34; }
  .row { display: flex; gap: 8px; margin-bottom: 10px; }
  select, input { width: 100%; padding: 11px; border-radius: 10px; border: 1px solid #2e3340; background: #101217; color: white; font-size: 14px; outline: none; }
  
  .btn { width: 100%; padding: 12px; border: none; border-radius: 10px; font-weight: 700; font-size: 14px; cursor: pointer; background: var(--accent); color: white; transition: 0.2s; }
  .btn:active { transform: scale(0.98); }
  .btn-green { background: var(--green); }
  .btn-outline { background: transparent; border: 1px solid #374151; color: var(--text); }

  .user-item { display: flex; justify-content: space-between; align-items: center; padding: 11px 12px; background: #101217; border-radius: 10px; margin-bottom: 8px; border: 1px solid #232732; }
  .user-name { font-family: monospace; font-size: 15px; font-weight: bold; color: #60a5fa; }
  .badge { font-size: 11px; padding: 3px 8px; border-radius: 6px; font-weight: 600; }
  .badge-free { background: rgba(16, 185, 129, 0.15); color: var(--green); }
  .badge-taken { background: rgba(239, 68, 68, 0.15); color: var(--red); }
  .badge-wait { background: rgba(245, 158, 11, 0.15); color: var(--yellow); }

  .actions { display: flex; gap: 6px; align-items: center; }
  .mini-btn { padding: 6px 10px; border-radius: 7px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; background: #262a34; color: white; }
  .section { display: none; }
  .section.active { display: block; }
</style>
</head>
<body>

  <div class="header">
    <h1>⚜️ TG OG USERNAME STUDIO</h1>
    <p>Generador & Verificador t.me en tiempo real</p>
  </div>

  <!-- PESTAÑAS DE NAVEGACIÓN (PUEDES AGREGAR MÁS AQUÍ) -->
  <div class="tabs">
    <button class="tab active" onclick="cambiarTab('gen', this)">🎲 Generador</button>
    <button class="tab" onclick="cambiarTab('check', this)">🔍 Verificar @</button>
    <button class="tab" onclick="cambiarTab('saved', this)">⭐ Guardados (<span id="count-saved">0</span>)</button>
  </div>

  <!-- SECCIÓN 1: GENERADOR + AUTO-CHECKER -->
  <div id="sec-gen" class="section active">
    <div class="card">
      <div class="row">
        <select id="categoria">
          <option value="4l_og">4 Letras OG (ej. bond, kizu)</option>
          <option value="5l_og">5 Letras OG (ej. ghost, viper)</option>
          <option value="5c_mix">5 Caracteres Mix (ej. v1per, x_king)</option>
          <option value="custom_pref">Con tu Prefijo OG (ej. xbond)</option>
        </select>
      </div>
      <div class="row">
        <button class="btn" onclick="generarYVerificar()">⚡ Generar y Verificar (8)</button>
      </div>
    </div>
    <div id="lista-resultados"></div>
  </div>

  <!-- SECCIÓN 2: VERIFICADOR MANUAL DIRECTO -->
  <div id="sec-check" class="section">
    <div class="card">
      <p style="font-size:13px; color:var(--muted); margin-top:0;">Escribe un usuario (mín. 5 letras en TG, o 4L si es Fragment):</p>
      <div class="row">
        <input type="text" id="input-manual" placeholder="Ej: ghost, v1per, king..." maxlength="32">
      </div>
      <button class="btn btn-green" onclick="verificarManual()">Comprobar en t.me</button>
      <div id="res-manual" style="margin-top:14px;"></div>
    </div>
  </div>

  <!-- SECCIÓN 3: FAVORITOS GUARDADOS -->
  <div id="sec-saved" class="section">
    <div class="card">
      <div class="row">
        <button class="btn btn-outline" onclick="copiarTodosGuardados()">📋 Copiar Todos</button>
        <button class="btn btn-outline" style="color:var(--red);" onclick="limpiarGuardados()">🗑️ Borrar</button>
      </div>
    </div>
    <div id="lista-guardados"></div>
  </div>

  <!-- ===================================================================== -->
  <!-- AQUÍ PUEDES AGREGAR TUS PROPIAS SECCIONES EXTRAS (EJ. FRAGMENT / TIPS) -->
  <!-- ===================================================================== -->

<script>
  const tg = window.Telegram.WebApp;
  tg.expand(); // Expande la Mini App a pantalla completa

  let guardados = JSON.parse(localStorage.getItem('og_saved') || '[]');
  actualizarContador();

  function cambiarTab(id, el) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('sec-' + id).classList.add('active');
    if (id === 'saved') renderGuardados();
  }

  async function generarYVerificar() {
    const cat = document.getElementById('categoria').value;
    const cont = document.getElementById('lista-resultados');
    cont.innerHTML = '<p style="text-align:center; color:#9ca3af;">⏳ Consultando t.me...</p>';

    try {
      const resp = await fetch(`/api/generar?cat=${cat}`);
      const data = await resp.json();
      cont.innerHTML = '';

      data.resultados.forEach(item => {
        const badgeClass = item.libre ? 'badge-free' : 'badge-taken';
        const badgeText = item.libre ? 'SIN PERFIL (LIBRE/FRAG)' : 'OCUPADO';
        cont.innerHTML += `
          <div class="user-item">
            <div>
              <div class="user-name">@${item.user}</div>
              <span class="badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="actions">
              <button class="mini-btn" onclick="copiar('${item.user}')">📋</button>
              <button class="mini-btn" onclick="guardar('${item.user}')">⭐</button>
            </div>
          </div>
        `;
      });
    } catch (e) {
      cont.innerHTML = '<p style="color:#ef4444; text-align:center;">Error conectando con el servidor.</p>';
    }
  }

  async function verificarManual() {
    let raw = document.getElementById('input-manual').value.trim().toLowerCase().replace('@', '');
    if (!raw) return;
    const box = document.getElementById('res-manual');
    box.innerHTML = '<p style="color:#9ca3af;">Verificando @' + raw + '...</p>';

    const resp = await fetch(`/api/check?u=${encodeURIComponent(raw)}`);
    const data = await resp.json();
    const badgeClass = data.libre ? 'badge-free' : 'badge-taken';
    const badgeText = data.libre ? '✅ SIN PERFIL PÚBLICO' : '❌ EN USO';

    box.innerHTML = `
      <div class="user-item">
        <div>
          <div class="user-name">@${data.user}</div>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="actions">
          <button class="mini-btn" onclick="copiar('${data.user}')">Copiar</button>
          <button class="mini-btn" onclick="guardar('${data.user}')">⭐</button>
        </div>
      </div>
    `;
  }

  function copiar(texto) {
    navigator.clipboard.writeText('@' + texto);
    tg.HapticFeedback.impactOccurred('light');
    tg.showAlert('Copiado: @' + texto);
  }

  function guardar(user) {
    if (!guardados.includes(user)) {
      guardados.push(user);
      localStorage.setItem('og_saved', JSON.stringify(guardados));
      actualizarContador();
      tg.HapticFeedback.notificationOccurred('success');
    }
  }

  function actualizarContador() {
  
APP ---

async def ruta_webapp(request):
return web.Response(text=HTML_MINI_APP, content_type="text/html")
async def ruta_api_check(request):
user = request.query.get("u", "").strip().lower()
if not user:
return web.json_response({"error": "vacio"}, status=400)
async with aiohttp.ClientSession() as session:
libre = await check_tme_disponible(session, user)
return web.json_response({"user": user, "libre": libre})
async def ruta_api_generar(request):
cat = request.query.get("cat", "5l_og")
candidatos = list({crear_candidato(cat) for _ in range(12)})[:8]
resultados = []
async with aiohttp.ClientSession() as session:
tareas = [check_tme_disponible(session, u) for u in candidatos]
estados = await asyncio.gather(*tareas)
for u, libre in zip(candidatos, estados):
resultados.append({"user": u, "libre": libre})
return web.json_response({"resultados": resultados})

--- COMANDO DEL BOT DE TELEGRAM ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not WEBAPP_URL:
await update.message.reply_text(
"⚠️ Falta configurar la variable WEBAPP_URL en Render con tu enlace .onrender.com.",
parse_mode="Markdown"
)
return
teclado = InlineKeyboardMarkup([
[InlineKeyboardButton("🚀 Abrir Mini App OG Hunter", web_app=WebAppInfo(url=WEBAPP_URL))]
])
await update.message.reply_text(
"⚜️ TG OG USERNAME STUDIO ⚜️\n\n"
"Toca el botón de abajo para abrir tu Mini App interactiva:",
reply_markup=teclado,
parse_mode="Markdown"
)
async def iniciar_todo():
web_app = web.Application()
web_app.router.add_get("/", ruta_webapp)
web_app.router.add_get("/api/check", ruta_api_check)
web_app.router.add_get("/api/generar", ruta_api_generar)
runner = web.AppRunner(web_app)
await runner.setup()
port = int(os.environ.get("PORT", 10000))
site = web.TCPSite(runner, "0.0.0.0", port)
await site.start()
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", cmd_start))
await app.initialize()
await app.start()
await app.updater.start_polling()
print(f"Mini App y Bot activos en puerto {port}...")
await asyncio.Event().wait()
if name == 'main':
asyncio.run(iniciar_todo())
