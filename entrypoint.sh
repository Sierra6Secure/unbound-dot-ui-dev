#!/bin/bash
set -e

echo "--- Sierra6 Unbound UI Startup ---"

# 1. Check if the config file exists
if [ ! -f /opt/unbound/etc/unbound/unbound.conf ]; then
    echo "WARNING: /opt/unbound/etc/unbound/unbound.conf not found!"
    echo "Check your Umbrel volume mounts in docker-compose."
else
    echo "Successfully located unbound.conf."
fi

# 2. Start the Python Flask server
# We use 'exec' so that Python becomes PID 1, 
# allowing it to receive shutdown signals properly.
echo "Starting backend bridge..."
exec python3 /app/server.py