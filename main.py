from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from zlapi import ZaloAPI, ThreadType, Message
from zlapi.models import Mention, MultiMention
import threading, time, random, json, os, uuid, re
from datetime import datetime

# GỘP KEY ZALO
API_KEY = "8820814773961806095"
SECRET_KEY = "e2d98bb618b02b0465a1b9365d6c2626"

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# CẤU HÌNH MẬT KHẨU PHÂN QUYỀN
SUPER_ADMIN_PASS = "caoquockietdz29082012" 
SUB_ADMIN_PASS = "gojohouseno1sanwar"     
USER_PASS = "toolzaloqkiet"           

active_sessions = {} 
user_roles = {}      

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

# ================= ADMIN APIs =================
@app.route('/api/admin/sessions', methods=['GET'])
def get_admin_sessions():
    ip = get_client_ip()
    my_role = user_roles.get(ip, "unknown")
    
    if my_role == "dân thường" or my_role == "unknown":
        return jsonify({"success": False, "msg": "Không có quyền!"})

    result = []
    for tid, data in active_sessions.items():
        result.append({
            "task_id": tid,
            "ip": data["ip"],
            "role": data["role"],
            "time": data["time"],
            "status": data["status"],
            "mode": data["mode"]
        })
    return jsonify({"success": True, "sessions": result, "my_role": my_role})

@app.route('/api/admin/kill', methods=['POST'])
def admin_kill_session():
    my_ip = get_client_ip()
    my_role = user_roles.get(my_ip, "unknown")
    task_id = request.json.get('task_id')

    if task_id not in active_sessions:
        return jsonify({"success": False, "msg": "Không tìm thấy phiên."})

    target_role = active_sessions[task_id]["role"]

    if my_role == "King":
        pass 
    elif my_role == "lính của King":
        if target_role == "dân thường":
            pass 
        else:
            return jsonify({"success": False, "msg": "Bạn không đủ quyền dừng Admin khác!"})
    else:
        return jsonify({"success": False, "msg": "Không có quyền!"})

    try:
        active_sessions[task_id]["tool_obj"].stop()
    except:
        pass
    active_sessions[task_id]["status"] = "stopped"
    return jsonify({"success": True, "msg": "Đã dừng phiên này."})

# ================= AUTH APIs =================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    ip = get_client_ip()
    password = data.get('password', '')
    
    if password == SUPER_ADMIN_PASS:
        user_roles[ip] = "King"
        return jsonify({"success": True, "role": "King", "msg": "Chào King!"})
    elif password == SUB_ADMIN_PASS:
        user_roles[ip] = "lính của King"
        return jsonify({"success": True, "role": "lính của King", "msg": "Chào Lính!"})
    elif password == USER_PASS:
        user_roles[ip] = "dân thường"
        return jsonify({"success": True, "role": "dân thường", "msg": "Đăng nhập thành công!"})
    
    return jsonify({"success": False, "msg": "Sai mật khẩu!"})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    ip = get_client_ip()
    role = user_roles.get(ip)
    if role:
        return jsonify({"authenticated": True, "role": role})
    return jsonify({"authenticated": False})

# ================= ZALO CORE APIs =================
class ZaloSpamManager:
    def __init__(self, cookie_json, box_id, message, delay, mode="text", tag_ids=None, tag_names=None):
        self.cookie = cookie_json
        self.box_id = box_id
        if isinstance(message, str):
            self.message = message.replace('\\n', '\n')
        else:
            self.message = message
            
        self.delay = max(delay, 5) # Ép delay tối thiểu 5s để bảo vệ CPU
        self.mode = mode
        self.tag_ids = tag_ids or []
        self.tag_names = tag_names or []
        self.is_running = True
        self.thread = None
        self.bot = None

    def start(self):
        try:
            self.bot = ZaloAPI(API_KEY, SECRET_KEY, "", self.cookie)
            self.bot.fetchAccountInfo()
        except Exception as e:
            return False
        self.is_running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()
        return True

    def worker(self):
        while self.is_running:
            try:
                if self.mode == "tag" and self.tag_ids:
                    batch_size = 5 
                    for i in range(0, len(self.tag_ids), batch_size):
                        if not self.is_running: break
                        batch_ids = self.tag_ids[i:i+batch_size]
                        mentions = []
                        formatted = (self.message or "").rstrip() + " "
                        for uid, name in zip(batch_ids, self.tag_names[i:i+batch_size]):
                            tag = f"@{name}"
                            offset = len(formatted)
                            formatted += tag + " "
                            mentions.append(Mention(uid=uid, length=len(tag), offset=offset, auto_format=False))
                        multi = MultiMention(mentions)
                        self.bot.send(Message(text=formatted, mention=multi), thread_id=self.box_id, thread_type=ThreadType.GROUP)
                        time.sleep(2) 
                else:
                    self.bot.send(Message(text=self.message), thread_id=self.box_id, thread_type=ThreadType.GROUP)
            except Exception as e:
                time.sleep(5) 
            time.sleep(self.delay * random.uniform(1.0, 1.2))

    def stop(self):
        self.is_running = False

