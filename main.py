import os
import mercadopago
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY"
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or "APP_USR-8665539850358774-042117-8d004302e0aa99888db395195557a328-494371753"

CHAT_ID_VIP = -1003739412423
CHAT_ID_FREE = -1003788752044

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# ================= BOT =================

app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --------- COMANDO START ---------

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🔥 Comprar VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "🔥 Bem-vindo ao NoxPlay!\n\nClique abaixo para acessar o VIP 👇",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --------- BOTÃO ---------

async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "vip":
        await query.message.reply_text("💰 Aqui você compraria o acesso VIP (integra com MercadoPago)")

# --------- HANDLERS ---------

app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(CallbackQueryHandler(button))

# ================= FASTAPI =================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Iniciando bot...")
    await app_bot.initialize()
    await app_bot.start()
    yield
    print("🛑 Encerrando bot...")
    await app_bot.stop()

app = FastAPI(lifespan=lifespan)

# ================= WEBHOOK TELEGRAM =================

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(request: Request):
    data = await request.json()
    print("🔥 UPDATE RECEBIDO:", data)

    update = Update.de_json(data, app_bot.bot)
    await app_bot.process_update(update)

    return {"ok": True}

# ================= WEBHOOK MERCADOPAGO =================

@app.post("/webhook")
async def mp_webhook(request: Request):
    data = await request.json()
    print("💰 MP WEBHOOK:", data)

    return {"ok": True}

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)