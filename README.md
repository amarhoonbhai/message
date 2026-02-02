# Group Message Scheduler

A Telegram system that auto-forwards Saved Messages to up to 15 groups with safe delays and fixed night mode.

## Features

- ✨ **Main Bot** - Dashboard, Plans, Referral, Admin
- 🔐 **Login Bot** - Account linking via OTP + 2FA using Telethon
- 🚀 **Worker Service** - Auto-forward with safety rules

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### 3. Run the Bots

**Windows:**
```bash
scripts\start_all.bat
```

**Linux:**
```bash
chmod +x scripts/start_all.sh
./scripts/start_all.sh
```

Or run each component separately:

```bash
# Terminal 1 - Main Bot
python -m main_bot.bot

# Terminal 2 - Login Bot
python -m login_bot.bot

# Terminal 3 - Worker
python -m worker.worker
```

## Configuration

| Variable | Description |
|----------|-------------|
| `MAIN_BOT_TOKEN` | Main Bot API token from @BotFather |
| `LOGIN_BOT_TOKEN` | Login Bot API token |
| `MAIN_BOT_USERNAME` | Main Bot username (without @) |
| `LOGIN_BOT_USERNAME` | Login Bot username |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash |
| `OWNER_ID` | Your Telegram user ID |
| `MONGODB_URI` | MongoDB Atlas connection string |

## Scheduling Rules

| Rule | Value |
|------|-------|
| Max groups per user | 15 |
| Group gap | 90 seconds |
| Message gap | 500 seconds |
| Min user interval | 20 minutes |
| Night mode | 00:00–06:00 IST (fixed) |

## License

MIT
