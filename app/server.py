import os
import socket
import docker
import shutil
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
        with socket.create_connection(("unbound", 53), timeout=2):
            ip_val = "Lookup Failed"
            
            try:
                client = docker.from_env()
                container = client.containers.get("sierra6-unbound-dot-_unbound_1")
                networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
                
                if networks:
                    found_ip = next(iter(networks.values())).get('IPAddress')
                    if found_ip:
                        ip_val = found_ip
                        print(f"INFO: Successfully retrieved Unbound IP: {ip_val}")
                    else:
                        print("WARN: Network found, but IPAddress field is empty.")
                else:
                    print("WARN: No networks found attached to Unbound container.")

            except Exception as e:
                print(f"ERROR: Docker API lookup failed: {e}")
                pass

            return jsonify({"status": "running", "ip": ip_val})
            
    except Exception:
        # No need to print here as 'stopped' is a standard state, 
        # but you could add a print(f"DEBUG: Service unreachable: {e}") if desired.
        return jsonify({"status": "stopped", "ip": None})
    
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
            container = client.containers.get("sierra6-unbound-dot-_unbound_1")
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
            container = client.containers.get("sierra6-unbound-dot-_unbound_1")
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