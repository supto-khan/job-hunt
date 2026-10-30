#!/usr/bin/env bash
# ==============================================================================
# Job Hunter Process Watchdog
# Checks if the FastAPI / Uvicorn server is responsive on port 8009.
# If dead or unresponsive, restarts it automatically.
# ==============================================================================

PROJECT_DIR="/www/wwwroot/job-hunter"
LOG_FILE="/www/wwwlogs/python/job-hunter/watchdog.log"
PORT=8009
CHECK_URL="http://127.0.0.1:${PORT}/api/hunt-status"

mkdir -p "$(dirname "$LOG_FILE")"

# Check HTTP status code with 5-second timeout
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$CHECK_URL" 2>/dev/null)

if [ "$HTTP_CODE" != "200" ]; then
    NOW=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$NOW] [ALERT] job-hunter is down (HTTP: '$HTTP_CODE'). Attempting restart..." >> "$LOG_FILE"

    # Try aaPanel project restart script first
    if [ -f "/www/server/panel/script/restart_project.py" ]; then
        btpython /www/server/panel/script/restart_project.py python job-hunter >> "$LOG_FILE" 2>&1
    fi

    # Verify after 4 seconds
    sleep 4
    NEW_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$CHECK_URL" 2>/dev/null)
    if [ "$NEW_CODE" = "200" ]; then
        echo "[$NOW] [RECOVERED] job-hunter successfully restored (HTTP 200)." >> "$LOG_FILE"
    else
        echo "[$NOW] [WARN] Standard restart failed (HTTP '$NEW_CODE'). Starting directly via virtualenv..." >> "$LOG_FILE"
        if [ -d "$PROJECT_DIR" ]; then
            cd "$PROJECT_DIR" || exit 1
            fuser -k "${PORT}/tcp" 2>/dev/null || true
            nohup /www/server/pyporject_evn/jobhunter/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" >> /www/wwwlogs/python/job-hunter/error.log 2>&1 &
        fi
    fi
fi
