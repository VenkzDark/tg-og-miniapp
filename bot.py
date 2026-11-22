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

def generar_4c_tiktok():
    """Genera 4 caracteres válidos en TikTok (letras, números, '_' y '.')."""
    caracteres = string.ascii_lowercase + string.digits + "_."
    while True:
        user = ''.join(random.choices(caracteres, k=4))
        # TikTok prohíbe terminar en punto, dos puntos seguidos o ser solo números
        if not user.endswith('.') and '..' not in user and not user.isdigit():
            return user

def generar_4l_tiktok():
    """Genera 4 letras puras pronunciables (ej. 'kizu', 'bako')."""
    vocales = "aeiou"
    consonantes = "bcdfghjklmnprstvz"
    return (
        random.choice(consonantes) +
        random.choice(vocales) +
        random.choice(consonantes) +
        random.choice(vocales)
    )

async def verificar_tiktok(session, username):
    """Analiza el código interno de TikTok para saber si el perfil existe."""
    global ultimo_detalle
    url = "https://tiktok.com" + "/@" + username
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        async with session.get(url, headers=headers, timeout=10) as resp:
            if resp.status == 429:
                ultimo_detalle = "429 (Rate Limit - Pausa)"
                return "RATE_LIMIT"
            elif resp.status == 403:
                ultimo_detalle = "403 (Bloqueo temporal)"
                return "ERROR"

            texto = await resp.text()

            # 10202 es el código interno de TikTok cuando el usuario no existe
            if '"statusCode":10202' in texto or "couldn't find this account" in texto.lower():
                ultimo_detalle = f"Libre (@{username})"
                return True

            # 0 es el código cuando el usuario sí existe y tiene perfil activo
            if '"statusCode":0' in texto or f'"uniqueId":"{username}"' in texto:
                ultimo_detalle = f"Ocupado (@{username})"
                return False

            # Si TikTok devolvió captcha o página vacía de bloqueo
            ultimo_detalle = f"Captcha/Filtro (HTTP {resp.status})"
            return "ERROR"
    except Exception as e:
        ultimo_detalle = f"Error red: {str(e)[:40]}"
        return "ERROR"

