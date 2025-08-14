import os
import json
import requests

# --- 常量定义 ---
# 获取此文件所在的目录，然后推断出项目根目录
ADMIN_DIR = os.path.dirname(__file__)
MAIN_APP_ROOT = os.path.abspath(os.path.join(ADMIN_DIR, '..'))

# 定义需要操作的文件的绝对路径
SONGS_JSON_PATH = os.path.join(MAIN_APP_ROOT, 'songs.json')
ETAG_FILE_PATH = os.path.join(MAIN_APP_ROOT, 'songs.etag')
ALIASES_JSON_PATH = os.path.join(MAIN_APP_ROOT, 'aliases.json') # **新增**: 别名文件路径
MUSIC_DATA_URL = "https://www.diving-fish.com/api/maimaidxprober/music_data"
ALIASES_DATA_URL = "https://www.yuzuchan.moe/api/maimaidx/maimaidxalias" # **新增**: 别名数据URL

def update_aliases():
    """
    下载并更新本地的 aliases.json 文件。
    这个函数不使用ETag，直接覆盖。
    
    返回:
        一个包含 'status' 和 'message' 键的字典。
    """
    print("正在尝试更新歌曲别名数据...")
    try:
        response = requests.get(ALIASES_DATA_URL, timeout=20)
        if response.status_code == 200:
            # **健壮性修复**: 确保响应是JSON
            new_data = response.json()
            with open(ALIASES_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2) # 使用indent增加可读性
            print("歌曲别名数据更新成功。")
            return {"status": "success", "message": "歌曲别名数据更新成功。"}
        else:
            message = f"更新别名失败，服务器返回状态码: {response.status_code}"
            print(message)
            return {"status": "error", "message": message}
    except requests.exceptions.RequestException as e:
        message = f"更新别名时发生网络错误: {e}"
        print(message)
        return {"status": "error", "message": message}
    except json.JSONDecodeError:
        message = "无法解析别名数据，响应可能不是有效的JSON。"
        print(message)
        return {"status": "error", "message": message}
    except Exception as e:
        message = f"更新别名时发生未知错误: {e}"
        print(message)
        return {"status": "error", "message": message}

def check_and_update_songs():
    """
    **V3重构**: 检查并更新本地的 songs.json 和 aliases.json 文件。
    确保两种文件的更新过程相对独立，一个失败不影响另一个。
    """
    # --- Part 1: 更新 songs.json ---
    songs_status = "unknown"
    songs_message = ""
    
    # 1a. 读取ETag
    current_etag = None
    if os.path.exists(ETAG_FILE_PATH):
        try:
            with open(ETAG_FILE_PATH, 'r', encoding='utf-8') as f:
                current_etag = f.read().strip()
        except Exception as e:
            print(f"读取 ETag 文件失败: {e}")

    # 1b. 构造请求头
    headers = {'Accept': 'application/json'}
    if current_etag:
        headers['If-None-Match'] = current_etag
    
    print(f"正在检查歌曲数据更新... 使用 ETag: {current_etag}")

    # 1c. 发送请求并处理
    try:
        response = requests.get(MUSIC_DATA_URL, headers=headers, timeout=30)
        if response.status_code == 200:
            new_data = response.json()
            new_etag = response.headers.get('ETag')
            with open(SONGS_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False)
            if new_etag:
                with open(ETAG_FILE_PATH, 'w', encoding='utf-8') as f:
                    f.write(new_etag)
            songs_message = f"歌曲数据已成功更新（共 {len(new_data)} 首）。"
            songs_status = "success"
        elif response.status_code == 304:
            songs_message = "歌曲数据已是最新。"
            songs_status = "not_modified"
        else:
            songs_message = f"歌曲数据更新失败（服务器状态码: {response.status_code}）。"
            songs_status = "error"
    except Exception as e:
        songs_message = f"歌曲数据更新时发生错误: {e}"
        songs_status = "error"
    
    print(songs_message)

    # --- Part 2: 更新 aliases.json (总是执行) ---
    aliases_result = update_aliases()
    
    # --- Part 3: 组合结果并返回 ---
    final_message = f"{songs_message} {aliases_result['message']}"
    
    # 决定最终状态：任何一方失败都算失败
    final_status = "error"
    if songs_status in ["success", "not_modified"] and aliases_result['status'] == "success":
        # 如果歌曲数据没变，但别名更新了，也算作成功
        final_status = "success" if songs_status == "success" or aliases_result.get("refreshed") else "not_modified"

    return {"status": final_status, "message": final_message}

if __name__ == '__main__':
    # 用于直接运行此脚本进行测试
    print("手动执行歌曲数据更新脚本...")
    result = check_and_update_songs()
    print(f"更新结果: {result['message']}")
