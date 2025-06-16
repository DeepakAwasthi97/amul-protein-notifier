import os
import json
import base64
import requests
import tempfile
import shutil
import uuid
import psutil
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import logging
import asyncio
from dotenv import load_dotenv

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
# GITHUB_REPO = "DeepakAwasthi97/amul-protein-notifier"
PRIVATE_REPO = os.getenv("PRIVATE_REPO", "DeepakAwasthi97/amul-protein-users")  # Fallback for local testing
GITHUB_BRANCH = "main"

# Check if another instance of the script is already running
def is_already_running():
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == 'python' and 'main.py' in ' '.join(proc.info['cmdline']) and proc.info['pid'] != current_pid:
            return True
    return False

if is_already_running():
    print("Another instance is running. Exiting.")
    sys.exit(0)

# GitHub API helper functions
# def get_file_sha(path):
#     url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
#     headers = {
#         "Authorization": f"token {GH_PAT}",
#         "Accept": "application/vnd.github+json"
#     }
#     response = requests.get(url, headers=headers)
#     if response.status_code == 200:
#         return response.json()["sha"]
#     logger.error("Could not retrieve SHA for %s: Status %d, Response: %s", path, response.status_code, response.text)
#     return None

# def update_users_file(users_data):
#     path = "users.json"
#     sha = get_file_sha(path)
#     if not sha:
#         return False

#     url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
#     headers = {
#         "Authorization": f"token {GH_PAT}",
#         "Accept": "application/vnd.github+json"
#     }
#     content = base64.b64encode(json.dumps(users_data, indent=2).encode()).decode()
#     data = {
#         "message": "Update users.json with new user data",
#         "content": content,
#         "sha": sha,
#         "branch": GITHUB_BRANCH
#     }
#     response = requests.put(url, headers=headers, json=data)
#     if response.status_code != 200:
#         logger.error("Failed to update users.json: Status %d, Response: %s", response.status_code, response.text)
#     return response.status_code == 200

# def read_users_file():
#     url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/users.json?ref={GITHUB_BRANCH}"
#     headers = {
#         "Authorization": f"token {GH_PAT}",
#         "Accept": "application/vnd.github+json"
#     }
#     response = requests.get(url, headers=headers)
#     if response.status_code != 200:
#         logger.error("Failed to read users.json: Status %d, Response: %s", response.status_code, response.text)
#         return {"users": []}
#     content = base64.b64decode(response.json()["content"]).decode()
#     return json.loads(content)

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
    sha = get_file_sha(path)
    if not sha:
        return False

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
    if response.status_code != 200:
        logger.error("Failed to update users.json: Status %d, Response: %s", response.status_code, response.text)
    return response.status_code == 200

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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "Welcome to the Amul Protein Notifier Bot!\n"
        "Use /setpincode PINCODE to set your PIN code (Mandatory).\n"
        "Use /setproducts product1;product2 to set products (this is optional, by default we will show any product which is available for your pincode).\n"
        "Use /stop to stop notifications."
    )

async def set_pincode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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

