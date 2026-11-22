import os
import io
import random
import string
import asyncio
import aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
CANAL_ID = os.environ.get("CANAL_ID", "")

admins = {OWNER_ID}
usuarios_autorizados = {OWNER_ID}
solicitudes_pendientes = {}

busquedas_activas = {}
estadisticas = {}
encontrados_lista = []
ultimo_detalle = "Sin iniciar"

# ==============================================================================
# SECCIÓN PERSONALIZABLE: AGREGA AQUÍ TUS PALABRAS Y PREFIJOS OG FAVORITOS
# ==============================================================================
PALABRAS_OG_CUSTOM = [
    "bond", "king", "dark", "cold", "fire", "soul", "void", "zero", "wolf", "lion",
    "star", "moon", "rain", "wind", "snow", "gold", "jade", "ruby", "onyx", "neon",
    "nova", "apex", "zeno", "echo", "flux", "haze", "mist", "dusk", "dawn", "fury",
    "ghost", "frost", "storm", "blade", "drift", "viper", "venom", "chaos", "night",
    "vibe", "flow", "rare", "pure", "myth", "rune", "grim", "doom", "prime", "elite"
]

PREFIJOS_CUSTOM = ["x", "z", "v", "k", "q", "im", "el", "mr", "dr"]
# ==============================================================================

def crear_candidato(modo: str) -> str:
    vocales = "aeiou"
    consonantes = "bcdfghjklmnprstvz"
    if modo == "4l":
        palabras_4 = [p for p in PALABRAS_OG_CUSTOM if len(p) == 4]
        if palabras_4 and random.random() < 0.4:
            return random.choice(palabras_4)
        return random.choice(consonantes) + random.choice(vocales) + random.choice(consonantes) + random.choice(vocales)
    elif modo == "5c":
        base = list(random.choice([p for p in PALABRAS_OG_CUSTOM if len(p) == 5] or ["ghost"]))
        reemp = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5'}
        idx = random.randint(0, 4)
        if base[idx] in reemp:
            base[idx] = reemp[base[idx]]
        else:
            base[idx] = random.choice(string.digits + "_")
        return "".join(base).strip("_")
    elif modo == "pref":
        pref = random.choice(PREFIJOS_CUSTOM)
        base = random.choice(PALABRAS_OG_CUSTOM)
        res = (pref + base)[:8]
        return res if len(res) >= 5 else res + random.choice(consonantes)
    else:  # 5l OG (mínimo 5 letras para registro normal en Telegram)
        palabras_5 = [p for p in PALABRAS_OG_CUSTOM if len(p) == 5]
        if palabras_5 and random.random() < 0.45:
            return random.choice(palabras_5)
        return (
            random.choice(consonantes) + random.choice(vocales) +
            random.choice(consonantes) + random.choice(vocales) + random.choice(consonantes)
        )

async def verificar_telegram(session, username):
    """Consulta t.me/usuario para ver si no tiene perfil/canal público activo."""
    global ultimo_detalle
    url = "https://t.me" + "/" + username
    try:
        async with session.get(url, timeout=7) as resp:
            if resp.status == 429:
                ultimo_detalle = "429 (Rate Limit - Pausa)"
                return "RATE_LIMIT"
            html = await resp.text()
            if 'tgme_page_title' in html:
                ultimo_detalle = f"Ocupado (@{username})"
                return False
            ultimo_detalle = f"Sin perfil (@{username})"
            return True
    except Exception as e:
        ultimo_detalle = f"Error red: {str(e)[:40]}"
        return "ERROR"

