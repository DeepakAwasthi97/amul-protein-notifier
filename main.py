import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv
import asyncio
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler('product_check.log')  # Output to a file
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PINCODE = os.getenv("PINCODE")
PRODUCT_NAMES = os.getenv("PRODUCT_NAMES").split(";")  # e.g., ["Amul High Protein Paneer, 400 g | Pack of 24", "Amul Kool Protein Milkshake | Chocolate, 180 mL | Pack of 30"] or ["Any"]

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def check_product_availability():
    url = "https://shop.amul.com/en/browse/protein"
    
    # Set up Selenium WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Uncomment for headless mode after testing
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/137.0.7151.69")
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.maximize_window()
        logger.info("Navigating to URL: %s", url)
        driver.get(url)
        
        # Enter PINCODE
        try:
            logger.info("Locating PINCODE input field...")
            pincode_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="search"]'))
            )
            logger.info("PINCODE input field found. Entering PINCODE: %s", PINCODE)
            pincode_input.clear()
            pincode_input.send_keys(PINCODE)
            logger.info("PINCODE entered successfully.")
            
            # Wait for dropdown and click
            logger.info("Waiting for PINCODE dropdown to appear...")
            try:
                # Wait for the parent container to ensure DOM stability
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "automatic"))
                )
                logger.info("Parent container '#automatic' found.")

                # Retry mechanism for clicking the dropdown
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        dropdown_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="automatic"]/div[2]/a'))
                        )
                        logger.info("Dropdown element found on attempt %d.", attempt + 1)

                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_button)
                        logger.info("Scrolled to dropdown element.")

                        # Check visibility and enabled state
                        logger.info("Dropdown - Is displayed: %s", dropdown_button.is_displayed())
                        logger.info("Dropdown - Is enabled: %s", dropdown_button.is_enabled())
                        logger.info("Dropdown - Element tag: %s", dropdown_button.tag_name)
                        logger.info("Dropdown - Element text: %s", dropdown_button.text)
                        logger.info("Dropdown - Element HTML: %s", driver.execute_script("return arguments[0].outerHTML;", dropdown_button))

                        # Attempt click with ActionChains
                        logger.info("Attempt %d: Clicking dropdown with ActionChains...", attempt + 1)
                        ActionChains(driver).move_to_element(dropdown_button).click().perform()

                        # Verify the click worked (e.g., check if dropdown disappears)
                        WebDriverWait(driver, 5).until(
                            EC.staleness_of(dropdown_button)
                        )
                        logger.info("Dropdown clicked successfully and disappeared!")
                        break  # Exit retry loop on success

                    except StaleElementReferenceException:
                        logger.warning("Attempt %d: Stale element detected, retrying...", attempt + 1)
                        continue
                    except ElementClickInterceptedException:
                        logger.warning("Attempt %d: Click intercepted, trying JavaScript click...", attempt + 1)
                        # Fallback to JavaScript click
                        driver.execute_script("arguments[0].click();", dropdown_button)
                        logger.info("JavaScript click executed.")
                        # Verify the click
                        WebDriverWait(driver, 5).until(
                            EC.staleness_of(dropdown_button)
                        )
                        logger.info("Dropdown clicked successfully via JavaScript!")
                        break
                    except TimeoutException as te:
                        logger.error("Timeout during click verification: %s", str(te))
                        driver.save_screenshot(f"pincode_timeout_attempt_{attempt + 1}.png")
                        continue

                else:
                    logger.error("Failed to click the dropdown after %d attempts.", max_attempts)
                    driver.save_screenshot("pincode_final_failure.png")
                    return []

            except TimeoutException:
                logger.error("Pincode %s is not serviceable or dropdown did not appear.", PINCODE)
                driver.save_screenshot("pincode_dropdown_timeout.png")
                return []
            except Exception as e:
                logger.error("Unexpected error while clicking dropdown: %s", str(e))
                driver.save_screenshot("pincode_error.png")
                return []
                
        except TimeoutException:
            logger.error("Failed to find PINCODE input field for %s.", PINCODE)
            driver.save_screenshot("pincode_input_timeout.png")
            return []
        
        # Wait for the product list to load after PINCODE confirmation
        logger.info("Waiting for product list to load after PINCODE confirmation...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-grid-item"))
        )
        logger.info("Product list loaded after PINCODE confirmation.")

        # Get page source and parse with BeautifulSoup
        logger.info("Parsing page source with BeautifulSoup...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_status = []
        
        # Find product elements
        logger.info("Finding all product elements on the page...")
        products = soup.select(".product-grid-item")
        logger.info("Found %d product elements with selector '.product-grid-item'.", len(products))

        # Debugging: Log the page source if no products are found
        if not products:
            logger.warning("No products found with selector '.product-grid-item'. Dumping page source for debugging...")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))
            logger.info("Page source saved to 'page_source.html'.")

        # Check if PRODUCT_NAMES is set to ["Any"]
        check_all_products = (len(PRODUCT_NAMES) == 1 and PRODUCT_NAMES[0].strip().lower() == "any")
        logger.info("Check all products: %s", check_all_products)

        for product in products:
            # Extract product name
            name_elem = product.select_one(".product-grid-name")
            if not name_elem:
                logger.warning("Product name element not found for a product, skipping...")
                continue
            name = name_elem.text.strip()
            logger.info("Processing product: %s", name)

            # Determine if we should process this product
            if check_all_products or any(p.lower() in name.lower() for p in PRODUCT_NAMES):
                logger.info("Product %s matches criteria, checking stock status...", name)

                # Check for "Sold Out" indicator within this product
                sold_out_elem = product.select_one("span.stock-indicator-text")
                # Additional check: Look for "outofstock" in the product's class list
                product_classes = product.get("class", [])
                is_out_of_stock = ("outofstock" in product_classes) or (sold_out_elem and "sold out" in sold_out_elem.text.strip().lower())
                
                if is_out_of_stock:
                    logger.info("Product %s has 'Sold Out' indicator or 'outofstock' class.", name)
                    product_status.append((name, "Sold Out"))
                else:
                    logger.info("Product %s does not have 'Sold Out' indicator or 'outofstock' class, marking as In Stock.", name)
                    product_status.append((name, "In Stock"))

        # Log the final list of products and their status
        logger.info("Final product status list: %s", product_status)
        return product_status
    
    finally:
        logger.info("Closing WebDriver.")
        driver.quit()

