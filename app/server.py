import os
import socket
import docker
import shutil
import re
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

CONFIG_PATH = "/opt/unbound/etc/unbound/unbound.conf"
BACKUP_PATH = CONFIG_PATH + ".bak"
PORT = int(os.environ.get("APP_PORT", 80))

# Initialize Docker client to talk to the host socket
try:
    client = docker.from_env()
except Exception as e:
    print(f"Docker connection failed: {e}")
    client = None

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')
#

@app.route('/api/status', methods=['GET'])
def get_status():
    """Checks if Unbound is responding and attempts to find its real IP"""
    try:
        client = docker.from_env()
        container = client.containers.get("sierra6-unbound-dot_unbound_1")

        status_res = container.exec_run("unbound-control status")
        if status_res.exit_code != 0 or "is running" not in status_res.output.decode():
            raise Exception("Unbound is not running")

        ip_val = "Lookup Failed"
        total_queries = 0
        total_hits = 0
        avg_latency = 0
        uptime = 0
        
        try:
            client = docker.from_env()
            container = client.containers.get("sierra6-unbound-dot_unbound_1")
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            
            if networks:
                found_ip = next(iter(networks.values())).get('IPAddress')
                if found_ip:
                    ip_val = found_ip

            # Get Stats from Unbound
            stats_res = container.exec_run("unbound-control stats_noreset")
            stats_output = stats_res.output.decode('utf-8')

            q_match = re.search(r"total\.num\.queries=\s*(\d+)", stats_output) # Queries
            h_match = re.search(r"total\.num\.cachehits=\s*(\d+)", stats_output) # Cache Hits
            avg_match = re.search(r"total\.recursion\.time\.avg=\s*(\d+\.\d+)", stats_output) # Average ms
            up_match = re.search(r"time\.up=\s*(\d+\.\d+)", stats_output) # New Uptime Regex
            
            if q_match: total_queries = int(q_match.group(1))
            if h_match: total_hits = int(h_match.group(1))
            if avg_match: avg_latency = round(float(avg_match.group(1)) * 1000, 1)
            if up_match: uptime = float(up_match.group(1)) # Capture uptime as float

        except Exception as e:
            print(f"ERROR: Docker API lookup failed: {e}")
            pass

        return jsonify({
            "status": "running", 
            "ip": ip_val, 
            "stats": {
                "total_queries": total_queries,
                "cache_hits": total_hits,
                "avg_latency": avg_latency,
                "uptime": uptime
            }
        })
            
    except Exception:
        return jsonify({
            "status": "stopped", 
            "ip": None, 
            "stats": {
                "total_queries": 0,
                "cache_hits": 0,
                "avg_latency": 0,
                "uptime": 0
            }
        })
    
@app.route('/api/get-config', methods=['GET'])
def get_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                content = f.read()
            return jsonify({"status": "success", "data": content})
        return jsonify({"status": "error", "message": "unbound.conf not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/apply-config', methods=['POST'])
def apply_config():
    """Writes config AND restarts the unbound container"""
    data = request.json
    new_content = data.get('content')
    
    if not new_content:
        return jsonify({"status": "error", "message": "No content provided"}), 400

    try:
        # 1. Write the new configuration
        with open(CONFIG_PATH, 'w') as f:
            f.write(new_content)
        
        # 2. Restart the Unbound container
        if client:
            # Note: In Umbrel, the container name is usually [app-id]_unbound_1
            # We target the 'unbound' service specifically
            container = client.containers.get("sierra6-unbound-dot_unbound_1")
            container.restart()
            return jsonify({"status": "success", "message": "Config applied and Unbound restarted"})
        else:
            return jsonify({"status": "error", "message": "Docker socket not available"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/restore-default', methods=['POST'])
def restore_default():
    try:
        if not os.path.exists(BACKUP_PATH):
            return jsonify({"status": "error", "message": "Backup file not found"}), 404
        
        shutil.copy(BACKUP_PATH, CONFIG_PATH)
        
        if client:
            container = client.containers.get("sierra6-unbound-dot_unbound_1")
            container.restart()
            return jsonify({"status": "success", "message": "Reverted and restarted"})
        return jsonify({"status": "error", "message": "Docker socket not available"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if os.path.exists(CONFIG_PATH) and not os.path.exists(BACKUP_PATH):
    shutil.copy(CONFIG_PATH, BACKUP_PATH)
    print(f"Unbound DoT: Initial backup created: {BACKUP_PATH}")

if __name__ == '__main__':
    print(f"Starting Sierra6 UI Bridge on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT)