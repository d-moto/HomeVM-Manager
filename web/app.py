import sys
from pathlib import Path
import threading
import time
import keyring

# Add project root to path to import core modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, jsonify, request
from core.vm_data import VM, load_vm_list, save_vm_list
from core.vm_control import power_action_unified, send_magic_packet
from core.vm_info import resolve_status

app = Flask(__name__)

# Cache for status
status_cache = {}

def update_status_loop():
    """Background thread to update VM status periodically"""
    while True:
        vms = load_vm_list()
        for vm in vms:
            try:
                status, new_ip = resolve_status(vm.mac, vm.host_ip)
                status_cache[vm.mac] = {
                    "status": status,
                    "ip": new_ip or vm.host_ip or "-",
                    "last_updated": time.strftime("%H:%M:%S")
                }
            except Exception as e:
                print(f"Error updating status for {vm.vm_name}: {e}")
        time.sleep(10)

# Start background thread
t = threading.Thread(target=update_status_loop, daemon=True)
t.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vms', methods=['GET'])
def get_vms():
    vms = load_vm_list()
    data = []
    for vm in vms:
        d = vm.to_dict()
        # Merge with live status
        if vm.mac in status_cache:
            d.update(status_cache[vm.mac])
        else:
            d.update({"status": "取得中...", "last_updated": "-"})
        data.append(d)
    return jsonify(data)

@app.route('/api/vms', methods=['POST'])
def add_vm():
    data = request.json
    vms = load_vm_list()
    
    # Validation
    if any(v.vm_name == data.get("vm_name") for v in vms):
        return jsonify({"error": "Name already exists"}), 400
        
    new_vm = VM.from_dict(data)
    vms.append(new_vm)
    save_vm_list(vms)
    return jsonify({"success": True})

@app.route('/api/vms/<string:mac>', methods=['DELETE'])
def delete_vm(mac):
    vms = load_vm_list()
    vms = [v for v in vms if v.mac != mac]
    save_vm_list(vms)
    return jsonify({"success": True})

@app.route('/api/power', methods=['POST'])
def power_action():
    data = request.json
    mac = data.get("mac")
    action = data.get("action")
    password = data.get("password") # Optional, if not in keyring

    vms = load_vm_list()
    target_vm = next((v for v in vms if v.mac == mac), None)
    
    if not target_vm:
        return jsonify({"error": "VM not found"}), 404

    if action == "wol":
        if target_vm.type != "physical":
             return jsonify({"error": "WOL only for physical machines"}), 400
        try:
            send_magic_packet(target_vm.mac)
            return jsonify({"success": True, "message": "Magic Packet sent"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # SSH/WinRM
    if not target_vm.host_ip:
         return jsonify({"error": "IP unknown"}), 400
         
    # Password resolution
    final_pw = password
    if not final_pw:
        try:
            final_pw = keyring.get_password("HomeVM-Manager", target_vm.host_ip)
        except:
            pass
    
    if not final_pw:
        return jsonify({"error": "Password required", "need_password": True}), 401

    try:
        ok, msg = power_action_unified(target_vm.method, target_vm.host_ip, target_vm.user, final_pw, action)
        if ok:
            # Save password if successful and provided manually
            if password:
                keyring.set_password("HomeVM-Manager", target_vm.host_ip, password)
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"error": msg}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rdp/<string:ip>')
def download_rdp(ip):
    """Generate and download .rdp file"""
    rdp_content = f"full address:s:{ip}\nprompt for credentials:i:1\n"
    return rdp_content, 200, {
        'Content-Type': 'application/x-rdp',
        'Content-Disposition': f'attachment; filename={ip}.rdp'
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
