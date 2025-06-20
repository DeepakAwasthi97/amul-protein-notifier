import os
import json
import base64
import requests
import shutil
import psutil
import sys
import time
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Product list for inline keyboard
PRODUCTS = [
    "Any of the products from the list",
    "Amul Kool Protein Milkshake | Chocolate, 180 mL | Pack of 30",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 8",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 30",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 8",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 30",
    "Amul High Protein Blueberry Shake, 200 mL | Pack of 30",
    "Amul High Protein Plain Lassi, 200 mL | Pack of 30",
    "Amul High Protein Rose Lassi, 200 mL | Pack of 30",
    "Amul High Protein Buttermilk, 200 mL | Pack of 30",
    "Amul High Protein Milk, 250 mL | Pack of 8",
    "Amul High Protein Milk, 250 mL | Pack of 32",
    "Amul High Protein Paneer, 400 g | Pack of 24",
    "Amul High Protein Paneer, 400 g | Pack of 2",
    "Amul Whey Protein Gift Pack, 32 g | Pack of 10 sachets",
    "Amul Whey Protein, 32 g | Pack of 30 Sachets",
    "Amul Whey Protein Pack, 32 g | Pack of 60 Sachets",
    "Amul Chocolate Whey Protein Gift Pack, 34 g | Pack of 10 sachets",
    "Amul Chocolate Whey Protein, 34 g | Pack of 30 sachets",
    "Amul Chocolate Whey Protein, 34 g | Pack of 60 sachets"
]

# Setup masking for sensitive information
def mask(value, visible=2):
    value = str(value)
    if len(value) <= visible * 2:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - 2 * visible) + value[-visible:]

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('product_check.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_PAT = os.getenv("GH_PAT")
PRIVATE_REPO = os.getenv("PRIVATE_REPO")
GITHUB_BRANCH = "main"

# Define pincode cache
pincode_cache = {}

# Check if another running instance
def is_already_running():
    logger.info("Checking for running instances")
    current_pid = os.getpid()
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (proc.info['name'].lower() == 'python' and 
                    proc.info['cmdline'] and 
                    'main.py' in ' '.join(proc.info['cmdline']).lower() and 
                    proc.info['pid'] != current_pid):
                    logger.info("Found another running instance with PID %d", proc.info['pid'])
                    return True
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                logger.warning("Could not access process %d: %s", proc.info['pid'], str(e))
                continue
    except Exception as e:
        logger.error("Error checking running processes: %s", str(e))
        return False
    logger.info("No other running instances found")
    return False

# GitHub API helper functions
def get_file_sha(path):
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["sha"]
    logger.error("Could not retrieve SHA for %s: Status %d, Response: %s", path, response.status_code, response.text)
    return None

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
                "Accept": "application/vnd.github+json"
            }
            content = base64.b64encode(json.dumps(users_data, indent=2).encode()).decode()
            data = {
                "message": "Update users.json with new user data",
                "content": content,
                "sha": sha,
                "branch": GITHUB_BRANCH
            }
            response = requests.put(url, headers=headers, json=data)
            if response.status_code == 200:
                return True
            logger.error("Failed to update users.json on attempt %d: Status %d, Response: %s", 
                        attempt + 1, response.status_code, response.text)
        except Exception as e:
            logger.error("Error updating users.json on attempt %d: %s", attempt + 1, str(e))
        if attempt < max_retries - 1:
            time.sleep(2)
    return False

def read_users_file():
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/users.json?ref={GITHUB_BRANCH}"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error("Failed to read users.json: Status %d, Response: %s", response.status_code, response.text)
        return {"users": []}
    content = base64.b64decode(response.json()["content"]).decode()
    return json.loads(content)

