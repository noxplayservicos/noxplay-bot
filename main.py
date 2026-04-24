import os
import mercadopago
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY"
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or "APP_USR-8665539850358774-042117-8d004302e0aa99888db395195557a328-494371753"

CHAT_ID_VIP = -1003739412423
CHAT_ID_FREE = -1003788752044

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

app = FastAPI()

# ================= BOT =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Bot funcionando!")

telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))


# ================= STARTUP =================

@app.on_event("startup")
async def startup():
    print("🚀 Inicializando bot...")
    await telegram_app.initialize()
    await telegram_app.start()


# ================= WEBHOOK TELEGRAM =================

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()

    update = Update.de_json(data, telegram_app.bot)

    await telegram_app.process_update(update)

    return {"ok": True}


# ================= WEBHOOK MP =================

@app.post("/webhook")
async def mp_webhook(request: Request):
    data = await request.json()
    print("💰 MP WEBHOOK:", data)

    return {"ok": True}