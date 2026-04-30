#!/bin/bash
cd /var/www/aibook/bookmaker/backend
lsof -ti :8086 | xargs -r kill -9 2>/dev/null
sleep 2
nohup ./venv/bin/uvicorn main:app --host 127.0.0.1 --port 8086 --reload > bookmaker.log 2>&1 &
sleep 3
echo "Server started"
tail -10 bookmaker.log
