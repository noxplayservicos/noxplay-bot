import os
import json
import asyncio
import threading
import time
from io import BytesIO
from datetime import datetime, timedelta

import mercadopago
import qrcode
from fastapi import FastAPI, Request
import uvicorn

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================
TELEGRAM_TOKEN = ("8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY")
MP_ACCESS_TOKEN = ("APP_USR-8665539850358774-042117-8d004302e0aa99888db395195557a328-494371753")

CHAT_ID_VIP = -1003739412423
CHAT_ID_FREE = -1003788752044

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
app = FastAPI()

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

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 VIP", callback_data="vip")],
        [InlineKeyboardButton("🎁 Teste grátis (1 dia)", callback_data="free")]
    ]

    await update.message.reply_text(
        "🔥 *Bem-vindo ao NoxPlay*\n\nEscolha uma opção:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= PIX =================
from datetime import datetime, timedelta

def criar_pix(user_id, valor):
    data = {
        "transaction_amount": float(valor),
        "description": f"user-{user_id}",
        "payment_method_id": "pix",
        "date_of_expiration": (datetime.utcnow() + timedelta(minutes=60)).isoformat(),
        "payer": {
            "email": "test@test.com"
        }
    }

    return sdk.payment().create(data)

async def gerar_pix(update, valor):
    query = update.callback_query
    res = criar_pix(query.from_user.id, valor)

    if res["status"] != 201:
        await query.message.reply_text("❌ Erro ao gerar pagamento.")
        return

    tx = res["response"]["point_of_interaction"]["transaction_data"]
    copia = tx["qr_code"]

    qr = qrcode.make(copia)
    buffer = BytesIO()
    buffer.name = "pix.png"
    qr.save(buffer)
    buffer.seek(0)

    await query.message.reply_photo(
        photo=buffer,
        caption=f"💰 PIX\n\n```{copia}```",
        parse_mode="Markdown"
    )

# ================= LIBERAR =================
async def liberar_acesso(user_id, valor):
    bot = Bot(token=TELEGRAM_TOKEN)

    tempo = get_tempo(valor)
    expira = datetime.now() + tempo

    users_db[str(user_id)] = {
        "expira": expira.isoformat(),
        "tipo": valor
    }
    save_db()

    chat_id = CHAT_ID_FREE if valor == "free" else CHAT_ID_VIP

    invite = await bot.create_chat_invite_link(
        chat_id=chat_id,
        member_limit=1
    )

    await bot.send_message(
        chat_id=user_id,
        text=(
            "🔥 <b>Acesso liberado!</b>\n\n"
            f"{invite.invite_link}\n\n"
            f"⏳ <b>Válido até:</b> {expira.strftime('%d/%m %H:%M')}\n\n"
            "🔐 Link pessoal e intransferível."
        ),
        parse_mode="HTML"
    )

# ================= EXPIRAÇÃO =================
async def verificar_expiracoes():
    bot = Bot(token=TELEGRAM_TOKEN)

    while True:
        agora = datetime.now()

        for user_id, dados in list(users_db.items()):
            expira = datetime.fromisoformat(dados["expira"])
            tipo = dados["tipo"]

            if agora > expira:
                try:
                    chat_id = CHAT_ID_FREE if tipo == "free" else CHAT_ID_VIP

                    await bot.ban_chat_member(chat_id, int(user_id))
                    await bot.unban_chat_member(chat_id, int(user_id))

                    del users_db[user_id]
                    save_db()

                    await bot.send_message(
                        chat_id=int(user_id),
                        text="⛔ Seu acesso expirou."
                    )
                except:
                    pass

        await asyncio.sleep(60)

# ================= WEBHOOK =================
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("WEBHOOK:", data)

    if data.get("type") == "payment":
        payment_id = data["data"]["id"]

        payment = sdk.payment().get(payment_id)
        print("PAGAMENTO:", payment)

        status = payment["response"].get("status")

        if status == "approved":
            descricao = payment["response"]["description"]
            user_id = int(descricao.split("-")[1])
            valor = str(payment["response"]["transaction_amount"])

            print("✅ PAGAMENTO APROVADO:", user_id)

            await liberar_acesso(user_id, valor)

    return {"status": "ok"}

# ================= BOTÕES =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "vip":
        keyboard = [
            [InlineKeyboardButton("🔥 1 Mês – R$14,90", callback_data="vip_14.9")],
            [InlineKeyboardButton("💰 1 Semana – R$6,90", callback_data="vip_6.9")],
            [InlineKeyboardButton("🥈 3 Meses – R$29,90", callback_data="vip_29.9")],
            [InlineKeyboardButton("🥇 6 Meses – R$39,90", callback_data="vip_39.9")],
            [InlineKeyboardButton("👑 1 Ano – R$69,90", callback_data="vip_69.9")]
        ]

        await query.edit_message_text("🔥 Escolha seu plano VIP:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "free":
        user_id = query.from_user.id

        if user_id in users_free:
            await query.message.reply_text("❌ Você já usou o teste.")
            return

        users_free.add(user_id)
        await liberar_acesso(user_id, "free")

    elif query.data.startswith("vip_"):
        valor = query.data.split("_")[1]
        await gerar_pix(update, valor)

# ================= RUN =================
def run_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button))

    print("🤖 Bot rodando...")
    app_bot.run_polling()

def main():
    threading.Thread(target=run_bot).start()
    time.sleep(2)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(verificar_expiracoes())

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

if __name__ == "__main__":
    main()