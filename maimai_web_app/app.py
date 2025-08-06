import faulthandler
faulthandler.enable()

import os
import json
import shutil
import time
import traceback
import math
import uuid
import requests
import jwt # **终极改造**: 引入JWT解码库
import threading
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, abort, g
from cryptography.fernet import Fernet

from ultralytics import YOLO
from paddleocr import PaddleOCR
from fuzzywuzzy import process

# --- 1. 创建Flask应用和文件夹 ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['COVER_CACHE_FOLDER'] = 'covers'
app.config['USER_DATA_FOLDER'] = 'user_data'
app.config['SECRET_KEY_FILE'] = 'secret.key'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['COVER_CACHE_FOLDER'], exist_ok=True)
os.makedirs(app.config['USER_DATA_FOLDER'], exist_ok=True)

# --- **终极改造**: 加密与会话管理 ---
server_sessions = {} # 内存会话字典，依然用于快速验证

def load_or_generate_key():
    """加载或生成用于加密密码的密钥"""
    key_path = app.config['SECRET_KEY_FILE']
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            key = f.read()
    else:
        print(f"警告: 未找到密钥文件 {key_path}。正在生成新的密钥...")
        print("警告: 如果您之前有已存储的用户数据，此操作将导致旧数据无法解密！")
        key = Fernet.generate_key()
        with open(key_path, 'wb') as f:
            f.write(key)
    return key

encryption_key = load_or_generate_key()
cipher_suite = Fernet(encryption_key)

def encrypt_password(password):
    return cipher_suite.encrypt(password.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_password):
    return cipher_suite.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')

# --- **留言板改造**: 新增文件锁 ---
feedback_lock = threading.Lock()

# --- 2. 在应用启动时加载所有模型 (只运行一次) ---

# --- **诊断**: 打印关键路径，以帮助调试文件保留问题 ---
MONITORING_FLAG_PATH_DIAG = os.path.abspath(os.path.join(os.path.dirname(__file__), 'monitoring.flag'))
print(f"--- [DIAGNOSTIC] Monitoring flag will be checked at this absolute path: {MONITORING_FLAG_PATH_DIAG} ---")

print("正在加载YOLOv8模型...")
# **终极路径修复**: 改为相对路径
YOLO_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'ultralytics-main', 'runs', 'detect', 'train11', 'weights', 'best.pt')
yolo_model = YOLO(YOLO_MODEL_PATH)
print("YOLOv8模型加载成功！")

print("正在加载PaddleOCR模型...")
ocr_instance = PaddleOCR(
    device="cpu",
    enable_mkldnn=False,
    cpu_threads=2,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    text_detection_model_name="PP-OCRv5_mobile_det", 
)
print("PaddleOCR模型加载成功！")

