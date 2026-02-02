#!/bin/bash

echo "Stopping all services..."

# Read PIDs from files
if [ -f logs/main_bot.pid ]; then
    MAIN_BOT_PID=$(cat logs/main_bot.pid)
    kill $MAIN_BOT_PID 2>/dev/null && echo "Stopped Main Bot (PID: $MAIN_BOT_PID)"
fi

if [ -f logs/login_bot.pid ]; then
    LOGIN_BOT_PID=$(cat logs/login_bot.pid)
    kill $LOGIN_BOT_PID 2>/dev/null && echo "Stopped Login Bot (PID: $LOGIN_BOT_PID)"
fi

if [ -f logs/worker.pid ]; then
    WORKER_PID=$(cat logs/worker.pid)
    kill $WORKER_PID 2>/dev/null && echo "Stopped Worker (PID: $WORKER_PID)"
fi

# Clean up PID files
rm -f logs/*.pid

echo "All services stopped!"
