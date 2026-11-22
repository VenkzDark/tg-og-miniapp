import os
import random
import string
import asyncio
import aiohttp
from aiohttp import web
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

PALABRAS_OG_CUSTOM = [
    "bond", "king", "dark", "cold", "fire", "soul", "void", "zero", "wolf", "lion",
    "star", "moon", "rain", "wind", "snow", "gold", "jade", "ruby", "onyx", "neon",
    "nova", "apex", "zeno", "echo", "flux", "haze", "mist", "dusk", "dawn", "fury",
    "ghost", "frost", "storm", "blade", "drift", "viper", "venom", "chaos", "night",
    "vibe", "flow", "rare", "pure", "myth", "rune", "grim", "doom"
]

PREFIJOS_CUSTOM = ["x", "z", "v", "k", "q", "im", "el", "mr", "dr"]

def crear_candidato(cat: str) -> str:
    vocales = "aeiou"
    consonantes = "bcdfghjklmnprstvz"
    if cat == "4l_og":
        palabras_4 = [p for p in PALABRAS_OG_CUSTOM if len(p) == 4]
        if palabras_4 and random.random() < 0.4:
            return random.choice(palabras_4)
        return random.choice(consonantes) + random.choice(vocales) + random.choice(consonantes) + random.choice(vocales)
    elif cat == "5c_mix":
        base = list(random.choice([p for p in PALABRAS_OG_CUSTOM if len(p) == 5] or ["ghost"]))
        reemp = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5'}
        idx = random.randint(0, 4)
        if base[idx] in reemp:
            base[idx] = reemp[base[idx]]
        else:
            base[idx] = random.choice(string.digits + "_")
        return "".join(base).strip("_")
    elif cat == "custom_pref":
        pref = random.choice(PREFIJOS_CUSTOM)
        base = random.choice(PALABRAS_OG_CUSTOM)
        return (pref + base)[:8]
    else:
        palabras_5 = [p for p in PALABRAS_OG_CUSTOM if len(p) == 5]
        if palabras_5 and random.random() < 0.45:
            return random.choice(palabras_5)
        return (
            random.choice(consonantes) + random.choice(vocales) +
            random.choice(consonantes) + random.choice(vocales) + random.choice(consonantes)
        )

async def check_tme_disponible(session: aiohttp.ClientSession, username: str) -> bool:
    url = "https://t.me" + "/" + username
    try:
        async with session.get(url, timeout=6) as resp:
            html = await resp.text()
            if 'tgme_page_title' in html:
                return False
            return True
    except Exception:
        return False

async def ruta_webapp(request):
    return web.FileResponse("index.html")

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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not WEBAPP_URL:
        await update.message.reply_text("⚠️ Falta configurar `WEBAPP_URL` en Render.", parse_mode="Markdown")
        return

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Abrir Mini App OG Hunter", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text(
        "⚜️ **TG OG USERNAME STUDIO** ⚜️\n\nToca el botón de abajo para abrir tu Mini App:",
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

if __name__ == '__main__':
    asyncio.run(iniciar_todo())
    