# --- **终极改造**: 服务器启动时自动恢复会话 ---
def restore_sessions_on_startup():
    print("--- 正在从硬盘恢复用户会话 ---")
    user_files = [f for f in os.listdir(app.config['USER_DATA_FOLDER']) if f.endswith('.json')]
    restored_count = 0
    for filename in user_files:
        try:
            user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], filename)
            with open(user_data_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
            
            username = user_data.get("username")
            session_token = user_data.get("session_token")
            jwt_token = user_data.get("jwt_token")

            if not username or not session_token or not jwt_token:
                print(f"警告: 文件 {filename} 缺少完整的会话信息，跳过。")
                continue

            # **终极会话持久化**: 直接从文件恢复会话到内存
            server_sessions[session_token] = jwt_token
            print(f"用户 [{username}] 的会话已从文件成功恢复。Session Token: {session_token[:8]}...")
            restored_count += 1

        except json.JSONDecodeError:
            print(f"错误: 文件 {filename} 格式损坏，无法解析。")
        except Exception as e:
            print(f"恢复文件 {filename} 时出错: {e}")
            traceback.print_exc()
            
    print(f"--- 会话恢复完成，共成功恢复 {restored_count} 个用户 ---")

# ----------------------------------------------------

# --- 辅助函数 ---
def get_cover_len5_id(mid) -> str:
    """将歌曲ID转换为符合水鱼API要求的5位数ID字符串"""
    mid = int(mid)
    if 10001 <= mid <= 11000:
        mid -= 10000
    return f"{mid:05d}"

def find_best_match(ocr_text, songs_data):
    """使用 fuzzywuzzy 查找最佳匹配的歌曲，并返回所有同名谱面"""
    unique_titles = list(set(song['title'] for song in songs_data))
    best_match = process.extractOne(ocr_text, unique_titles)
    
    # **算法调优**: 根据用户反馈，将匹配阈值调整为60，以在准确性和容错性之间取得平衡
    if best_match and best_match[1] > 60:
        matched_title = best_match[0]
        all_versions = [song for song in songs_data if song['title'] == matched_title]
        # **终极改造**: 为每个版本添加封面URL
        for version in all_versions:
            version['cover_url'] = f"/cover/{version['id']}"
        return all_versions
        
    return None

def is_inside(inner_box, outer_box):
    """检查 inner_box 是否在 outer_box 内部"""
    ix1, iy1, ix2, iy2 = inner_box.xyxy[0]
    ox1, oy1, ox2, oy2 = outer_box.xyxy[0]
    return ix1 >= ox1 and iy1 >= oy1 and ix2 <= ox2 and iy2 <= oy2

def get_most_centered_box(boxes, img_shape):
    """从一组box中找到最居中的那一个"""
    if not boxes:
        return None
    
    img_height, img_width = img_shape
    img_center_x, img_center_y = img_width / 2, img_height / 2
    
    min_distance = float('inf')
    most_centered = None
    
    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0]
        box_center_x = (x1 + x2) / 2
        box_center_y = (y1 + y2) / 2
        distance = math.sqrt((box_center_x - img_center_x)**2 + (box_center_y - img_center_y)**2)
        
        if distance < min_distance:
            min_distance = distance
            most_centered = box
            
    return most_centered

# --- 主路由 ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(os.path.join(app.root_path), 'manifest.json')

# **终极健壮性修复**: 新增一个专门用于提供静态图片的路由
@app.route('/image/<path:subfolder>/<path:filename>')
def serve_image(subfolder, filename):
    # 构建安全的图片文件夹路径
    image_dir = os.path.join(app.root_path, 'image', subfolder)
    # 检查路径是否在允许的 'image' 目录下，防止路径遍历攻击
    if not os.path.abspath(image_dir).startswith(os.path.abspath(os.path.join(app.root_path, 'image'))):
        abort(404)
    return send_from_directory(image_dir, filename)

# --- **新增**: 封面获取与缓存路由 ---
@app.route('/cover/<song_id>')
def get_song_cover(song_id):
    try:
        cover_id_str = get_cover_len5_id(song_id)
        cover_filename = f"{cover_id_str}.png"
        cached_cover_path = os.path.join(app.config['COVER_CACHE_FOLDER'], cover_filename)

        # 1. 检查本地缓存
        if os.path.exists(cached_cover_path):
            return send_from_directory(app.config['COVER_CACHE_FOLDER'], cover_filename)

        # 2. 如果没有缓存，则从外部API下载
        external_url = f"https://www.diving-fish.com/covers/{cover_id_str}.png"
        response = requests.get(external_url, stream=True)

        # 3. 检查下载是否成功
        if response.status_code == 200:
            # 保存到缓存
            with open(cached_cover_path, 'wb') as f:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, f)
            
            # 发送给客户端
            return send_from_directory(app.config['COVER_CACHE_FOLDER'], cover_filename)
        else:
            # **终极健壮性修复**: 如果下载失败，直接返回后备图片
            print(f"Cover for song_id {song_id} not found. Serving fallback image.")
            return send_from_directory(os.path.join(app.root_path, 'image', '404'), '404.png')

    except Exception as e:
        print(f"Error getting cover for song_id {song_id}: {e}. Serving fallback image.")
        # **终极健壮性修复**: 任何异常都返回后备图片
        return send_from_directory(os.path.join(app.root_path, 'image', '404'), '404.png')


# --- **终极改造**: 新增JWT解码辅助函数 ---
def get_username_from_jwt(jwt_token):
    """从Diving-Fish的JWT中解码出用户名，不验证签名"""
    try:
        decoded = jwt.decode(jwt_token, options={"verify_signature": False})
        return decoded.get("username")
    except Exception as e:
        print(f"JWT解码失败: {e}")
        return None

