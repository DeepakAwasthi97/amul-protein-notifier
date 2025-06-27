import base64
import json
import logging
import os
import psutil
import requests

from config import (
    LOG_FILE,
    USERS_FILE,
    PRIVATE_REPO,
    GITHUB_BRANCH,
    GH_PAT,
)

# Constants
PRODUCTS = [
    "Any",
    "Amul Kool Protein Milkshake | Chocolate, 180 mL | Pack of 30",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 8",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 30",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 8",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 30",
    "Amul Kool Protein Milkshake | Vanilla, 180 mL | Pack of 8",
    "Amul Kool Protein Milkshake | Vanilla, 180 mL | Pack of 30",
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
    "Amul Chocolate Whey Protein, 34 g | Pack of 60 sachets",
]

PRODUCT_NAME_MAP = {
    "Any": "❗ Any of the products from the list",
    "Amul Kool Protein Milkshake | Chocolate, 180 mL | Pack of 30": "🍫🍫Chocolate Milkshake 180mL | Pack of 30",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 8": "☕ Coffee Milkshake 180mL | Pack of 8",
    "Amul Kool Protein Milkshake | Arabica Coffee, 180 mL | Pack of 30": "☕☕ Coffee Milkshake 180mL | Pack of 30",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 8": "🌸 Kesar Milkshake 180mL | Pack of 8",
    "Amul Kool Protein Milkshake | Kesar, 180 mL | Pack of 30": "🌸🌸 Kesar Milkshake 180mL | Pack of 30",
    "Amul Kool Protein Milkshake | Vanilla, 180 mL | Pack of 8": "🍨 Vanilla Milkshake 180mL | Pack of 8",
    "Amul Kool Protein Milkshake | Vanilla, 180 mL | Pack of 30": "🍨🍨 Vanilla Milkshake 180mL | Pack of 30",
    "Amul High Protein Blueberry Shake, 200 mL | Pack of 30": "🫐🫐 Blueberry Shake 200mL | Pack of 30",
    "Amul High Protein Plain Lassi, 200 mL | Pack of 30": "🥛🥛 Plain Lassi 200mL | Pack of 30",
    "Amul High Protein Rose Lassi, 200 mL | Pack of 30": "🌹🌹 Rose Lassi 200mL | Pack of 30",
    "Amul High Protein Buttermilk, 200 mL | Pack of 30": "🥛🥛 Buttermilk 200mL | Pack of 30",
    "Amul High Protein Milk, 250 mL | Pack of 8": "🥛 Milk 250mL | Pack of 8",
    "Amul High Protein Milk, 250 mL | Pack of 32": "🥛🥛 Milk 250mL | Pack of 32",
    "Amul High Protein Paneer, 400 g | Pack of 24": "🧀🧀 Paneer 400g | Pack of 24",
    "Amul High Protein Paneer, 400 g | Pack of 2": "🧀 Paneer 400g | Pack of 2",
    "Amul Whey Protein Gift Pack, 32 g | Pack of 10 sachets": "💪 Whey Protein 32g | Pack of 10 sachets",
    "Amul Whey Protein, 32 g | Pack of 30 Sachets": "💪💪 Whey Protein 32g | Pack of 30 Sachets",
    "Amul Whey Protein Pack, 32 g | Pack of 60 Sachets": "💪💪💪 Whey Protein 32g | Pack of 60 Sachets",
    "Amul Chocolate Whey Protein Gift Pack, 34 g | Pack of 10 sachets": "🍫 Chocolate Whey 34g | Pack of 10 sachets",
    "Amul Chocolate Whey Protein, 34 g | Pack of 30 sachets": "🍫🍫 Chocolate Whey 34g | Pack of 30 sachets",
    "Amul Chocolate Whey Protein, 34 g | Pack of 60 sachets": "🍫🍫🍫 Chocolate Whey 34g | Pack of 60 sachets",
}

SHORT_TO_FULL = {v: k for k, v in PRODUCT_NAME_MAP.items()}

# Logging setup
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE),
        ],
    )
    return logging.getLogger(__name__)

# Helper functions
def mask(value, visible=2):
    value = str(value)
    if len(value) <= visible * 2:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - 2 * visible) + value[-visible:]

def is_already_running(script_name):
    logger = logging.getLogger(__name__)
    logger.info("Checking for running instances of %s", script_name)
    current_pid = os.getpid()
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if (
                    proc.info["name"].lower() == "python"
                    and proc.info["cmdline"]
                    and script_name in " ".join(proc.info["cmdline"]).lower()
                    and proc.info["pid"] != current_pid
                ):
                    logger.info("Found another running instance with PID %d", proc.info["pid"])
                    return True
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                logger.warning("Could not access process %d: %s", proc.info["pid"], str(e))
                continue
    except Exception as e:
        logger.error("Error checking running processes: %s", str(e))
        return False
    logger.info("No other running instances found")
    return False

def get_file_sha(path):
    logger = logging.getLogger(__name__)
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["sha"]
    logger.error(
        "Could not retrieve SHA for %s: Status %d, Response: %s",
        path,
        response.status_code,
        response.text,
    )
    return None

def read_users_file():
    logger = logging.getLogger(__name__)
    url = f"https://api.github.com/repos/{PRIVATE_REPO}/contents/{USERS_FILE}?ref={GITHUB_BRANCH}"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(
            "Failed to read users.json: Status %d, Response: %s",
            response.status_code,
            response.text,
        )
        return {"users": []}
    content = base64.b64decode(response.json()["content"]).decode()
    return json.loads(content)