async def send_telegram_notification(products):
    if not products:
        logger.info("No products found to notify about.")
        return

    # Check if we're looking for all products (PRODUCT_NAMES = ["Any"])
    check_all_products = (len(PRODUCT_NAMES) == 1 and PRODUCT_NAMES[0].strip().lower() == "any")
    
    if check_all_products:
        # If checking all products, notify about all that are "In Stock"
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for 'Any': %s", in_stock_products)

        if not in_stock_products:
            # If all products are "Sold Out", send the special message
            message = f"None of the Amul Protein items are available for your PINCODE: {PINCODE}"
            logger.info("All products are Sold Out, sending notification: %s", message)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        else:
            # Notify about all "In Stock" products
            message = f"Available Amul Protein Products for PINCODE {PINCODE}:\n\n"
            for name, _ in in_stock_products:
                message += f"- {name}\n"
            logger.info("Sending Telegram notification for available products: %s", message)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    else:
        # If checking specific products, notify only for those that are "In Stock"
        in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
        logger.info("In Stock products for specific list: %s", in_stock_products)

        if in_stock_products:
            message = f"Available Amul Protein Products for PINCODE {PINCODE}:\n\n"
            for name, _ in in_stock_products:
                message += f"- {name}\n"
            logger.info("Sending Telegram notification for available products: %s", message)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        else:
            logger.info("No 'In Stock' products to notify about.")

def main():
    logger.info("Starting product availability check...")
    product_status = check_product_availability()
    asyncio.run(send_telegram_notification(product_status))
    logger.info("Product check completed.")

if __name__ == "__main__":
    main()