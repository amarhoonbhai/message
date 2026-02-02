# VPS Deployment Guide

Complete guide to deploy Group Message Scheduler on a VPS (Ubuntu/Debian).

## Prerequisites

- VPS with Ubuntu 20.04+ or Debian 11+
- SSH access to your server
- Domain (optional, for webhooks)

---

## Step 1: Connect to Your VPS

```bash
ssh root@your_vps_ip
```

---

## Step 2: System Update & Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python and Git
apt install python3 python3-pip python3-venv git screen -y
```

---

## Step 3: Clone the Repository

```bash
# Create app directory
mkdir -p /opt/message-scheduler
cd /opt/message-scheduler

# Clone from GitHub
git clone https://github.com/amarhoonbhai/message.git .
```

---

## Step 4: Setup Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 5: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Fill in your values:**
```
MAIN_BOT_TOKEN=your_main_bot_token
LOGIN_BOT_TOKEN=your_login_bot_token
MAIN_BOT_USERNAME=YourMainBot
LOGIN_BOT_USERNAME=spinifyLoginbot
API_ID=your_api_id
API_HASH=your_api_hash
OWNER_ID=your_telegram_user_id
MONGODB_URI=mongodb+srv://...
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

---

## Step 6: Run with Screen (Simple Method)

### Start Main Bot
```bash
screen -S main_bot
source venv/bin/activate
python -m main_bot.bot
# Press Ctrl+A then D to detach
```

### Start Login Bot
```bash
screen -S login_bot
source venv/bin/activate
python -m login_bot.bot
# Press Ctrl+A then D to detach
```

### Start Worker
```bash
screen -S worker
source venv/bin/activate
python -m worker.worker
# Press Ctrl+A then D to detach
```

### Reattach to screens
```bash
screen -r main_bot   # View main bot logs
screen -r login_bot  # View login bot logs
screen -r worker     # View worker logs
```

---

## Step 7: Run with Systemd (Production Method)

### Create systemd service files

**Main Bot Service:**
```bash
sudo nano /etc/systemd/system/main-bot.service
```

```ini
[Unit]
Description=Group Message Scheduler - Main Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/message-scheduler
Environment=PATH=/opt/message-scheduler/venv/bin
ExecStart=/opt/message-scheduler/venv/bin/python -m main_bot.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Login Bot Service:**
```bash
sudo nano /etc/systemd/system/login-bot.service
```

```ini
[Unit]
Description=Group Message Scheduler - Login Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/message-scheduler
Environment=PATH=/opt/message-scheduler/venv/bin
ExecStart=/opt/message-scheduler/venv/bin/python -m login_bot.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Worker Service:**
```bash
sudo nano /etc/systemd/system/worker.service
```

```ini
[Unit]
Description=Group Message Scheduler - Worker
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/message-scheduler
Environment=PATH=/opt/message-scheduler/venv/bin
ExecStart=/opt/message-scheduler/venv/bin/python -m worker.worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable main-bot login-bot worker

# Start all services
sudo systemctl start main-bot login-bot worker

# Check status
sudo systemctl status main-bot
sudo systemctl status login-bot
sudo systemctl status worker
```

### Useful Commands

```bash
# View logs
journalctl -u main-bot -f
journalctl -u login-bot -f
journalctl -u worker -f

# Restart services
sudo systemctl restart main-bot login-bot worker

# Stop services
sudo systemctl stop main-bot login-bot worker
```

---

## Step 8: Update from GitHub

```bash
cd /opt/message-scheduler

# Pull latest changes
git pull origin main

# Restart services
sudo systemctl restart main-bot login-bot worker
```

---

## Troubleshooting

### Check if services are running
```bash
systemctl status main-bot login-bot worker
```

### View recent logs
```bash
journalctl -u main-bot --since "1 hour ago"
```

### Check Python errors
```bash
cd /opt/message-scheduler
source venv/bin/activate
python -m main_bot.bot  # Run manually to see errors
```

### MongoDB connection issues
- Verify your MongoDB URI is correct
- Check if your VPS IP is whitelisted in MongoDB Atlas Network Access

### Telegram API issues
- Verify API_ID and API_HASH are correct
- Ensure bot tokens are valid

---

## Quick Start Script

Create a quick start script:

```bash
nano /opt/message-scheduler/start.sh
```

```bash
#!/bin/bash
cd /opt/message-scheduler
source venv/bin/activate

echo "Starting all services..."
sudo systemctl start main-bot login-bot worker

echo "Services started! Checking status..."
sudo systemctl status main-bot login-bot worker --no-pager
```

```bash
chmod +x /opt/message-scheduler/start.sh
```

---

## Security Recommendations

1. **Use a non-root user** for running services
2. **Enable UFW firewall**: `ufw enable && ufw allow ssh`
3. **Keep system updated**: `apt update && apt upgrade -y`
4. **Use fail2ban**: `apt install fail2ban -y`
5. **Secure MongoDB** with IP whitelisting in Atlas

---

## Support

For issues, join [@PHilobots](https://t.me/PHilobots) on Telegram.