def parse_cookie(cookie_str):
    if cookie_str.strip().startswith("{"): return json.loads(cookie_str)
    cookies = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/start', methods=['POST'])
def start():
    data = request.json
    raw_cookie = data.get('cookie')
    box_id = data.get('box_id')
    message = data.get('message', 'Hello')
    delay = int(data.get('delay', 10))
    mode = data.get('mode', 'text')
    tag_ids = data.get('tag_ids', [])
    tag_names = data.get('tag_names', [])
    my_ip = get_client_ip()
    my_role = user_roles.get(my_ip, "unknown")

    if not raw_cookie or not box_id: return jsonify({"success": False, "msg": "Thiếu dữ liệu!"})
    try: cookie_json = parse_cookie(raw_cookie)
    except: return jsonify({"success": False, "msg": "Cookie không hợp lệ!"})

    task_id = str(uuid.uuid4())[:8]
    tool = ZaloSpamManager(cookie_json, box_id, message, delay, mode, tag_ids, tag_names)
    
    if tool.start():
        active_sessions[task_id] = {
            "ip": my_ip,
            "role": my_role,
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": "running",
            "mode": mode,
            "tool_obj": tool
        }
        return jsonify({"success": True, "msg": f"Đã chạy ngầm Zalo!", "task_id": task_id})
    return jsonify({"success": False, "msg": "Lỗi đăng nhập Zalo!"})

@app.route('/api/stop', methods=['POST'])
def stop():
    data = request.json
    task_id = data.get('task_id')
    if task_id in active_sessions:
        try:
            active_sessions[task_id]["tool_obj"].stop()
        except:
            pass
        active_sessions[task_id]["status"] = "stopped"
        return jsonify({"success": True, "msg": "Đã dừng tool."})
    return jsonify({"success": False, "msg": "Không tìm thấy tiến trình."})

@app.route('/api/get_box', methods=['POST'])
def get_box():
    data = request.json
    cookie_str = data.get('cookie', '').strip()
    if not cookie_str: return jsonify({"success": False, "msg": "Thiếu Cookie!"})
    try: cookie_json = parse_cookie(cookie_str)
    except: return jsonify({"success": False, "msg": "Cookie sai định dạng!"})
    try:
        bot = ZaloAPI(API_KEY, SECRET_KEY, "", cookie_json)
        data_groups = bot.fetchAllGroups()
        groups = []
        grid_map = getattr(data_groups, "gridVerMap", {}) or getattr(data_groups, "gridInfoMap", {})
        for gid in grid_map.keys():
            try:
                info = bot.fetchGroupInfo(gid)
                name = info.gridInfoMap[gid].get("name", str(gid))
            except: name = str(gid)
            groups.append({"id": gid, "name": name})
        return jsonify({"success": True, "threads": groups})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi Zalo: {e}"})

@app.route('/api/get_members', methods=['POST'])
def get_members():
    data = request.json
    cookie_str = data.get('cookie', '').strip()
    group_id = data.get('group_id', '').strip()
    if not cookie_str or not group_id: return jsonify({"success": False, "msg": "Thiếu dữ liệu!"})
    try: cookie_json = parse_cookie(cookie_str)
    except: return jsonify({"success": False, "msg": "Cookie sai định dạng!"})
    
    try:
        bot = ZaloAPI(API_KEY, SECRET_KEY, "", cookie_json)
        info = bot.fetchGroupInfo(group_id)
        mem_list = info.gridInfoMap.get(group_id, {}).get("memVerList", [])
        members = []
        for m in mem_list:
            uid = m.split("_")[0]
            try:
                uinfo = bot.fetchUserInfo(uid)
                name = uinfo.changed_profiles.get(uid, {}).get('displayName', uid)
            except: name = uid
            members.append({"id": uid, "name": name})
            time.sleep(0.1) 
        return jsonify({"success": True, "members": members})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi lấy thành viên: {e}"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, threaded=True)