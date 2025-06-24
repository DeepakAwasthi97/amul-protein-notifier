import asyncio
import shutil
import os
import time
import signal
from telegram.ext import Application
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import PRODUCTS, PRODUCT_NAME_MAP, TELEGRAM_BOT_TOKEN, setup_logging, mask, is_already_running, read_users_file

logger = setup_logging()
pincode_cache = {}

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
    user_data_dir = None
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
            logger.error("Failed to find PINCODE input field for PINCODE: %s", mask(pincode))
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
        logger.info(f"Cached results for pincode: {mask(pincode)}")
        return product_status
    except Exception as e:
        logger.error("Error checking pincode %s: %s", mask(pincode), str(e))
        if driver:
            try:
                driver.save_screenshot("chrome_error.png")
            except Exception:
                logger.warning("Failed to save screenshot")
        return []
    finally:
        if driver:
            logger.info("Closing WebDriver for pincode %s", mask(pincode))
            try:
                def quit_driver():
                    driver.quit()
                from threading import Thread
                t = Thread(target=quit_driver)
                t.start()
                t.join(timeout=5)
                if t.is_alive():
                    logger.error("WebDriver quit timed out for pincode %s", mask(pincode))
            except Exception as e:
                logger.warning("Error quitting driver for pincode %s: %s", mask(pincode), str(e))
        if not os.getenv("GITHUB_ACTIONS") and user_data_dir and os.path.exists(user_data_dir):
            try:
                shutil.rmtree(user_data_dir)
                logger.info("Cleaned up temporary user data directory: %s", user_data_dir)
            except Exception as e:
                logger.warning("Failed to clean up user data directory %s: %s", user_data_dir, str(e))

async def send_telegram_notification_for_user(app, chat_id, pincode, product_names, products):
    try:
        async with asyncio.timeout(10):
            if not products:
                logger.info("No products found to notify for chat_id %s", mask(chat_id))
                return
            check_all_products = len(product_names) == 1 and product_names[0].strip().lower() == "any"
            if check_all_products:
                in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
                logger.info("In Stock products for 'Any' for chat_id %s: %s", mask(chat_id), in_stock_products)
                if not in_stock_products:
                    message = f"None of the Amul Protein items are available for your PINCODE: {pincode}"
                    logger.info("All products Sold Out for chat_id %s, PINCODE %s", mask(chat_id), mask(pincode))
                else:
                    message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
                    for name, _ in in_stock_products:
                        short_name = PRODUCT_NAME_MAP.get(name, name)
                        message += f"- {short_name}\n"
                    logger.info("Sending notification for chat_id %s: %s", mask(chat_id), message)
                    await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            else:
                in_stock_products = [(name, status) for name, status in products if status == "In Stock"]
                logger.info("In Stock products for specific list for chat_id %s: %s", mask(chat_id), in_stock_products)
                relevant_products = [(name, status) for name, status in in_stock_products if any(p.lower() in name.lower() for p in product_names)]
                if relevant_products:
                    message = f"Available Amul Protein Products for PINCODE {pincode}:\n\n"
                    for name, _ in relevant_products:
                        short_name = PRODUCT_NAME_MAP.get(name, name)
                        message += f"- {short_name}\n"
                    logger.info("Sending notification for chat_id %s: %s", mask(chat_id), message)
                    await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
                else:
                    logger.info("No 'In Stock' product to notify for chat_id %s", mask(chat_id))
    except asyncio.TimeoutError:
        logger.error("Timeout sending notification to chat_id %s for pincode %s", mask(chat_id), mask(pincode))
    except Exception as e:
        logger.error("Error sending notification to chat_id %s: %s", mask(chat_id), str(e))

async def check_products_for_users():
    logger.info("Starting product check for all users")
    global pincode_cache
    pincode_cache.clear()
    logger.info("Pincode cache cleared")
    
    users_data = read_users_file()
    active_users = [u for u in users_data["users"] if u.get("active", False)]
    if not active_users:
        logger.info("No active users to check")
        return

    # Initialize Telegram app once and keep it alive
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    await app.initialize()
    
    try:
        # Group users by pincode
        pincode_groups = {}
        for user in active_users:
            pincode = user.get("pincode")
            if not pincode:
                logger.error("Skipping user with missing pincode: %s", user)
                continue
            if pincode not in pincode_groups:
                pincode_groups[pincode] = []
            pincode_groups[pincode].append(user)

        # Create semaphore to limit concurrent product checks
        semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent checks
        
        async def process_single_pincode(pincode, users):
            async with semaphore:
                logger.info("Starting process for pincode %s with %d users", mask(pincode), len(users))
                
                # Run product check in thread pool
                loop = asyncio.get_event_loop()
                try:
                    product_status = await loop.run_in_executor(
                        None, check_product_availability, pincode
                    )
                    logger.info("Product check completed for pincode %s", mask(pincode))
                    
                    # Immediately send notifications for this pincode
                    notification_tasks = []
                    for user in users:
                        chat_id = user.get("chat_id")
                        products_to_check = user.get("products")
                        logger.info("Creating notification task for chat_id %s, pincode %s", mask(chat_id), mask(pincode))
                        
                        task = asyncio.create_task(
                            send_telegram_notification_for_user(
                                app, chat_id, pincode, products_to_check, product_status
                            )
                        )
                        notification_tasks.append(task)
                    
                    # Wait for all notifications for this pincode to complete
                    if notification_tasks:
                        await asyncio.gather(*notification_tasks, return_exceptions=True)
                        logger.info("All notifications completed for pincode %s", mask(pincode))
                    
                except Exception as e:
                    logger.error("Error processing pincode %s: %s", mask(pincode), str(e))
                finally:
                    logger.info("Finished processing pincode %s", mask(pincode))

        # Process all pincodes concurrently
        tasks = [
            asyncio.create_task(process_single_pincode(pincode, users))
            for pincode, users in pincode_groups.items()
        ]
        
        if tasks:
            logger.info("Starting concurrent processing of %d pincodes", len(tasks))
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("All pincode processing completed")
        
    except Exception as e:
        logger.error("Error in main processing: %s", str(e))
        raise
    finally:
        # Clean shutdown
        logger.info("Shutting down application...")
        try:
            await app.shutdown()
            logger.info("Application shutdown completed")
        except Exception as e:
            logger.error("Error shutting down application: %s", str(e))

    logger.info("Completed product check for all users")

def main():
    # Fix Windows console encoding for emoji support
    import sys
    if sys.platform == "win32":
        try:
            # Try to set console to UTF-8
            import os
            os.system("chcp 65001 >nul 2>&1")
            # Set stdout encoding
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass  # Fallback silently if encoding setup fails
    
    logger.info("Starting product check script")
    
    def handle_shutdown(signum, frame):
        logger.info("Received shutdown signal, exiting...")
        raise KeyboardInterrupt
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        if is_already_running("check_products.py"):
            logger.error("Another instance of check_products.py is already running. Exiting...")
            raise SystemExit(1)
        
        asyncio.run(check_products_for_users())
        
    except KeyboardInterrupt:
        logger.info("Main process interrupted, exiting cleanly...")
        raise SystemExit(0)
    except Exception as e:
        logger.error("Unexpected error in main: %s", str(e))
        raise SystemExit(1)

if __name__ == "__main__":
    main()