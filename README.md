# 🥛 Amul Protein Notifier Bot (Automation)

**A fully automated, production-hardened Telegram bot that checks product availability for Amul protein products and notifies users every 15 minutes. Built to showcase real-world testability, resilience, and CI/CD practices.**

---

## 🚀 What It Does

- ✅ Scrapes [shop.amul.com](https://shop.amul.com/en/browse/protein) for product availability using **Selenium WebDriver**
- ✅ Allows users to subscribe via Telegram by setting their **PIN code** and **product preferences**
- ✅ Checks availability **every 15 minutes** using **GitHub Actions as a scheduler**
- ✅ Sends real-time notifications to users on Telegram
- ✅ Avoids spamming — only sends relevant, updated info per user
- ✅ Optimized with caching, retry logic, and rotating logs
- ✅ Deploys in a secure and **cost-free 24/7 environment** using GitHub Actions

---

## 🛠️ Tech Stack

| Layer             | Tool                         |
|------------------|------------------------------|
| Notification      | Telegram Bot API             |
| Web Scraping      | Selenium + BeautifulSoup     |
| Bot Framework     | python-telegram-bot v20+     |
| CI/CD             | GitHub Actions (cron-based)  |
| Infra/Hosting     | GitHub-hosted runners        |
| Logging           | Python logging + Rotating Logs |
| Config/Secrets    | Python `dotenv`, GitHub Secrets |
| Data Persistence  | GitHub API + `users.json` in private repo |

---

## 🧠 Why This Project Matters

As a QA/SDET Automation Engineer, this project demonstrates:

- 💡 **CI-driven testing & execution** (Selenium + GitHub Actions)
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
- Product filters: `"Any"` or specific product list
- `/start`, `/stop`, `/setpincode`, `/setproducts` commands handled via polling

### 📆 Scheduler via GitHub Actions
- Runs polling for **5 hours 50 minutes** (to stay under GitHub's 6-hour limit)
- Automatically **restarts every 6 hours**
- Runs `check_products_for_users()` **every 15 minutes** within each job

### 📁 Logs
- Rotating file handler limits logs to **5MB x 3 files**
- `product_check.log` is auto-uploaded to a **private GitHub repo** for secure storage
- Logs include product status, bot actions, and scraping diagnostics

---

## ✅ Setup & Deployment

### 🧪 1. Clone & Install
```bash
git clone https://github.com/your-username/amul-protein-notifier.git
cd amul-protein-notifier
pip install -r requirements.txt
