Amul Protein Availability Notifier
Checks https://shop.amul.com/en/browse/protein every 5 minutes for product availability based on a pincode and sends Telegram notifications when products are in stock.
Setup

Clone the repository.
Create a Telegram bot via @BotFather and get the bot token.
Create a Telegram channel/group, add the bot as an admin, and get the chat ID via @GetIDsBot.
Add secrets to GitHub (Settings > Secrets and variables > Actions):
TELEGRAM_BOT_TOKEN: Your bot token.
TELEGRAM_CHAT_ID: Your channel/group chat ID.
PINCODE: Your area’s pincode (e.g., 400001).
PRODUCT_NAMES: Semicolan-separated product names (e.g., Amul Pro Whey Protein Drink,Amul Protein Lassi).