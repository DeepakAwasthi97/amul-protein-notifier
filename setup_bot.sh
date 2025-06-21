#!/bin/bash

# Exit on any error
set -e

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a setup_bot.log
}

# Check if running on Ubuntu/Debian
if ! command -v apt >/dev/null 2>&1; then
    log "❌ This script requires an Ubuntu/Debian-based system with apt."
    exit 1
fi

# Check for sudo privileges
if ! sudo -n true 2>/dev/null; then
    log "❌ This script requires sudo privileges."
    exit 1
fi

# Check architecture
if [[ "$(uname -m)" != "x86_64" ]]; then
    log "⚠️ Warning: Script assumes AMD64 architecture. Non-AMD64 systems may fail."
fi

# Check Python version (minimum 3.8)
if ! command -v python3 >/dev/null 2>&1; then
    log "❌ Python3 not found. Installing..."
    sudo apt install -y python3
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
IFS='.' read -r MAJOR MINOR PATCH <<< "${PYTHON_VERSION}"
if [[ ${MAJOR} -lt 3 || (${MAJOR} -eq 3 && ${MINOR} -lt 8) ]]; then
    log "❌ Python 3.8 or higher required. Found: ${PYTHON_VERSION}"
    exit 1
fi
log "✅ Python version ${PYTHON_VERSION} is sufficient"

log "🔧 Updating system packages..."
sudo apt update && sudo apt upgrade -y

log "📦 Installing core dependencies..."
sudo apt install -y python3-pip python3-venv git screen curl wget unzip \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils libgbm1 \
    libu2f-udev libpango-1.0-0 libcairo2

# Check if Google Chrome is installed
if ! command -v google-chrome >/dev/null 2>&1; then
    log "🧩 Installing Google Chrome..."
    wget -O google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    rm google-chrome-stable_current_amd64.deb
else
    log "✅ Google Chrome already installed"
fi

# Check if ChromeDriver is installed
if ! command -v chromedriver >/dev/null 2>&1; then
    log "🧩 Installing ChromeDriver..."
    CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+\.\d+')
    log "Detected Chrome version: ${CHROME_VERSION}"
    CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"
    log "Attempting to download ChromeDriver from: ${CHROMEDRIVER_URL}"
    if ! wget -O chromedriver.zip "${CHROMEDRIVER_URL}"; then
        log "⚠️ Failed to download ChromeDriver for version ${CHROME_VERSION}. Trying fallback version..."
        FALLBACK_VERSION="137.0.7151.68"
        CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${FALLBACK_VERSION}/linux64/chromedriver-linux64.zip"
        log "Attempting fallback download from: ${CHROMEDRIVER_URL}"
        if ! wget -O chromedriver.zip "${CHROMEDRIVER_URL}"; then
            log "❌ Failed to download ChromeDriver for fallback version ${FALLBACK_VERSION}. Check version compatibility."
            exit 1
        fi
    fi
    unzip chromedriver.zip chromedriver-linux64/chromedriver
    sudo mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
    sudo chmod +x /usr/local/bin/chromedriver
    rm -rf chromedriver.zip chromedriver-linux64
    log "✅ ChromeDriver installed for Chrome version ${CHROME_VERSION}"
else
    log "✅ ChromeDriver already installed"
fi

# Check if repository exists
if [[ ! -d amul-protein-notifier ]]; then
    log "🐍 Cloning bot repository..."
    git clone https://github.com/DeepakAwasthi97/amul-protein-notifier.git || {
        log "❌ Failed to clone repository. Ensure it’s accessible (public or correct credentials)."
        exit 1
    }
else
    log "✅ Repository already cloned"
fi
cd amul-protein-notifier || {
    log "❌ Failed to enter repository directory."
    exit 1
}

# Check if virtual environment exists
if [[ ! -d venv ]]; then
    log "📁 Setting up virtual environment..."
    python3 -m venv venv || {
        log "❌ Failed to create virtual environment."
        exit 1
    }
else
    log "✅ Virtual environment already exists"
fi
source venv/bin/activate

# Install Python dependencies
log "📦 Installing Python dependencies..."
pip install --upgrade pip
if [[ ! -f requirements.txt ]]; then
    log "❌ requirements.txt not found in repository."
    exit 1
}
pip install -r requirements.txt || {
    log "❌ Failed to install Python dependencies. Check requirements.txt."
    exit 1
}

# Check if .env exists
if [[ ! -f .env ]]; then
    log "🛡️ Creating .env file..."
    cat <<EOF > .env
TELEGRAM_BOT_TOKEN=
GH_PAT=
PRIVATE_REPO=
EOF
    chmod 600 .env
    log "➡️ Please edit .env file now to insert your secrets:"
    nano .env
else
    log "✅ .env file already exists. Edit with 'nano .env' if needed."
fi

# Validate .env file
if ! grep -q "^TELEGRAM_BOT_TOKEN=[^ ]" .env || ! grep -q "^PRIVATE_REPO=[^ ]" .env || ! grep -q "^GH_PAT=[^ ]" .env; then
    log "⚠️ Warning: TELEGRAM_BOT_TOKEN, GH_PAT, or PRIVATE_REPO in .env is empty. Bot may fail to run."
fi

log "✅ Setup Complete. You can run the bot manually with:"
log "source venv/bin/activate && python main.py"

# Offer to start bot in screen session
read -p "Would you like to start the bot now in a screen session? (y/n): " START_BOT
if [[ "${START_BOT}" =~ ^[Yy]$ ]]; then
    log "🚀 Starting bot in screen session..."
    screen -S amul-bot bash -c "source venv/bin/activate && python main.py; exec bash"
    log "✅ Bot started in screen session 'amul-bot'. Reattach with: screen -r amul-bot"
fi