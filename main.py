import os
from io import BytesIO
import base64

import mercadopago
import qrcode
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================
TELEGRAM_TOKEN = ("8748292806:AAFxfJxMYPfPU1eDDTr5li3l5I2tK3GVphY")
MP_ACCESS_TOKEN = ("APP_USR-4158707768099151-042117-fe3fc6dade05ab2121dc72e60db28db0-3352200768")

GRUPO_VIP = "https://t.me/seugrupovip"
GRUPO_FREE = "https://t.me/seugrupofree"

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 VIP", callback_data="vip")],
        [InlineKeyboardButton("🎁 Teste grátis (1 dia)", callback_data="free")]
    ]

    await update.message.reply_text(
        "🔥 *Bem-vindo ao NoxPlay*\n\n"
        "Doramas e séries curtas pra maratonar!\n\n"
        "Escolha uma opção abaixo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= CRIAR PIX =================
def criar_pix(user_id, valor):
    payment_data = {
        "transaction_amount": float(valor),
        "description": f"user-{user_id}",
        "payment_method_id": "pix",
        "payer": {
            "email": "test_user@test.com"
        }
    }

    return sdk.payment().create(payment_data)

# ================= GERAR PIX =================
async def gerar_pix(update, valor):
    query = update.callback_query
    user_id = query.from_user.id

    res = criar_pix(user_id, valor)

    if res["status"] != 201:
        await query.message.reply_text("❌ Erro ao gerar pagamento.")
        print("ERRO MP:", res)
        return

    pagamento = res["response"]

    tx = pagamento.get("point_of_interaction", {}).get("transaction_data", {})

    copia_cola = tx.get("qr_code")
    qr_base64 = tx.get("qr_code_base64")

    if not copia_cola:
        await query.message.reply_text("❌ Erro ao gerar QR.")
        return

    if qr_base64:
        buffer = BytesIO(base64.b64decode(qr_base64))
    else:
        qr = qrcode.make(copia_cola)
        buffer = BytesIO()
        buffer.name = "pix.png"
        qr.save(buffer)
        buffer.seek(0)

    await query.message.reply_photo(
        photo=buffer,
        caption=(
            f"💰 *Pagamento via PIX*\n\n"
            f"```{copia_cola}```\n\n"
            "⚡ Liberação automática após pagamento"
        ),
        parse_mode="Markdown"
    )

# ================= BOTÕES =================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "vip":
        keyboard = [
            [InlineKeyboardButton("🥉 1 semana - R$7", callback_data="v_7")],
            [InlineKeyboardButton("🥈 1 mês - R$15", callback_data="v_15")],
            [InlineKeyboardButton("🥇 3 meses - R$35", callback_data="v_35")],
            [InlineKeyboardButton("💎 6 meses - R$60", callback_data="v_60")],
            [InlineKeyboardButton("👑 1 ano - R$100", callback_data="v_100")]
        ]

        await query.edit_message_text(
            "🔥 Escolha seu plano VIP:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "free":
        await query.message.reply_text(
            f"🎁 Acesso liberado por 1 dia:\n{GRUPO_FREE}"
        )

    elif query.data.startswith("v_"):
        valor = query.data.split("_")[1]
        await gerar_pix(update, valor)

# ================= RUN =================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("🤖 Bot rodando...")

    app.run_polling()

if __name__ == "__main__":
    main()