async def set_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Please provide products. Usage: /setproducts product1;product2")
        return

    products = context.args[0].split(";")
    products = [p.strip() for p in products if p.strip()]
    if not products:
        products = ["Any"]

    users_data = read_users_file()
    users = users_data["users"]
    user = next((u for u in users if u["chat_id"] == str(chat_id)), None)

    if not user:
        await update.message.reply_text("Please set your PIN code first using /setpincode PINCODE")
        return

    user["products"] = products
    if update_users_file(users_data):
        await update.message.reply_text(f"Products set to {', '.join(products)}.")
    else:
        await update.message.reply_text("Failed to update products. Make sure you have provided the product names as per shown in the Amul Protein website.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
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
    url = "https://shop.amul.com/en/browse/protein"
    
    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.69 Safari/537.36")
    
    # Configure based on environment
    # if os.getenv("GITHUB_ACTIONS"):
    #     options.binary_location = "/usr/bin/chrome"
    #     options.add_argument("--single-process")
    #     options.add_argument("--disable-background-networking")
    #     options.add_argument("--disable-default-apps")
    #     options.add_argument("--disable-sync")
    #     options.add_argument("--memory-pressure-off")
    #     options.add_argument("--max_old_space_size=4096")
    #     logger.info("Running in GitHub Actions environment")
        
        # Use Chrome Service for better control
        # service = Service("/usr/bin/chromedriver")
    # else:
    #     options.binary_location = "/snap/bin/chromium"
        # Only use user-data-dir for local development
        # unique_id = str(uuid.uuid4())
        # user_data_dir = tempfile.mkdtemp(prefix=f"chrome_user_data_{unique_id}_")
        # options.add_argument(f"--user-data-dir={user_data_dir}")
        # logger.info("Using temporary user data directory: %s", user_data_dir)
        # service = Service()  # Use default chromedriver path
    
    # driver = None
    try:
        logger.info("Initializing Chrome WebDriver with Service...")
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome WebDriver initialized successfully")
        
        # Set window size for consistent behavior
        driver.set_window_size(1920, 1080)
        logger.info("Navigating to URL: %s", url)
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.info("Page loaded completely")
        
        try:
            logger.info("Locating PINCODE input field...")
            pincode_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="search"]'))
            )
            logger.info("PINCODE input field found. Entering PINCODE: %s", pincode)
            pincode_input.clear()
            pincode_input.send_keys(pincode)
            logger.info("PINCODE entered successfully.")
            
            # Wait a bit for the dropdown to appear
            import time
            time.sleep(2)
            
            logger.info("Waiting for PINCODE dropdown to appear...")
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "automatic"))
                )
                logger.info("Parent container '#automatic' found.")

                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        dropdown_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="automatic"]/div[2]/a'))
                        )
                        logger.info("Dropdown element found on attempt %d.", attempt + 1)

                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_button)
                        time.sleep(1)  # Wait for scroll to complete
                        logger.info("Scrolled to dropdown element.")

                        logger.info("Dropdown - Is displayed: %s", dropdown_button.is_displayed())
                        logger.info("Dropdown - Is enabled: %s", dropdown_button.is_enabled())
                        logger.info("Dropdown - Element text: %s", dropdown_button.text)

                        logger.info("Attempt %d: Clicking dropdown with JavaScript...", attempt + 1)
                        driver.execute_script("arguments[0].click();", dropdown_button)
                        
                        # Wait for the dropdown to disappear or page to change
                        try:
                            WebDriverWait(driver, 10).until(
                                EC.staleness_of(dropdown_button)
                            )
                            logger.info("Dropdown clicked successfully and page changed!")
                            break
                        except TimeoutException:
                            # Alternative: check if page has changed by looking for products
                            try:
                                WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid-item"))
                                )
                                logger.info("Products loaded - dropdown click was successful!")
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
                    logger.error("Failed to click the dropdown after %d attempts.", max_attempts)
                    driver.save_screenshot("pincode_final_failure.png")
                    return []

            except TimeoutException:
                logger.error("Pincode %s is not serviceable or dropdown did not appear.", pincode)
                driver.save_screenshot("pincode_dropdown_timeout.png")
                return []
            except Exception as e:
                logger.error("Unexpected error while clicking dropdown: %s", str(e))
                driver.save_screenshot("pincode_error.png")
                return []
                
        except TimeoutException:
            logger.error("Failed to find PINCODE input field for %s.", pincode)
            driver.save_screenshot("pincode_input_timeout.png")
            return []
        
        logger.info("Waiting for product list to load after PINCODE confirmation...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid-item"))
        )
        logger.info("Product list loaded after PINCODE confirmation.")

        logger.info("Parsing page source with BeautifulSoup...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_status = []
        
        logger.info("Finding all product elements on the page...")
        products = soup.select(".product-grid-item")
        logger.info("Found %d product elements with selector '.product-grid-item'.", len(products))

        if not products:
            logger.warning("No products found with selector '.product-grid-item'. Dumping page source...")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))
            logger.info("Page source saved to 'page_source.html'.")

        for product in products:
            name_elem = product.select_one(".product-grid-name")
            if not name_elem:
                logger.warning("Product name element not found for a product, skipping...")
                continue
            name = name_elem.text.strip()
            logger.info("Processing product: %s", name)

            sold_out_elem = product.select_one("span.stock-indicator-text")
            product_classes = product.get("class", [])
            is_out_of_stock = ("outofstock" in product_classes) or (sold_out_elem and "sold out" in sold_out_elem.text.strip().lower())
            
            if is_out_of_stock:
                logger.info("Product %s has 'Sold Out' indicator or 'outofstock' class.", name)
                product_status.append((name, "Sold Out"))
            else:
                logger.info("Product %s does not have 'Sold Out' indicator or 'outofstock' class, marking as In Stock.", name)
                product_status.append((name, "In Stock"))

        logger.info("Final product status list: %s", product_status)
        return product_status
    
    except Exception as e:
        logger.error("Error initializing or using Chrome WebDriver: %s", str(e))
        if driver:
            try:
                driver.save_screenshot("chrome_error.png")
            except:
                pass
        return []
    
    finally:
        if driver:
            logger.info("Closing WebDriver.")
            try:
                driver.quit()
            except Exception as e:
                logger.warning("Error while quitting driver: %s", str(e))
        
        # Clean up the temporary user data directory (only for local development)
        if not os.getenv("GITHUB_ACTIONS"):
            try:
                if 'user_data_dir' in locals() and os.path.exists(user_data_dir):
                    shutil.rmtree(user_data_dir)
                    logger.info("Cleaned up temporary user data directory: %s", user_data_dir)
            except Exception as e:
                logger.warning("Failed to clean up temporary user data directory %s: %s", user_data_dir, str(e))

