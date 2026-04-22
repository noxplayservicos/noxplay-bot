import os
import threading
import time
from io import BytesIO

import mercadopago
import qrcode
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================
TELEGRAM_TOKEN = "8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY"
MP_ACCESS_TOKEN = "APP_USR-8665539850358774-042117-8d004302e0aa99888db395195557a328-494371753"
GRUPO_LINK = "https://t.me/seugrupo"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
app = FastAPI()

# ================= TELEGRAM =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Planos", callback_data="planos")],
        [InlineKeyboardButton("🔥 VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "🔥 Bem-vindo ao NoxPlay\n\nEscolha uma opção abaixo:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def criar_pix(user_id, valor):
    payment_data = {
        "transaction_amount": float(valor),
        "description": f"user-{user_id}",
        "payment_method_id": "pix",
        "payer": {
            "email": "test_user_123@test.com"
        }
    }

    payment = sdk.payment().create(payment_data)

    print("RESPOSTA MP:", payment)

    return payment

async def gerar_pix(update, valor):
    try:
        query = update.callback_query
        user_id = query.from_user.id

        res = criar_pix(user_id, valor)

        print("=== RESPOSTA COMPLETA MP ===")
        print(res)
        print("===========================")

        # verifica erro
        if res["status"] != 201:
            await query.message.reply_text(f"❌ ERRO MP:\n{res}")
            return

        pagamento = res["response"]

        # tenta pegar QR de forma segura
        tx = pagamento.get("point_of_interaction", {}).get("transaction_data", {})

        copia_cola = tx.get("qr_code")
        qr_base64 = tx.get("qr_code_base64")

        if not copia_cola:
            await query.message.reply_text(f"❌ NÃO VEIO QR:\n{pagamento}")
            return

        # gera imagem do QR (se tiver base64)
        if qr_base64:
            import base64
            buffer = BytesIO(base64.b64decode(qr_base64))
        else:
            import qrcode
            qr = qrcode.make(copia_cola)
            buffer = BytesIO()
            buffer.name = "pix.png"
            qr.save(buffer)
            buffer.seek(0)

        await query.message.reply_photo(
            photo=buffer,
            caption=f"💰 PIX:\n\n```{copia_cola}```",
            parse_mode="Markdown"
        )

    except Exception as e:
        print("ERRO GERAL:", e)
        await query.message.reply_text("❌ Erro ao gerar pagamento.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "planos":
        keyboard = [
            [InlineKeyboardButton("1 série - R$5", callback_data="p_5")],
            [InlineKeyboardButton("3 séries - R$10", callback_data="p_10")],
            [InlineKeyboardButton("6 séries - R$20", callback_data="p_20")]
        ]
        await query.edit_message_text("Escolha seu plano:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("p_"):
        valor = query.data.split("_")[1]
        await gerar_pix(update, valor)

# ================= WEBHOOK =================
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if data.get("type") == "payment":
        payment_id = data["data"]["id"]
        payment = sdk.payment().get(payment_id)

        if payment["response"]["status"] == "approved":
            descricao = payment["response"]["description"]
            user_id = int(descricao.split("-")[1])

            bot = Bot(token=TELEGRAM_TOKEN)

            await bot.send_message(
                chat_id=user_id,
                text=f"🔥 Pagamento aprovado!\n\nAcesse:\n{GRUPO_LINK}"
            )

    return {"status": "ok"}

# ================= BOT =================
def run_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button))

    print("🤖 Bot rodando...")

    app_bot.run_polling()

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()

    time.sleep(2)

    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)