# Telegram bot command handlers
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
            "active": True
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
        display_text = product if i != 1 else f"❗ 𝐀𝐧𝐲 𝐨𝐟 𝐭𝐡𝐞 𝐩𝐫𝐨𝐝𝐮𝐜𝐭𝐬 𝐟𝐫𝐨𝐦 𝐭𝐡𝐞 𝐥𝐢𝐬𝐭"
        selected = "✅ " if product in context.user_data["selected_products"] else ""
        keyboard.append([InlineKeyboardButton(f"{selected}{display_text}", callback_data=callback_data)])
    keyboard.append([InlineKeyboardButton("Confirm Selection", callback_data="confirm_products")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select products to receive notifications for (click 'Any' for all products, or select specific ones):\n"
        "Use the buttons below to toggle selections, then press 'Confirm Selection'.",
        reply_markup=reply_markup
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
                await query.message.reply_text("No products selected. Please select at least one product or 'Any'.")
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
                display_products = ["Any of the products from the list" if p == "Any" else p for p in selected_products]
                await query.message.reply_text(
                    f"Fantastic! You'll now get notifications for these products:\n" + "\n".join(f"- {p}" for p in display_products)
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
            selected_product = "Any" if index == 0 else PRODUCTS[index]
            selected_products = context.user_data.get("selected_products", [])
            if selected_product == "Any":
                if "Any" in selected_products:
                    selected_products.remove("Any")
                    logger.info("User %s deselected 'Any'", mask(chat_id))
                else:
                    selected_products = ["Any"]
                    logger.info("User %s selected 'Any', clearing specific products", mask(chat_id))
            else:
                if "Any" in selected_products:
                    selected_products = []
                    logger.info("User %s selected specific product, removing 'Any'", mask(chat_id))
                if selected_product in selected_products:
                    selected_products.remove(selected_product)
                    logger.info("User %s deselected product: %s", mask(chat_id), selected_product)
                else:
                    selected_products.append(selected_product)
                    logger.info("User %s selected product: %s", mask(chat_id), selected_product)
            context.user_data["selected_products"] = selected_products
            keyboard = []
            for i, product in enumerate(PRODUCTS, 1):
                callback_data = f"product_{i}"
                display_text = product if i != 1 else f"❗ 𝐀𝐧𝐲 𝐨𝐟 𝐭𝐡𝐞 𝐩𝐫𝐨𝐝𝐮𝐜𝐭𝐬 𝐟𝐫𝐨𝐦 𝐭𝐡𝐞 𝐥𝐢𝐬𝐭"
                is_selected = product in selected_products or (product == PRODUCTS[0] and "Any" in selected_products)
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

# Product checking function
def check_product_availability(pincode):
    global pincode_cache
    if pincode in pincode_cache:
        logger.info(f"Using cached results for pincode: {mask(pincode)}")
        return pincode_cache[pincode]
    url = "https://shop.amul.com/en/browse/protein"
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.69 Safari/537.36")
    driver = None
    try:
        logger.info("Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome WebDriver initialized successfully")
        driver.set_window_size(1920, 1080)
        logger.info("Navigating to URL: %s", url)
        driver.get(url)
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.info("Page loaded completely")
        try:
            logger.info("Locating PINCODE input field...")
            pincode_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="search"]'))
            )
            logger.info("PINCODE input field found. Entering PINCODE: %s", mask(pincode))
            pincode_input.clear()
            pincode_input.send_keys(pincode)
            logger.info("PINCODE entered successfully")
            time.sleep(2)
            logger.info("Waiting for PINCODE dropdown to appear...")
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "automatic"))
                )
                logger.info("Parent container '#automatic' found")
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        dropdown_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="automatic"]/div[2]/a'))
                        )
                        logger.info("Dropdown element found on attempt %d", attempt + 1)
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_button)
                        time.sleep(1)
                        logger.info("Scrolled to dropdown element")
                        logger.info("Dropdown - Is displayed: %s", dropdown_button.is_displayed())
                        logger.info("Dropdown - Is enabled: %s", dropdown_button.is_enabled())
                        logger.info("Dropdown - Element text: %s", mask(dropdown_button.text))
                        logger.info("Attempt %d: Clicking dropdown with JavaScript...", attempt + 1)
                        driver.execute_script("arguments[0].click();", dropdown_button)
                        try:
                            WebDriverWait(driver, 10).until(
                                EC.staleness_of(dropdown_button)
                            )
                            logger.info("Dropdown clicked successfully and page changed")
                            break
                        except TimeoutException:
                            try:
                                WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid-item"))
                                )
                                logger.info("Products loaded - dropdown click was successful")
                                break
                            except TimeoutException:
                                logger.warning("Attempt %d: Click may not have registered, retrying...", attempt + 1)
                                continue
                    except StaleElementReferenceException:
                        logger.warning("Attempt %d: Stale element detected, retrying...", attempt + 1)
                        continue
                    except Exception as e:
                        logger.error("Attempt %d: Unexpected error: %s", attempt + 1, str(e))
                        continue
                else:
                    logger.error("Failed to click the dropdown after %d attempts", max_attempts)
                    driver.save_screenshot("pincode_final_failure.png")
                    return []
            except TimeoutException:
                logger.error("Pincode %s is not serviceable or dropdown did not appear", mask(pincode))
                driver.save_screenshot("pincode_dropdown_timeout.png")
                return []
            except Exception as e:
                logger.error("Unexpected error while clicking dropdown: %s", str(e))
                driver.save_screenshot("pincode_error.png")
                return []
        except TimeoutException:
            logger.error("Failed to find PINCODE input field for %s", mask(pincode))
            driver.save_screenshot("pincode_input_timeout.png")
            return []
        logger.info("Waiting for product list to load after PINCODE confirmation...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid-item"))
        )
        logger.info("Product list loaded successfully")
        logger.info("Parsing page source with BeautifulSoup...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_status = []
        logger.info("Finding all product elements...")
        products = soup.select(".product-grid-item")
        logger.info("Found %d product elements with selector '.product-grid-item'", len(products))
        if not products:
            logger.warning("No products found with selector '.product-grid-item'. Dumping page source...")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))
            logger.info("Page source saved to 'page_source.html'")
        for product in products:
            name_elem = product.select_one(".product-grid-name")
            if not name_elem:
                logger.warning("Product name element not found, skipping...")
                continue
            name = name_elem.text.strip()
            logger.info("Processing product: %s", name)
            sold_out_elem = product.select_one("span.stock-indicator-text")
            product_classes = product.get("class", [])
            is_out_of_stock = ("outofstock" in product_classes) or (sold_out_elem and "sold out" in sold_out_elem.text.strip().lower())
            if is_out_of_stock:
                logger.info("Product %s has 'Sold Out' indicator or 'outofstock' class", name)
                product_status.append((name, "Sold Out"))
            else:
                logger.info("Product %s is In Stock", name)
                product_status.append((name, "In Stock"))
        logger.info("Final product status: %s", product_status)
        pincode_cache[pincode] = product_status
        logger.info(f"Cached results for pincode: %s", mask(pincode))
        return product_status
    except Exception as e:
        logger.error("Error in Chrome WebDriver: %s", str(e))
        if driver:
            try:
                driver.save_screenshot("chrome_error.png")
            except:
                pass
        return []
    finally:
        if driver:
            logger.info("Closing WebDriver")
            try:
                driver.quit()
            except Exception as e:
                logger.warning("Error quitting driver: %s", str(e))
        if not os.getenv("GITHUB_ACTIONS"):
            try:
                if 'user_data_dir' in locals() and os.path.exists(user_data_dir):
                    shutil.rmtree(user_data_dir)
                    logger.info("Cleaned up temporary user data directory: %s", user_data_dir)
            except Exception as e:
                logger.warning("Failed to clean up user data directory %s: %s", user_data_dir, str(e))