async def bucle_automatico(chat_id: int, app, modo: str):
    estadisticas[chat_id] = {"revisados": 0, "ok": 0, "libres": 0, "error": 0, "rate_limit": 0}

    async with aiohttp.ClientSession() as session:
        while busquedas_activas.get(chat_id, False):
            # En TikTok conviene ir de 2 en 2 con pausa de 1.5s para evitar captchas
            if modo == "4l":
                lote = [generar_4l_tiktok() for _ in range(2)]
            else:
                lote = [generar_4c_tiktok() for _ in range(2)]

            tareas = [verificar_tiktok(session, u) for u in lote]
            resultados = await asyncio.gather(*tareas)

            for user, estado in zip(lote, resultados):
                estadisticas[chat_id]["revisados"] += 1

                if estado is True:
                    estadisticas[chat_id]["ok"] += 1
                    estadisticas[chat_id]["libres"] += 1

                    if user not in encontrados_lista:
                        encontrados_lista.append(user)

                    mensaje_hit = (
                        f"🎵 **4C/4L POSIBLE EN TIKTOK**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 **Usuario:** `@{user}`\n"
                        f"🔗 **Perfil:** `://tiktok.com@{user}`\n"
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
                    await asyncio.sleep(8)
                else:
                    estadisticas[chat_id]["error"] += 1

            await asyncio.sleep(1.5)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in usuarios_autorizados:
        solicitudes_pendientes[uid] = user.first_name or "Usuario"
        await update.message.reply_text(
            "🔒 **Acceso Restringido**\n\n"
            "No tienes permiso para usar este bot.\n"
            f"Tu solicitud con ID `{uid}` fue enviada al **Owner** para su aprobación.",
            parse_mode="Markdown"
        )
        if OWNER_ID != 0:
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=(
                        f"📩 **Nueva solicitud de acceso**\n\n"
                        f"• Nombre: {user.first_name}\n"
                        f"• Usuario: @{user.username or 'Sin alias'}\n"
                        f"• ID: `{uid}`\n\n"
                        f"👉 Para aceptarlo envía: `/aceptar {uid}`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    texto = (
        "🎵 **HUNTER 4C / 4L • TIKTOK** 🎵\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• `/auto4c` — Cazar **4 caracteres** (letras, números, `.`, `_`)\n"
        "• `/auto4l` — Cazar **4 letras puras** (ej. `kizu`)\n"
        "• `/parar` — Detener la búsqueda\n"
        "• `/lista` — Descargar archivo `.txt` con los encontrados\n"
    )
    if uid in admins:
        texto += (
            "\n🛡️ **Panel de Administración:**\n"
            "• `/estado` — Ver diagnóstico en vivo\n"
            "• `/limpiar` — Borrar la lista `.txt` guardada\n"
            "• `/aceptar ID` — Dar acceso a un usuario\n"
            "• `/denegar ID` — Quitar acceso a un usuario\n"
            "• `/addadmin ID` — Hacer administrador a un usuario"
        )
    await update.message.reply_text(texto, parse_mode="Markdown")

async def cmd_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in usuarios_autorizados:
        return

    if not encontrados_lista:
        await update.message.reply_text("📭 Aún no hay usuarios guardados en la lista.")
        return

    contenido = "\n".join([f"@{u}" for u in encontrados_lista])
    archivo = io.BytesIO(contenido.encode("utf-8"))
    archivo.name = "TikTok_4C_posibles.txt"

    await update.message.reply_document(
        document=archivo,
        caption=f"📄 **Lista TikTok:** `{len(encontrados_lista)}` usuarios encontrados.",
        parse_mode="Markdown"
    )

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins:
        return
    encontrados_lista.clear()
    await update.message.reply_text("🗑️ Lista `.txt` vaciada correctamente.", parse_mode="Markdown")

async def cmd_aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Solo el **Owner** puede aceptar usuarios.", parse_mode="Markdown")
        return

    if not context.args or not context.args.isdigit():
        await update.message.reply_text("ℹ️ Uso correcto: `/aceptar 123456789`", parse_mode="Markdown")
        return

    nuevo_id = int(context.args)
    usuarios_autorizados.add(nuevo_id)
    solicitudes_pendientes.pop(nuevo_id, None)
    await update.message.reply_text(f"✅ Usuario `{nuevo_id}` **aceptado**.", parse_mode="Markdown")

    try:
        await context.bot.send_message(
            chat_id=nuevo_id,
            text="🎉 **¡Tu acceso ha sido aprobado por el Owner!**\nEnvía `/start` para ver los comandos.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def cmd_denegar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Solo el **Owner** puede revocar accesos.", parse_mode="Markdown")
        return

    if not context.args or not context.args.isdigit():
        await update.message.reply_text("ℹ️ Uso correcto: `/denegar 123456789`", parse_mode="Markdown")
        return

    target_id = int(context.args)
    if target_id == OWNER_ID:
        await update.message.reply_text("⚠️ No puedes bloquearte a ti mismo.")
        return

    usuarios_autorizados.discard(target_id)
    admins.discard(target_id)
    busquedas_activas[target_id] = False
    await update.message.reply_text(f"🚫 Acceso eliminado para `{target_id}`.", parse_mode="Markdown")

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Solo el **Owner** puede nombrar administradores.", parse_mode="Markdown")
        return

    if not context.args or not context.args.isdigit():
        await update.message.reply_text("ℹ️ Uso correcto: `/addadmin 123456789`", parse_mode="Markdown")
        Usa el código con precaución.
return
nuevo_admin = int(context.args)
usuarios_autorizados.add(nuevo_admin)
admins.add(nuevo_admin)
await update.message.reply_text(f"🛡️ Usuario {nuevo_admin} ahora es Administrador.", parse_mode="Markdown")
async def iniciar_caza(update: Update, context: ContextTypes.DEFAULT_TYPE, modo: str, etiqueta: str):
uid = update.effective_user.id
if uid not in usuarios_autorizados:
await update.message.reply_text("🔒 No estás autorizado. Envía /start para solicitar acceso.", parse_mode="Markdown")
return
chat_id = update.effective_chat.id
if busquedas_activas.get(chat_id, False):
await update.message.reply_text("⚠️ Ya tienes una caza activa. Usa /parar primero.", parse_mode="Markdown")
return
busquedas_activas[chat_id] = True
await update.message.reply_text(
f"🚀 Caza de {etiqueta} en TikTok iniciada...\n"
"Recuerda probar los hallazgos en la app de TikTok para confirmar que no estén congelados.",
parse_mode="Markdown"
)
asyncio.create_task(bucle_automatico(chat_id, context.application, modo))
async def cmd_auto4c(update: Update, context: ContextTypes.DEFAULT_TYPE):
await iniciar_caza(update, context, "4c", "4 caracteres (4C)")
async def cmd_auto4l(update: Update, context: ContextTypes.DEFAULT_TYPE):
await iniciar_caza(update, context, "4l", "4 letras puras (4L)")
async def cmd_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id not in usuarios_autorizados:
return
chat_id = update.effective_chat.id
busquedas_activas[chat_id] = False
await update.message.reply_text("🛑 Búsqueda detenida.")
async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
if update.effective_user.id not in admins:
await update.message.reply_text("⛔ Este comando es exclusivo para Administradores.", parse_mode="Markdown")
return
chat_id = update.effective_chat.id
stats = estadisticas.get(chat_id)
if not stats:
await update.message.reply_text("ℹ️ No hay ninguna sesión activa. Envía /auto4c o /auto4l.", parse_mode="Markdown")
return
texto = (
f"🛡️ DIAGNÓSTICO ADMIN • TIKTOK\n"
f"━━━━━━━━━━━━━━━━━━━━\n"
f"• Intentados: {stats['revisados']}\n"
f"• Verificados OK: {stats['ok']}\n"
f"• Posibles Libres: {stats['libres']}\n"
f"• Guardados en .txt: {len(encontrados_lista)}\n"
f"• Rate Limits: {stats['rate_limit']}\n"
f"• Errores/Captcha: {stats['error']}\n"
f"• Último estado: {ultimo_detalle}"
)
await update.message.reply_text(texto, parse_mode="Markdown")
async def web_ping(request):
return web.Response(text="Hunter TikTok activo")
async def iniciar_todo():
web_app = web.Application()
web_app.router.add_get("/", web_ping)
runner = web.AppRunner(web_app)
await runner.setup()
port = int(os.environ.get("PORT", 10000))
site = web.TCPSite(runner, "0.0.0.0", port)
await site.start()
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", cmd_start))
app.add_handler(CommandHandler("lista", cmd_lista))
app.add_handler(CommandHandler("limpiar", cmd_limpiar))
app.add_handler(CommandHandler("aceptar", cmd_aceptar))
app.add_handler(CommandHandler("denegar", cmd_denegar))
app.add_handler(CommandHandler("addadmin", cmd_addadmin))
app.add_handler(CommandHandler("auto4c", cmd_auto4c))
app.add_handler(CommandHandler("auto4l", cmd_auto4l))
app.add_handler(CommandHandler("parar", cmd_parar))
app.add_handler(CommandHandler("estado", cmd_estado))
await app.initialize()
await app.start()
await app.updater.start_polling()
print(f"Bot TikTok activo en puerto {port}...")
await asyncio.Event().wait()
if name == 'main':
   asyncio.run(iniciar_todo())