# Notification function for all users
async def send_telegram_notification_for_user(app, chat_id, pincode, product_names, products):
    if not products:
        logger.info("No products found to notify about for chat_id %s.", chat_id)
        return

    check_all_products = (len(product_names) == 1 and product_names[0].strip().lower() == "any")
    
    if check_all_products:
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for 'Any' for chat_id %s: %s", chat_id, in_stock_products)

        if not in_stock_products:
            message = f"None of the Amul Protein items are available for your PINCODE: {pincode}"
            logger.info("All products are Sold Out for chat_id %s, sending notification: %s", chat_id, message)
            await app.bot.send_message(chat_id=chat_id, text=message)
        else:
            message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
            for name, _ in in_stock_products:
                message += f"- {name}\n"
            logger.info("Sending Telegram notification for chat_id %s: %s", chat_id, message)
            await app.bot.send_message(chat_id=chat_id, text=message)
    else:
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for specific list for chat_id %s: %s", chat_id, in_stock_products)

        relevant_products = [(name, status) for name, status in in_stock_products if any(p.lower() in name.lower() for p in product_names)]
        if relevant_products:
            message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
            for name, _ in relevant_products:
                message += f"- {name}\n"
            logger.info("Sending Telegram notification for chat_id %s: %s", chat_id, message)
            await app.bot.send_message(chat_id=chat_id, text=message)
        else:
            logger.info("No 'In Stock' products to notify about for chat_id %s.", chat_id)

# Main function for GitHub Actions to check products for all users
async def check_products_for_users():
    users_data = read_users_file()
    active_users = [u for u in users_data["users"] if u.get("active", False)]
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    for user in active_users:
        chat_id = user["chat_id"]
        pincode = user["pincode"]
        products_to_check = user["products"]
        logger.info("Checking products for chat_id %s, PINCODE %s", chat_id, pincode)

        product_status = check_product_availability(pincode)
        await send_telegram_notification_for_user(app, chat_id, pincode, products_to_check, product_status)

def main():
    if os.getenv("GITHUB_ACTIONS"):
        asyncio.run(check_products_for_users())
    else:
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setpincode", set_pincode))
        app.add_handler(CommandHandler("setproducts", set_products))
        app.add_handler(CommandHandler("stop", stop))
        app.run_polling()

if __name__ == "__main__":
    main()