async def send_telegram_notification_for_user(app, chat_id, pincode, product_names, products):
    if not products:
        logger.info("No products found to notify for chat_id %s", mask(chat_id))
        return
    check_all_products = (len(product_names) == 1 and product_names[0].strip().lower() == "any")
    if check_all_products:
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for 'Any' for chat_id %s: %s", mask(chat_id), in_stock_products)
        if not in_stock_products:
            message = f"None of the Amul Protein items are available for your PINCODE: {pincode}"
            logger.info("All products Sold Out for chat_id %s, sending: %s", mask(chat_id), message)
            await app.bot.send_message(chat_id=chat_id, text=message)
        else:
            message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
            for name, _ in in_stock_products:
                message += f"- {name}\n"
            logger.info("Sending notification for chat_id %s: %s", mask(chat_id), message)
            await app.bot.send_message(chat_id=chat_id, text=message)
    else:
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for specific list for chat_id %s: %s", mask(chat_id), in_stock_products)
        relevant_products = [(name, status) for name, status in in_stock_products if any(p.lower() in name.lower() for p in product_names)]
        if relevant_products:
            message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
            for name, _ in relevant_products:
                message += f"- {name}\n"
            logger.info("Sending notification for chat_id %s: %s", mask(chat_id), mask)
            await app.bot.send_message(chat_id=chat_id, text=message)
        else:
            logger.info("No 'In Stock' product to notify for chat_id %s", mask(chat_id))

async def check_products_for_users():
    logger.info("Starting product check for users")
    global pincode_cache
    pincode_cache.clear()
    logger.info("Pincode cache cleared")
    users_data = read_users_file()
    active_users = [u for u in users_data["users"] if u.get("active", False)]
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    for user in active_users:
        chat_id = user["chat_id"]
        pincode = user["pincode"]
        products_to_check = user["products"]
        logger.info("Checking products for chat_id %s, PINCODE %s", mask(pincode), mask(chat_id))
        product_status = check_product_availability(pincode)
        await send_telegram_notification_for_user(app, chat_id, pincode, products_to_check, product_status)
        logger.info("Finished checking for chat_id %s", mask(pincode))
    logger.info("Completed product check for all users")

async def run_polling_with_scheduled_notifications(app):
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("Running product checks every 15 minutes")
    logger.info("Polling started")
    try:
        while True:
            logger.info("Running product check task...")
            await check_products_for_users()
            logger.info("Finished product check task. Sleeping for 15 minutes...")
            await asyncio.sleep(15 * 60)
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
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpincode", set_pincode))
    app.add_handler(CommandHandler("setproducts", set_products))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(product_callback))
    asyncio.run(run_polling_with_scheduled_notifications(app))

if __name__ == "__main__":
    main()