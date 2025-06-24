import asyncio
import json
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from common import (
    PRODUCTS,
    PRODUCT_NAME_MAP,
    SHORT_TO_FULL,
    TELEGRAM_BOT_TOKEN,
    PRIVATE_REPO,
    GITHUB_BRANCH,
    GH_PAT,
    setup_logging,
    mask,
    is_already_running,
    get_file_sha,
    read_users_file,
)

logger = setup_logging()

def update_users_file(users_data):
    path = "users.json"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sha = get_file_sha(path)
            if not sha:
                logger.error("Failed to get SHA for users.json on attempt %d", attempt + 1)
                continue
            url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{path}"
            headers = {
                "Authorization": f"token {GH_PAT}",
                "Accept": "application/vnd.github+json",
            }
            content = base64.b64encode(json.dumps(users_data, indent=2).encode()).decode()
            data = {
                "message": "Update users.json with new user data",
                "content": content,
                "sha": sha,
                "branch": GITHUB_BRANCH,
            }
            response = requests.put(url, headers=headers, json=data)
            if response.status_code == 200:
                return True
            logger.error(
                "Failed to update users.json on attempt %d: Status %d, Response: %s",
                attempt + 1,
                response.status_code,
                response.text,
            )
        except Exception as e:
            logger.error("Error updating users.json on attempt %d: %s", attempt + 1, str(e))
        if attempt < max_retries - 1:
            time.sleep(2)
    return False

async def start(update: Update, context: ContextTypes):
    chat_id = update.effective_chat.id
    logger.info("Handling /start command for chat_id %s", mask(chat_id))
    await update.message.reply_text(
        "Welcome to the Amul Protein Items Notifier Bot!\n"
        "Use /setpincode PINCODE to set your PIN code (Mandatory).\n"
        "Use /setproducts to select products (Optional, by default we will show any Amul protein product which is available for your pincode).\n"
        "Use /stop to stop notifications."
    )

async def set_pincode(update: Update, context: ContextTypes):
    chat_id = update.effective_chat.id
    logger.info("Handling /setpincode command for chat_id %s", mask(chat_id))
    if not context.args:
        await update.message.reply_text("Please provide a PIN code. Usage: /setpincode PINCODE")
        return
    pincode = context.args[0]
    if not pincode.isdigit() or len(pincode) != 6:
        await update.message.reply_text("PIN code must be a 6-digit number.")
        return
    users_data = read_users_file()
    users = users_data["users"]
    user = next((u for u in users if u["chat_id"] == str(chat_id)), None)
    if user:
        user["pincode"] = pincode
        user["active"] = True
    else:
        users.append({
            "chat_id": str(chat_id),
            "pincode": pincode,
            "products": ["Any"],
            "active": True,
        })
    if update_users_file(users_data):
        await update.message.reply_text(f"PIN code set to {pincode}. You will receive notifications for available products.")
    else:
        await update.message.reply_text("Failed to update your PIN code. Please try again.")

