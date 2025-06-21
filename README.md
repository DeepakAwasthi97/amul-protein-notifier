# 🥛 Amul Protein Notifier Bot (Automation)

**A fully automated, production-hardened Telegram bot that checks product availability for Amul protein products and notifies users every 15 minutes. Built to showcase real-world testability, resilience, and CI/CD practices.**

---

## 🚀 What It Does

- ✅ Scrapes [shop.amul.com](https://shop.amul.com/en/browse/protein) for product availability using **Selenium WebDriver**
- ✅ Allows users to subscribe via Telegram by setting their **PIN code** and **product preferences**
- ✅ Checks availability **every 15 minutes** using **GitHub Actions as a scheduler/Google Compute Engine API**
- ✅ Sends real-time notifications to users on Telegram
- ✅ Avoids spamming — only sends relevant, updated info per user
- ✅ Optimized with caching, retry logic.
- ✅ Deploys in a secure and **cost-free 24/7 environment** using GitHub Actions/GCP free-tier

---

## 🛠️ Tech Stack

| Layer             | Tool                         |
|-------------------|------------------------------|
| Notification      | Telegram Bot API             |
| Web Scraping      | Selenium + BeautifulSoup     |
| Bot Framework     | python-telegram-bot v20+     |
| CI/CD             | GitHub Actions / GCE VM      |
| Infra/Hosting     | GCE VM / GitHub Runners      |
| Logging           | Python logging               |
| Config/Secrets    | Python`dotenv`,GitHub Secrets|
| Data Persistence  | Private GitHub Repo          |

---

## 🧠 Why This Project Matters

As a QA/SDET Automation Engineer, this project demonstrates:

- 💡 **CI-driven testing & execution** (Selenium + GitHub Actions/Google cloud platform)
- 🔁 **Idempotent job design** (no side effects on rerun)
- 📡 **Live system monitoring**
- 🧪 **End-to-end automation** from data source to user notification
- 🛡️ **Secure DevOps** using encrypted GitHub Secrets
- 🧩 **Custom state management** with GitHub API instead of databases

---

## 📦 Features Overview

### 🔍 Availability Checks
- Headless Chrome-based Selenium scraper
- Resilient to slow-loading UIs and partial page loads
- Logs DOM changes, fallback behavior, and takes screenshots on failure

### 🔔 Telegram Notifications
- Users receive messages when subscribed products become available
- Product filters: `"Any of the available product"` or specific product list if specified
- `/start`, `/stop`, `/setpincode`, `/setproducts` commands handled via polling

### 📆 Scheduler via GitHub Actions/GCP
- On github ,Runs polling for **5 hours 50 minutes** (to stay under GitHub's 6-hour limit)
- Automatically **restarts every 6 hours**
- Runs `check_products_for_users()` **every 15 minutes** within each job
- GCP : Now handled all of it within using google cloud VM E2-micro for just 600rs per month and the bot runs 24/7

### 📁 Logs
- `product_check.log` keeps the logs which helps in debugging whenever something fails.
- Logs include product status, bot actions, and scraping diagnostics

---

## ✅ Setup & Deployment

### 🧪 1. Prerequisites
- Ubuntu-based system (tested on 20.04/22.04).
- Google Cloud account for GCE VM (optional for persistent hosting).
- GitHub account with Personal Access Token (GH_PAT) for private repo access.
- When prompted, add your Telegram bot token, GitHub PAT, and private repo details

### 🧪 2. Clone & Install
```bash
git clone https://github.com/DeepakAwasthi97/amul-protein-notifier.git
cd amul-protein-notifier
chmod +x setup_bot.sh
./setup_bot.sh
```
## 📬 Contact

Built by Deepak Awasthi. Reach out for collaboration or any project related ideas
