#!/bin/bash

echo "============================================"
echo "Group Message Scheduler - Starting All Services"
echo "============================================"

# Create log directory
mkdir -p logs

# Start Main Bot
echo "Starting Main Bot..."
python -m main_bot.bot > logs/main_bot.log 2>&1 &
MAIN_BOT_PID=$!
echo "Main Bot PID: $MAIN_BOT_PID"

# Wait a moment
sleep 2

# Start Login Bot
echo "Starting Login Bot..."
python -m login_bot.bot > logs/login_bot.log 2>&1 &
LOGIN_BOT_PID=$!
echo "Login Bot PID: $LOGIN_BOT_PID"

# Wait a moment
sleep 2

# Start Worker
echo "Starting Worker Service..."
python -m worker.worker > logs/worker.log 2>&1 &
WORKER_PID=$!
echo "Worker PID: $WORKER_PID"

echo ""
echo "All services started!"
echo ""
echo "PIDs:"
echo "  Main Bot:  $MAIN_BOT_PID"
echo "  Login Bot: $LOGIN_BOT_PID"
echo "  Worker:    $WORKER_PID"
echo ""
echo "Logs are in ./logs/"
echo ""
echo "To stop all services gracefully (recommended):"
echo "  kill -SIGINT $MAIN_BOT_PID $LOGIN_BOT_PID $WORKER_PID"

# Save PIDs to file for easy stopping
echo "$MAIN_BOT_PID" > logs/main_bot.pid
echo "$LOGIN_BOT_PID" > logs/login_bot.pid
echo "$WORKER_PID" > logs/worker.pid

# Wait for all processes
wait
