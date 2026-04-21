import mercadopago
import qrcode
from io import BytesIO
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import threading
import uvicorn

# ================= CONFIG =================
TELEGRAM_TOKEN = "8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY"
MP_ACCESS_TOKEN = "APP_USR-8665539850358774-042117-8d004302e0aa99888db395195557a328-494371753"
GRUPO_LINK = "https://t.me/seugrupo"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
app_web = FastAPI()

# ================= TELEGRAM =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Planos", callback_data="planos")],
        [InlineKeyboardButton("🔥 VIP", callback_data="vip")]
    ]

    await update.message.reply_text(
        "🔥 Bem-vindo ao NoxPlay\n\nDoramas e séries curtas pra maratonar!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def criar_pix(user_id, valor):
    payment_data = {
        "transaction_amount": float(valor),
        "description": f"user-{user_id}",
        "payment_method_id": "pix",
        "payer": {
            "email": f"user{user_id}@noxplay.com"
        }
    }

    payment = sdk.payment().create(payment_data)
    return payment["response"]

async def gerar_pix(update, valor):
    try:
        query = update.callback_query
        user_id = query.from_user.id

        pagamento = criar_pix(user_id, valor)

        copia_cola = pagamento["point_of_interaction"]["transaction_data"]["qr_code"]

        # gerar QR code
        qr = qrcode.make(copia_cola)
        buffer = BytesIO()
        buffer.name = 'pix.png'
        qr.save(buffer)
        buffer.seek(0)

        await query.message.reply_photo(
            photo=buffer,
            caption=(
                "💰 *Pague via PIX*\n\n"
                "📸 Escaneie o QR Code acima\n\n"
                "📋 *Toque abaixo para copiar:*\n\n"
                f"```{copia_cola}```\n\n"
                "⚡ Liberação automática após pagamento"
            ),
            parse_mode="Markdown"
        )

    except Exception as e:
        print("ERRO gerar_pix:", e)
        await query.message.reply_text("❌ Erro ao gerar pagamento. Tente novamente.")

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

    elif query.data == "vip":
        keyboard = [
            [InlineKeyboardButton("Semanal - R$7", callback_data="v_7")],
            [InlineKeyboardButton("Mensal - R$15", callback_data="v_15")],
            [InlineKeyboardButton("Trimestral - R$35", callback_data="v_35")]
        ]
        await query.edit_message_text("Escolha seu VIP:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("p_") or query.data.startswith("v_"):
        valor = query.data.split("_")[1]
        await gerar_pix(update, valor)

# ================= WEBHOOK =================
@app_web.post("/webhook")
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
                text=f"🔥 Pagamento aprovado!\n\nAcesse agora:\n{GRUPO_LINK}"
            )

    return {"status": "ok"}

# ================= RUN =================
def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("🤖 Bot rodando...")

    app.run_polling()

if __name__ == "__main__":
    # roda bot em paralelo
    threading.Thread(target=run_bot).start()

    # roda servidor webhook
    uvicorn.run(app_web, host="0.0.0.0", port=8000)