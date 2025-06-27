import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Secrets and Environment-Specific ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_PAT = os.getenv("GH_PAT")
PRIVATE_REPO = os.getenv("PRIVATE_REPO")
GITHUB_BRANCH = "main"

# --- Concurrency and Retries for Scraper ---
SEMAPHORE_LIMIT = 5  # Max concurrent Selenium instances
MAX_RETRIES = 2      # Retries for failed PIN code checks

# --- File Paths ---
LOG_FILE = "product_check.log"
USERS_FILE = "users.json"