def _get_latest_data_from_fish(jwt_token):
    """
    **终极架构重建**: 此函数的唯一职责是从Diving-Fish获取并合并数据，然后返回字典。
    它不进行任何文件读写操作。
    """
    client = requests.Session()
    client.cookies.set("jwt_token", jwt_token)
    
    print("正在从Diving-Fish服务器拉取最新数据 (阶段1/2: Records)...")
    records_response = client.get("https://www.diving-fish.com/api/maimaidxprober/player/records", timeout=20)
    records_response.raise_for_status()
    records_data = records_response.json()
    
    print("正在从Diving-Fish服务器拉取最新数据 (阶段2/2: Profile)...")
    profile_response = client.get("https://www.diving-fish.com/api/maimaidxprober/player/profile", timeout=10)
    profile_response.raise_for_status()
    profile_data = profile_response.json()

    # 合并数据源
    merged_data = records_data.copy()
    merged_data['bind_qq'] = profile_data.get('bind_qq', '')
    merged_data['plate'] = profile_data.get('plate', '')
    merged_data['username'] = profile_data.get('username') # 以profile的为准
    
    return merged_data

# --- **新增**: 认证装饰器 ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        if token not in server_sessions:
            return jsonify({'message': 'Token is invalid or expired!'}), 401
        
        # **留言板改造**: 将用户名存入g，方便后续路由使用
        jwt_token = server_sessions.get(token)
        username = get_username_from_jwt(jwt_token)
        if not username:
            # 如果JWT解析失败，尝试从本地文件后备
            user_files = [f for f in os.listdir(app.config['USER_DATA_FOLDER']) if f.endswith('.json')]
            for filename in user_files:
                user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], filename)
                with open(user_data_path, 'r', encoding='utf-8') as f_user:
                    user_data = json.load(f_user)
                if user_data.get("session_token") == token:
                    username = user_data.get("username")
                    break
        
        g.username = username
        return f(*args, **kwargs)
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    """
    **终极架构重建**: 登录端点现在负责完整的用户初始化流程。
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    try:
        # 1. 代理登录到Diving-Fish
        client = requests.Session()
        df_login_response = client.post(
            "https://www.diving-fish.com/api/maimaidxprober/login",
            headers={"Content-Type": "application/json"},
            json={"username": username, "password": password},
            timeout=10
        )
        df_login_response.raise_for_status()
        df_jwt = client.cookies.get("jwt_token")
        if not df_jwt:
            return jsonify({"error": "未能从Diving-Fish获取认证令牌"}), 500

        # 2. 获取最新的完整用户数据
        user_data = _get_latest_data_from_fish(df_jwt)
        actual_username = user_data.get("username")
        if not actual_username:
            return jsonify({"error": "获取用户数据失败"}), 500

        # 3. 创建并添加新的认证信息
        session_token = str(uuid.uuid4())
        user_data["session_token"] = session_token
        user_data["jwt_token"] = df_jwt
        user_data["encrypted_password"] = encrypt_password(password)

        # 4. 将完整的用户数据写入文件
        safe_filename = "".join(c for c in actual_username if c.isalnum() or c in ('_', '-')).rstrip()
        user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], f"{safe_filename}.json")
        with open(user_data_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=4)
        
        # 5. 更新内存会话并返回
        server_sessions[session_token] = df_jwt
        print(f"用户 [{actual_username}] 的完整数据和会话已创建并保存。")
        return jsonify({"message": "登录成功", "session_token": session_token})

    except requests.exceptions.HTTPError:
        return jsonify({"error": "登录凭据错误，请检查您的用户名和密码"}), 401
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"登录时网络错误: {e}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"发生未知错误: {e}"}), 500

@app.route('/api/logout', methods=['POST'])
@token_required
def logout():
    """处理用户登出"""
    token = request.headers['x-access-token']
    if token in server_sessions:
        del server_sessions[token]
    return jsonify({"message": "登出成功"})

@app.route('/api/profile/refresh', methods=['POST'])
@token_required
def refresh_profile():
    """
    **终极架构重建**: 刷新端点现在负责完整的用户数据更新流程。
    """
    session_token = request.headers['x-access-token']
    jwt_token = server_sessions.get(session_token)
    
    try:
        # 1. 获取最新的完整用户数据
        new_data = _get_latest_data_from_fish(jwt_token)
        username = new_data.get("username")
        if not username:
            return jsonify({"error": "刷新时未能获取用户名"}), 500

        # 2. 从旧文件中继承认证信息
        safe_filename = "".join(c for c in username if c.isalnum() or c in ('_', '-')).rstrip()
        user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], f"{safe_filename}.json")
        
        if os.path.exists(user_data_path):
            with open(user_data_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            new_data["session_token"] = old_data.get("session_token", session_token) # 保持旧token不变
            new_data["encrypted_password"] = old_data.get("encrypted_password")
        else:
            # 这是一个异常情况，但为了健壮性，我们还是处理一下
            new_data["session_token"] = session_token
        
        new_data["jwt_token"] = jwt_token

        # 3. 将更新后的完整数据写回文件
        with open(user_data_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)

        # 4. 更新内存会话并返回
        server_sessions[new_data["session_token"]] = jwt_token
        print(f"用户 [{username}] 的数据已刷新并保存。")
        return jsonify({
            "rating": new_data.get("rating"),
            "username": new_data.get("username"),
            "bind_qq": new_data.get("bind_qq"),
            "additional_rating": new_data.get("additional_rating"),
            "plate": new_data.get("plate")
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"从Diving-Fish刷新数据时出错: {e}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"刷新数据时发生未知错误: {e}"}), 500

@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile():
    """
    **终极数据一致性修复**: 直接从本地缓存文件读取并返回个人资料。
    本地文件是唯一的数据源，通过 /api/profile/refresh 更新。
    """
    try:
        session_token = request.headers['x-access-token']
        jwt_token = server_sessions.get(session_token)
        username = get_username_from_jwt(jwt_token)

        if not username:
            return jsonify({"error": "无法从Token中解析用户名"}), 401

        safe_filename = "".join(c for c in username if c.isalnum() or c in ('_', '-')).rstrip()
        user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], f"{safe_filename}.json")

        if not os.path.exists(user_data_path):
            return jsonify({"error": "未找到该用户的本地数据文件，请尝试重新登录或更新数据。"}), 404

        with open(user_data_path, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        
        # 返回前端需要的所有字段
        profile_to_return = {
            "rating": local_data.get("rating"),
            "username": local_data.get("username"),
            "bind_qq": local_data.get("bind_qq"),
            "additional_rating": local_data.get("additional_rating"),
            "plate": local_data.get("plate")
        }
        return jsonify(profile_to_return)

    except Exception as e:
        print(f"获取本地个人资料时出错: {e}")
        traceback.print_exc()
        return jsonify({"error": f"发生未知服务器错误: {e}"}), 500


@app.route('/api/b50', methods=['GET'])
@token_required
def get_b50():
    """
    **B50功能**: 从Diving-Fish的 /query/player 端点获取B50数据，
    并用本地歌曲信息进行丰富后返回。
    """
    try:
        # 1. 获取认证信息和用户名
        session_token = request.headers['x-access-token']
        jwt_token = server_sessions.get(session_token)
        username = get_username_from_jwt(jwt_token)

        if not username:
            # **终极健壮性修复**: 如果JWT解析失败，尝试从本地文件获取用户名作为后备
            user_files = [f for f in os.listdir(app.config['USER_DATA_FOLDER']) if f.endswith('.json')]
            for filename in user_files:
                user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], filename)
                with open(user_data_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                if user_data.get("session_token") == session_token:
                    username = user_data.get("username")
                    break
        
        if not username:
            return jsonify({"error": "无法确定用户名，请尝试重新登录。"}), 401

        # 2. 从Diving-Fish获取B50数据
        print(f"正在为用户 [{username}] 查询B50数据...")
        df_response = requests.post(
            "https://www.diving-fish.com/api/maimaidxprober/query/player",
            json={"username": username, "b50": "true"},
            timeout=20
        )
        df_response.raise_for_status()
        b50_data = df_response.json()

        # 3. **终极根本原因修复**: 根据用户提供的最新日志，从 'charts' 键中提取 'dx' 和 'sd'
        charts_data = b50_data.get("charts", {})
        dx_records = charts_data.get("dx", [])
        sd_records = charts_data.get("sd", [])

        # **终极B50逻辑重构 (根据用户最新指示修正)**: b15是新版(dx), b35是旧版(sd)
        dx_records.sort(key=lambda x: x.get('ra', 0), reverse=True)
        sd_records.sort(key=lambda x: x.get('ra', 0), reverse=True)

        b15_records = dx_records[:15] # 新版 Best 15
        b35_records = sd_records[:35] # 旧版 Best 35

        # 4. 加载本地歌曲数据库以丰富信息
        songs_json_path = os.path.join(app.root_path, 'songs.json')
        with open(songs_json_path, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        songs_map = {str(song['id']): song for song in songs_data}

        # 5. 封装一个函数来丰富列表，避免代码重复
        def enrich_records(records):
            enriched_list = []
            for record in records:
                song_id = record.get("song_id")
                song_info = songs_map.get(str(song_id))
                
                if song_info:
                    record['title'] = song_info.get('basic_info', {}).get('title', '未知曲名')
                    record['cover_url'] = f"/cover/{song_id}"
                else:
                    print(f"警告: 在本地songs.json中未找到 song_id: {song_id} 的信息。")
                    record['title'] = '未知曲名'
                    record['cover_url'] = ''
                enriched_list.append(record)
            return enriched_list

        enriched_b15 = enrich_records(b15_records)
        enriched_b35 = enrich_records(b35_records)

        # 6. 以结构化对象返回 (根据用户最新指示修正)
        return jsonify({
            "b15": enriched_b15,
            "b35": enriched_b35
        })

    except requests.exceptions.HTTPError as e:
        try:
            message = e.response.json().get("message", str(e))
            if e.response.status_code == 403:
                return jsonify({"error": "该用户已设置隐私或未同意用户协议，无法查询B50。"}), 403
            if e.response.status_code == 400:
                return jsonify({"error": "Diving-Fish服务器报告：无此用户。"}), 400
        except Exception:
             message = str(e)
        return jsonify({"error": f"查询B50时HTTP错误: {message}"}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"查询B50时网络错误: {e}"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"处理B50数据时发生未知错误: {e}"}), 500


@app.route('/api/player_score', methods=['POST'])
@token_required
def get_player_score():
    """根据歌曲ID，从本地用户文件中查找并返回玩家的成绩，并附带谱面总分"""
    try:
        # 1. 获取请求数据和认证信息
        data = request.get_json()
        song_id = data.get('song_id')
        if not song_id:
            return jsonify({"error": "未提供歌曲ID"}), 400

        session_token = request.headers['x-access-token']
        jwt_token = server_sessions.get(session_token)
        username = get_username_from_jwt(jwt_token)

        if not username:
            return jsonify({"error": "无法从Token中解析用户名"}), 401

        # 2. 读取本地用户数据文件
        safe_filename = "".join(c for c in username if c.isalnum() or c in ('_', '-')).rstrip()
        user_data_path = os.path.join(app.config['USER_DATA_FOLDER'], f"{safe_filename}.json")

        if not os.path.exists(user_data_path):
            return jsonify({"error": "未找到该用户的本地数据文件"}), 404

        with open(user_data_path, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        records = user_data.get("records", [])

        # 3. 加载歌曲数据库以查找谱面总分
        songs_json_path = os.path.join(app.root_path, 'songs.json')
        with open(songs_json_path, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        
        # 为了快速查找，创建一个歌曲ID到歌曲信息的映射
        songs_map = {str(song['id']): song for song in songs_data}

        # 4. 查找所有匹配的成绩记录，并附加上谱面总分
        scores_data = []
        for record in records:
            if str(record.get("song_id")) == str(song_id):
                player_score_type = record.get("type")
                player_score_level_index = record.get("level_index")
                
                # 在歌曲数据库中找到对应的歌曲和谱面
                song_info = songs_map.get(str(song_id))
                max_dx_score = 0
                
                if song_info and song_info.get('type') == player_score_type:
                    charts = song_info.get('charts', [])
                    if 0 <= player_score_level_index < len(charts):
                        chart_info = charts[player_score_level_index]
                        notes = chart_info.get('notes', [])
                        # **终极正确性修复**: 无论notes数组包含4个(SD)还是5个(DX)元素，
                        # 都将所有元素求和，以得到正确的总物量。
                        if len(notes) >= 4:
                            total_notes = sum(notes)
                            max_dx_score = total_notes * 3
                
                scores_data.append({
                    "achievements": record.get("achievements"),
                    "dxScore": record.get("dxScore"),
                    "maxDxScore": max_dx_score, # 新增字段
                    "fc": record.get("fc"),
                    "fs": record.get("fs"),
                    "rate": record.get("rate"),
                    "level": record.get("level"),
                    "level_index": record.get("level_index"),
                    "type": player_score_type
                })
        
        # 5. 返回所有找到的成绩记录
        return jsonify(scores_data)

    except Exception as e:
        print(f"获取玩家成绩时出错: {e}")
        traceback.print_exc()
        return jsonify({"error": f"发生未知服务器错误: {e}"}), 500


@app.route('/search', methods=['POST'])
def search_song():
    """根据查询词（ID或歌曲名）搜索歌曲"""
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': '未提供查询参数'}), 400
    
    query = data['query'].strip()
    if not query:
        return jsonify({'error': '查询参数为空'}), 400

    # 加载歌曲数据
    songs_json_path = os.path.join(app.root_path, 'songs.json')
    with open(songs_json_path, 'r', encoding='utf-8') as f:
        songs_data = json.load(f)

    # **终极后端逻辑修复**: 严格区分ID搜索和文本搜索
    if query.isdigit():
        # --- ID 精确搜索路径 ---
        # **终极类型匹配修复**: 直接使用字符串进行比较，不再转换为整数
        songs_by_id = [song for song in songs_data if song['id'] == query]
        
        if songs_by_id:
            # 找到了，为每个版本添加封面URL并返回
            for version in songs_by_id:
                version['cover_url'] = f"/cover/{version['id']}"
            return jsonify(songs_by_id)
        else:
            # 按ID精确搜索但未找到，直接返回404，绝不进行模糊匹配
            return jsonify({'error': f'本地数据库中未找到ID为 {query} 的歌曲'}), 404
    else:
        # --- 文本模糊搜索路径 ---
        found_songs = find_best_match(query, songs_data)
        if found_songs:
            return jsonify(found_songs)
        else:
            return jsonify({'error': '未找到匹配的歌曲'}), 404


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    unique_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    filename = f"{unique_id}.jpg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    project_name = f"runs/detect/{unique_id}"
    save_dir = None
    
    try:
        # 1. 第一次YOLO预测
        print(f"[{unique_id}] Running 1st YOLO prediction...")
        yolo_results = yolo_model.predict(source=filepath, save_crop=True, project=project_name, name="predict_pass_1", device='cpu')
        save_dir = yolo_results[0].save_dir
        
        if not yolo_results[0].boxes:
            return jsonify({"error": "YOLO did not detect any objects in the first pass."}), 500
        
        boxes = yolo_results[0].boxes
        img_shape = yolo_results[0].orig_shape
        
        all_boxes = {int(b.cls): [] for b in boxes}
        for b in boxes:
            all_boxes[int(b.cls)].append(b)

        name_boxes = all_boxes.get(0, [])
        name1_boxes = all_boxes.get(1, [])
        frame1_boxes = all_boxes.get(2, [])
        name2_boxes = all_boxes.get(3, [])
        frame2_boxes = all_boxes.get(4, [])

        # 2. 第一次筛选逻辑
        target_box = None
        
        if name_boxes:
            target_box = get_most_centered_box(name_boxes, img_shape)
        elif frame1_boxes:
            name1_in_frame1 = [n1 for n1 in name1_boxes for f1 in frame1_boxes if is_inside(n1, f1)]
            if name1_in_frame1:
                target_box = get_most_centered_box(name1_in_frame1, img_shape)
        elif frame2_boxes:
            name2_in_frame2 = [n2 for n2 in name2_boxes for f2 in frame2_boxes if is_inside(n2, f2)]
            if name2_in_frame2:
                target_box = get_most_centered_box(name2_in_frame2, img_shape)
        
        # 3. **二次预测逻辑**
        if not target_box and (frame1_boxes or frame2_boxes):
            print(f"[{unique_id}] No direct name found. Initiating 2nd pass (Re-scan)...")
            
            # 优先选择 frame1
            frame_to_rescan_boxes = frame1_boxes if frame1_boxes else frame2_boxes
            frame_label = "frame1" if frame1_boxes else "frame2"
            
            most_centered_frame = get_most_centered_box(frame_to_rescan_boxes, img_shape)
            
            if most_centered_frame:
                crop_dir_frame = os.path.join(save_dir, 'crops', frame_label)
                if os.path.exists(crop_dir_frame) and os.listdir(crop_dir_frame):
                    # 假设第一个裁剪图对应最居中的框
                    frame_crop_path = os.path.join(crop_dir_frame, os.listdir(crop_dir_frame)[0])
                    
                    print(f"[{unique_id}] Re-scanning crop: {frame_crop_path}")
                    
                    # 在frame的裁剪图上进行第二次预测
                    yolo_results_2 = yolo_model.predict(source=frame_crop_path, save_crop=True, project=project_name, name="predict_pass_2", device='cpu')
                    
                    if yolo_results_2[0].boxes:
                        boxes_2 = yolo_results_2[0].boxes
                        img_shape_2 = yolo_results_2[0].orig_shape
                        
                        all_boxes_2 = {int(b.cls): [] for b in boxes_2}
                        for b in boxes_2:
                            all_boxes_2[int(b.cls)].append(b)
                        
                        # 在第二次结果中寻找任何name
                        name_boxes_2 = all_boxes_2.get(0, [])
                        name1_boxes_2 = all_boxes_2.get(1, [])
                        name2_boxes_2 = all_boxes_2.get(3, [])
                        
                        potential_targets_2 = name_boxes_2 + name1_boxes_2 + name2_boxes_2
                        
                        if potential_targets_2:
                            print(f"[{unique_id}] Success! Found name in 2nd pass.")
                            target_box = get_most_centered_box(potential_targets_2, img_shape_2)
                            # 更新 save_dir 和 crop_dir 到第二次预测的结果
                            save_dir = yolo_results_2[0].save_dir
                        else:
                             print(f"[{unique_id}] 2nd pass failed to find any name.")
                else:
                    print(f"[{unique_id}] Could not find crop for '{frame_label}' to re-scan.")

        # 4. 如果二次预测后仍然没有目标，则执行最终降级策略
        if not target_box:
            print(f"[{unique_id}] 2nd pass failed or was not triggered. Applying final fallbacks.")
            final_fallback_targets = name_boxes + name1_boxes + name2_boxes
            if final_fallback_targets:
                target_box = get_most_centered_box(final_fallback_targets, img_shape)

        # 5. 如果最终还是没有找到，则报错
        if not target_box:
            return jsonify({"error": "未能识别到歌曲名，请尝试调整拍摄角度，确保画面清晰、无反光。"}), 500

        # 6. 处理最终的目标裁剪图
        target_label = yolo_model.names[int(target_box.cls)]
        print(f"[{unique_id}] Final target selected: a '{target_label}' box.")
        crop_dir = os.path.join(save_dir, 'crops', target_label)
        
        if not os.path.exists(crop_dir) or not os.listdir(crop_dir):
            return jsonify({"error": f"YOLO did not generate any crops for the final target '{target_label}'."}), 500
        
        crop_image_name = os.listdir(crop_dir)[0]
        crop_image_path = os.path.join(crop_dir, crop_image_name)

        # 7. OCR识别
        print(f"[{unique_id}] Processing final crop: {crop_image_path}")
        ocr_text = ""
        try:
            ocr_result = ocr_instance.predict(crop_image_path)
            if ocr_result and ocr_result[0] is not None:
                texts = ocr_result[0].get('rec_texts', [])
                filtered_texts = [text for text in texts if '等级' not in text]
                ocr_text = "".join(filtered_texts)
                print(f"[{unique_id}] OCR Result: {ocr_text}")
        except BaseException:
            print(f"--- [{unique_id}] OCR FAILED WITH UNKNOWN EXCEPTION ---")
            traceback.print_exc()
            ocr_text = ""

        if not ocr_text:
            # **最终修复**: 将OCR失败从500错误改为正常的业务失败，以便客户端重试
            print(f"[{unique_id}] OCR failed to produce text. Returning a soft error to trigger client retry.")
            return jsonify({"error": "OCR did not recognize any text from the best crop."})

        # 8. 匹配并返回结果
        # **终极路径修复**: 改为相对路径
        songs_json_path = os.path.join(app.root_path, 'songs.json')
        with open(songs_json_path, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        
        best_match_song = find_best_match(ocr_text, songs_data)

        if best_match_song:
            return jsonify(best_match_song)
        else:
            # **最终修复**: 根据指示，将“匹配失败”的错误统一为指导性提示
            print(f"[{unique_id}] OCR text '{ocr_text}' found, but no match in database. Prompting user to retry.")
            return jsonify({"error": "未能识别到歌曲名，请尝试调整拍摄角度，确保画面清晰、无反光。"})

    except BaseException as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(f"--- [{unique_id}] FATAL ERROR ---")
        traceback.print_exc()
        return jsonify({'error': 'An unexpected error occurred', 'details': error_message}), 500
    finally:
        # **监控模式改造与健壮性修复**
        monitoring_flag_path = os.path.join(app.root_path, 'monitoring.flag')
        flag_exists = os.path.exists(monitoring_flag_path)
        
        # 增加明确的诊断日志
        print(f"[{unique_id}] Final cleanup check. Monitoring flag at '{monitoring_flag_path}' exists: {flag_exists}.")

        if not flag_exists:
            print(f"[{unique_id}] Cleaning up temporary files...")
            # 删除 YOLO 预测生成的文件夹
            if save_dir and os.path.exists(save_dir):
                try:
                    shutil.rmtree(save_dir)
                    print(f"[{unique_id}] Successfully deleted prediction folder: {save_dir}")
                except Exception as e:
                    print(f"[{unique_id}] Error deleting prediction folder: {e}")
            
            # 删除上传的原始文件
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"[{unique_id}] Successfully deleted upload file: {filepath}")
                except Exception as e:
                    print(f"[{unique_id}] Error deleting upload file: {e}")
        else:
            print(f"[{unique_id}] Monitoring mode is ON. Temporary files are preserved.")

# --- **留言板改造**: 新增反馈接口 ---
@app.route('/api/feedback', methods=['POST'])
@token_required
def submit_feedback():
    """接收并存储用户的反馈"""
    data = request.get_json()
    feedback_type = data.get('type')
    content = data.get('content')
    contact = data.get('contact', '') # 联系方式是可选的

    if not feedback_type or not content:
        return jsonify({"error": "反馈类型和内容不能为空"}), 400

    # 从g对象获取用户名，这是由token_required装饰器设置的
    username = getattr(g, 'username', 'unknown_user')
    if not username or username == 'unknown_user':
         return jsonify({"error": "无法识别用户身份，请重新登录"}), 401

    feedback_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "username": username,
        "type": feedback_type,
        "content": content,
        "contact": contact
    }

    feedback_file_path = os.path.join(app.root_path, 'feedback.json')

    with feedback_lock:
        try:
            if os.path.exists(feedback_file_path):
                with open(feedback_file_path, 'r+', encoding='utf-8') as f:
                    # **健壮性修复**: 处理空文件或格式错误的文件
                    try:
                        feedbacks = json.load(f)
                        if not isinstance(feedbacks, list):
                            feedbacks = []
                    except json.JSONDecodeError:
                        feedbacks = []
                    
                    feedbacks.append(feedback_entry)
                    f.seek(0)
                    f.truncate()
                    json.dump(feedbacks, f, ensure_ascii=False, indent=4)
            else:
                with open(feedback_file_path, 'w', encoding='utf-8') as f:
                    json.dump([feedback_entry], f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"写入反馈文件时出错: {e}")
            traceback.print_exc()
            return jsonify({"error": "服务器内部错误，无法保存您的反馈"}), 500

    return jsonify({"message": "反馈已成功提交，感谢您的宝贵意见！"})


if __name__ == '__main__':
    # 当使用Waitress等生产服务器启动时，
    # 这个 __main__ 块通常不会被执行。
    # 但为了保持直接运行 `python app.py` 进行基本检查的可能性（虽然不推荐），
    # 我们可以保留会话恢复的调用。
    # app.run() 必须被移除或注释掉，因为它将被waitress-serve替代。
    restore_sessions_on_startup()
    print("应用已准备好，请通过 'waitress-serve' 命令来启动。")