async def set_products(update: Update, context: ContextTypes):
    chat_id = update.effective_chat.id
    logger.info("Handling /setproducts command for chat_id %s", mask(chat_id))
    users_data = read_users_file()
    users = users_data["users"]
    user = next((u for u in users if u["chat_id"] == str(chat_id)), None)
    if not user:
        await update.message.reply_text("Please set your PIN code first using /setpincode PINCODE")
        return
    context.user_data["selected_products"] = []
    keyboard = []
    for i, product in enumerate(PRODUCTS, 1):
        callback_data = f"product_{i}"
        display_text = PRODUCT_NAME_MAP[product]
        selected = "✅ " if product in context.user_data["selected_products"] else ""
        keyboard.append([InlineKeyboardButton(f"{selected}{display_text}", callback_data=callback_data)])
    keyboard.append([InlineKeyboardButton("Confirm Selection", callback_data="confirm_products")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select products to monitor (click 'Any of the products from the list' for all products):\n"
        "Toggle selections, then press 'Confirm Selection'.",
        reply_markup=reply_markup,
    )

async def product_callback(update: Update, context: ContextTypes):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    logger.info("Handling product callback for chat_id %s: %s", mask(chat_id), query.data)
    try:
        if query.data == "confirm_products":
            selected_products = context.user_data.get("selected_products", [])
            if not selected_products:
                await query.message.reply_text("No products selected. Please select at least one product or 'Any of the products from the list'.")
                return
            users_data = read_users_file()
            users = users_data["users"]
            user = next((u for u in users if u["chat_id"] == str(chat_id)), None)
            if not user:
                await query.message.reply_text("Please set your PIN code first using /setpincode PINCODE")
                return
            user["products"] = selected_products
            user["active"] = True
            if update_users_file(users_data):
                display_products = [PRODUCT_NAME_MAP[p] for p in selected_products]
                await query.message.reply_text(
                    f"You'll get notifications for:\n" + "\n".join(f"- {p}" for p in display_products),
                    parse_mode="Markdown",
                )
                logger.info("User %s set products: %s", mask(chat_id), selected_products)
                context.user_data.pop("selected_products", None)
            else:
                await query.message.reply_text("Failed to update products. Please try again.")
            return
        if query.data.startswith("product_"):
            index = int(query.data.replace("product_", "")) - 1
            if index < 0 or index >= len(PRODUCTS):
                logger.warning("Invalid product index %d for chat_id %s", index, mask(chat_id))
                return
            selected_product = PRODUCTS[index]
            selected_products = context.user_data.setdefault("selected_products", [])
            if selected_product == "Any":
                if "Any" in selected_products:
                    selected_products.remove("Any")
                    logger.info("User %s deselected 'Any'", mask(chat_id))
                else:
                    selected_products.clear()
                    selected_products.append("Any")
                    logger.info("User %s selected 'Any', clearing specific products", mask(chat_id))
            else:
                if "Any" in selected_products:
                    selected_products.clear()
                    logger.info("User %s selected specific product, removing 'Any'", mask(chat_id))
                if selected_product in selected_products:
                    selected_products.remove(selected_product)
                    logger.info("User %s deselected product: %s", mask(chat_id), selected_product)
                else:
                    selected_products.append(selected_product)
                    logger.info("User %s selected product: %s", mask(chat_id), selected_product)
            keyboard = []
            for i, product in enumerate(PRODUCTS, 1):
                callback_data = f"product_{i}"
                display_text = PRODUCT_NAME_MAP[product]
                is_selected = product in selected_products
                selected = "✅ " if is_selected else ""
                keyboard.append([InlineKeyboardButton(f"{selected}{display_text}", callback_data=callback_data)])
            keyboard.append([InlineKeyboardButton("Confirm Selection", callback_data="confirm_products")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
    except Exception as e:
        logger.error("Error in product callback for chat_id %s: %s", mask(chat_id), str(e))
        await query.message.reply_text("An error occurred. Please try /setproducts again.")

async def stop(update: Update, context: ContextTypes):
    chat_id = update.effective_chat.id
    logger.info("Handling /stop command for chat_id %s", mask(chat_id))
    users_data = read_users_file()
    users = users_data["users"]
    user = next((u for u in users if u["chat_id"] == str(chat_id)), None)
    if not user:
        await update.message.reply_text("You are not subscribed to notifications.")
        return
    user["active"] = False
    if update_users_file(users_data):
        await update.message.reply_text("Notifications stopped. Use /setpincode to restart.")
    else:
        await update.message.reply_text("Failed to stop notifications. Please try again.")

async def run_polling(app):
    await app.initialize()
    await app.start()
    await app.updater.start_polling(timeout=5)
    logger.info("Polling started")
    try:
        await asyncio.Event().wait()  # Keep running until interrupted
    except asyncio.CancelledError:
        logger.info("Polling task cancelled")
    except KeyboardInterrupt:
        logger.info("Polling stopped manually")
    finally:
        logger.info("Shutting down bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Bot shutdown complete")

def main():
    logger.info("Starting main function")
    if is_already_running("main.py"):
        logger.error("Another instance of the bot is already running. Exiting...")
        raise SystemExit(1)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpincode", set_pincode))
    app.add_handler(CommandHandler("setproducts", set_products))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(product_callback))
    asyncio.run(run_polling(app))

if __name__ == "__main__":
    main()
