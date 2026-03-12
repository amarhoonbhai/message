#!/bin/bash

echo "============================================"
echo "Spinify Distributed Architecture - Start All"
echo "============================================"

# Create log directory
mkdir -p logs

# 1. Start Main Bot
echo "Starting Main Bot..."
python -m main_bot.bot > logs/main_bot.log 2>&1 &
MAIN_BOT_PID=$!
echo "  PID: $MAIN_BOT_PID"

sleep 1

# 2. Start Login Bot
echo "Starting Login Bot..."
python -m login_bot.bot > logs/login_bot.log 2>&1 &
LOGIN_BOT_PID=$!
echo "  PID: $LOGIN_BOT_PID"

sleep 1

# 3. Start Scheduler Service
echo "Starting Scheduler Service..."
python -m services.scheduler.scheduler > logs/scheduler.log 2>&1 &
SCHEDULER_PID=$!
echo "  PID: $SCHEDULER_PID"

sleep 1

# 4. Start ARQ Worker
echo "Starting ARQ Worker..."
arq services.worker.task_worker.WorkerSettings > logs/worker.log 2>&1 &
WORKER_PID=$!
echo "  PID: $WORKER_PID"

sleep 1

# 5. Start Command Listener
echo "Starting Command Listener..."
python -m services.worker.command_listener > logs/listener.log 2>&1 &
LISTENER_PID=$!
echo "  PID: $LISTENER_PID"

echo ""
echo "✅ All 5 services started in the background!"
echo "Logs are located in the ./logs/ directory."
echo ""
echo "Press Ctrl+C at any time to stop them all."
echo ""

# Wait for all background processes (keeps terminal open)
wait $MAIN_BOT_PID $LOGIN_BOT_PID $SCHEDULER_PID $WORKER_PID $LISTENER_PID

# Cleanup hook when Ctrl+C is pressed
trap "echo 'Stopping all services...'; kill -SIGINT $MAIN_BOT_PID $LOGIN_BOT_PID $SCHEDULER_PID $WORKER_PID $LISTENER_PID" SIGINT SIGTERM