async def bucle_automatico(chat_id: int, app, modo: str):
    estadisticas[chat_id] = {"revisados": 0, "ok": 0, "libres": 0, "error": 0, "rate_limit": 0}
    
    async with aiohttp.ClientSession() as session:
        while busquedas_activas.get(chat_id, False):
            lote = [crear_candidato(modo) for _ in range(3)]
            tareas = [verificar_telegram(session, u) for u in lote]
            resultados = await asyncio.gather(*tareas)

            for user, estado in zip(lote, resultados):
                estadisticas[chat_id]["revisados"] += 1
                
                if estado is True:
                    estadisticas[chat_id]["ok"] += 1
                    estadisticas[chat_id]["libres"] += 1
                    
                    if user not in encontrados_lista:
                        encontrados_lista.append(user)

                    nota = "_(4L requiere Fragment)_" if len(user) == 4 else "_(5+ caracteres)_"
                    mensaje_hit = (
                        f"⚜️ **USUARIO OG SIN PERFIL EN TG** {nota}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 **Usuario:** `@{user}`\n"
                        f"🔗 **Enlace:** `t.me/{user}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━"
                    )
                    await app.bot.send_message(chat_id=chat_id, text=mensaje_hit, parse_mode="Markdown")

                    if CANAL_ID:
                        try:
                            await app.bot.send_message(chat_id=CANAL_ID, text=mensaje_hit, parse_mode="Markdown")
                        except Exception:
                            pass

                elif estado is False:
                    estadisticas[chat_id]["ok"] += 1
                elif estado == "RATE_LIMIT":
                    estadisticas[chat_id]["rate_limit"] += 1
                    await asyncio.sleep(5)
                else:
                    estadisticas[chat_id]["error"] += 1

            await asyncio.sleep(1.0)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in usuarios_autorizados:
        solicitudes_pendientes[uid] = user.first_name or "Usuario"
        await update.message.reply_text(
            "🔒 **Acceso Restringido**\n\n"
            f"Tu solicitud con ID `{uid}` fue enviada al **Owner** para aprobación.",
            parse_mode="Markdown"
        )
        if OWNER_ID != 0:
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"📩 **Nueva solicitud**\n• Usuario: @{user.username or 'Sin alias'}\n• ID: `{uid}`\n👉 `/aceptar {uid}`",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    texto = (
        "⚜️ **HUNTER OG • TELEGRAM** ⚜️\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• `/auto5l` — Cazar **5 letras OG** (tipo `ghost`, `viper`)\n"
        "• `/auto5c` — Cazar **5 caracteres Mix** (tipo `v1per`, `gh0st`)\n"
        "• `/autopref` — Cazar con **tu Prefijo OG** (tipo `xbond`)\n"
        "• `/auto4l` — Cazar **4 letras OG** (tipo `bond`, Fragment)\n"
        "• `/check usuario` — Verificar un `@` específico al instante\n"
        "• `/lista` — Descargar archivo `.txt` con los encontrados\n"
        "• `/parar` — Detener la búsqueda\n"
    )
    if uid in admins:
        texto += (
            "\n🛡️ **Panel de Administración:**\n"
            "• `/estado` — Ver diagnóstico en vivo\n"
            "• `/limpiar` — Borrar lista `.txt`\n"
            "• `/aceptar ID` | `/denegar ID` | `/addadmin ID`"
        )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in usuarios_autorizados:
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Uso: `/check ghost`", parse_mode="Markdown")
        return
    target = context.args[0].lower().replace("@", "").strip()
    async with aiohttp.ClientSession() as session:
        res = await verificar_telegram(session, target)
    if res is True:
        await update.message.reply_text(f"✅ `@{target}` **no tiene perfil público activo** (pruébalo en tus ajustes de TG o Fragment).", parse_mode="Markdown")
    elif res is False:
        await update.message.reply_text(f"❌ `@{target}` **ya está en uso**.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ No se pudo verificar en este momento.")

async def cmd_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in usuarios_autorizados:
        return
    if not encontrados_lista:
        await update.message.reply_text("📭 Aún no hay usuarios guardados en la lista.")
        return
    contenido = "\n".join([f"@{u}" for u in encontrados_lista])
    archivo = io.BytesIO(contenido.encode("utf-8"))
    archivo.name = "Telegram_OG_encontrados.txt"
    await update.message.reply_document(document=archivo, caption=f"📄 **Lista TG:** `{len(encontrados_lista)}` usuarios.", parse_mode="Markdown")

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in admins:
        encontrados_lista.clear()
        await update.message.reply_text("🗑️ Lista vaciada.")

async def cmd_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args or not context.args[0].isdigit():
        return
    nuevo_id = int(context.args[0])
    usuarios_autorizados.add(nuevo_id)
    await update.message.reply_text(f"✅ Usuario `{nuevo_id}` aceptado.", parse_mode="Markdown")

async def cmd_denegar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args or not context.args[0].isdigit():
        return
    target_id = int(context.args[0])
    if target_id != OWNER_ID:
        usuarios_autorizados.discard(target_id)
        admins.discard(target_id)
        busquedas_activas[target_id] = False
        await update.message.reply_text(f"🚫 Acceso revocado a `{target_id}`.", parse_mode="Markdown")

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args or not context.args[0].isdigit():
        cmd_parar))
app.add_handler(CommandHandler("estado", cmd_estado))
await app.initialize()
await app.start()
await app.updater.start_polling()
print(f"Bot TG OG activo en puerto {port}...")
await asyncio.Event().wait()
if name == 'main':
asyncio.run(iniciar_todo())
