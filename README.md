# iPhoneStockChecker
Check when any given iPhone is in stock in any Apple store automatically and notify users via Telegram or Email.

## Features
- Monitors stock across multiple stores via Apple Retail API.
- Fetches target models dynamically from a GitHub Gist.
- Alerts via Telegram and Email (SMTP).

## Configuration
1. **`config.json`**: Set your `country_code`, `zip_code`, and `stores`.

Customise your search parameters in the config.json file for email notifications. 

Customise your own GitHub Gist to customise Telegram notifications. You'll find mine at the end of the store_checker.py file to be used as a template.

2. **Environment Variables**: Add your `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GMAIL_USER`, and `GMAIL_APP_PASSWORD` to your AWS Lambda settings or directly into the file (if you're okay with hard-coding)

## Dependencies
- `requests`
- `crayons`
