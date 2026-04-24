import os
import json
import asyncio
from io import BytesIO
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import mercadopago
import qrcode
from fastapi import FastAPI, Request

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "SEU_TOKEN"
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or "SEU_MP_TOKEN"

CHAT_ID_VIP = -1003739412423
CHAT_ID_FREE = -1003788752044

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# ================= BANCO =================

DB_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(users_db, f)

users_db = load_db()
users_free = set()

# ================= TEMPO =================

def get_tempo(valor):
    planos = {
        "6.9": 7,
        "14.9": 30,
        "29.9": 90,
        "39.9": 180,
        "69.9": 365,
        "free": 1
    }
    return timedelta(days=planos.get(valor, 0))

# ================= BOT =================

app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 VIP", callback_data="vip")],
        [InlineKeyboardButton("🎁 Teste grátis", callback_data="free")]
    ]

    await update.message.reply_text(
        "🔥 Bem-vindo ao NoxPlay",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= BOTÕES =================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == "vip":
        keyboard = [
            [InlineKeyboardButton("1 mês – 14.9", callback_data="vip_14.9")],
            [InlineKeyboardButton("7 dias – 6.9", callback_data="vip_6.9")]
        ]
        await query.edit_message_text("Escolha:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "free":
        user_id = query.from_user.id
        if user_id in users_free:
            await query.message.reply_text("Você já usou.")
            return

        users_free.add(user_id)
        await liberar_acesso(user_id, "free")

    elif query.data.startswith("vip_"):
        valor = query.data.split("_")[1]
        await gerar_pix(update, valor)

# ================= PIX =================

def criar_pix(user_id, valor):
    return sdk.payment().create({
        "transaction_amount": float(valor),
        "description": f"user-{user_id}",
        "payment_method_id": "pix",
        "payer": {"email": "test@test.com"}
    })

async def gerar_pix(update, valor):
    query = update.callback_query
    res = criar_pix(query.from_user.id, valor)

    if res["status"] != 201:
        await query.message.reply_text("Erro no pagamento")
        return

    copia = res["response"]["point_of_interaction"]["transaction_data"]["qr_code"]

    qr = qrcode.make(copia)
    buffer = BytesIO()
    buffer.name = "pix.png"
    qr.save(buffer)
    buffer.seek(0)

    await query.message.reply_photo(photo=buffer, caption=copia)

# ================= LIBERAR =================

async def liberar_acesso(user_id, valor):
    bot = Bot(token=TELEGRAM_TOKEN)

    expira = datetime.now() + get_tempo(valor)

    users_db[str(user_id)] = {
        "expira": expira.isoformat(),
        "tipo": valor
    }
    save_db()

    chat_id = CHAT_ID_FREE if valor == "free" else CHAT_ID_VIP

    invite = await bot.create_chat_invite_link(chat_id, member_limit=1)

    await bot.send_message(user_id, f"Acesso liberado:\n{invite.invite_link}")

# ================= EXPIRAÇÃO =================

async def verificar_expiracoes():
    bot = Bot(token=TELEGRAM_TOKEN)

    while True:
        agora = datetime.now()

        for user_id, dados in list(users_db.items()):
            if agora > datetime.fromisoformat(dados["expira"]):
                try:
                    chat_id = CHAT_ID_FREE if dados["tipo"] == "free" else CHAT_ID_VIP
                    await bot.ban_chat_member(chat_id, int(user_id))
                    await bot.unban_chat_member(chat_id, int(user_id))
                    del users_db[user_id]
                    save_db()
                except:
                    pass

        await asyncio.sleep(60)

# ================= FASTAPI =================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await app_bot.initialize()
    await app_bot.start()
    asyncio.create_task(verificar_expiracoes())
    yield
    await app_bot.stop()

app = FastAPI(lifespan=lifespan)

# ================= TELEGRAM =================

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, app_bot.bot)
        await app_bot.process_update(update)
        return {"ok": True}
    except Exception as e:
        print("ERRO:", e)
        return {"ok": True}

# ================= MERCADOPAGO =================

@app.post(f"/telegram/{TELEGRAM_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        print("🔥 UPDATE:", data)

        if not app_bot:
            print("❌ BOT NÃO INICIALIZADO")
            return {"ok": False}

        update = Update.de_json(data, app_bot.bot)

        if update:
            await app_bot.process_update(update)

        return {"ok": True}

    except Exception as e:
        print("❌ ERRO WEBHOOK:", str(e))
        return {"ok": True}