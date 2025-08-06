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
MUSIC_DATA_URL = "https://www.diving-fish.com/api/maimaidxprober/music_data"

def check_and_update_songs():
    """
    检查并更新本地的 songs.json 文件。
    使用 ETag 缓存机制来避免不必要的下载。
    
    返回:
        一个包含 'status' 和 'message' 键的字典。
    """
    # 1. 读取本地保存的 ETag（如果存在）
    current_etag = None
    if os.path.exists(ETAG_FILE_PATH):
        try:
            with open(ETAG_FILE_PATH, 'r', encoding='utf-8') as f:
                current_etag = f.read().strip()
        except Exception as e:
            print(f"读取 ETag 文件失败: {e}")
            # 如果读取失败，当作没有 ETag 处理

    # 2. 构造请求头
    headers = {
        'Accept': 'application/json'
    }
    if current_etag:
        # ETag 格式本身包含双引号，直接使用即可
        headers['If-None-Match'] = current_etag
    
    print(f"正在检查歌曲数据更新... 使用 ETag: {current_etag}")

    try:
        # 3. 发送 GET 请求到 Diving-Fish API
        response = requests.get(MUSIC_DATA_URL, headers=headers, timeout=30) # 30秒超时

        # 4. 根据响应状态码处理
        if response.status_code == 200:
            # --- 数据已更新 ---
            print("检测到新版本的歌曲数据，正在下载并更新...")
            
            # 获取新数据和新的 ETag
            new_data = response.json()
            new_etag = response.headers.get('ETag')

            # 写入新的 JSON 数据到 songs.json
            # 使用 ensure_ascii=False 来正确处理非 ASCII 字符
            # 不使用 indent 来减小文件体积，提高加载效率
            with open(SONGS_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False)

            # 如果响应头中有新的 ETag，则保存它
            if new_etag:
                with open(ETAG_FILE_PATH, 'w', encoding='utf-8') as f:
                    f.write(new_etag)
                print(f"已保存新的 ETag: {new_etag}")
            
            return {"status": "success", "message": f"歌曲数据已成功更新！共加载 {len(new_data)} 首歌曲。"}

        elif response.status_code == 304:
            # --- 数据未修改 ---
            print("服务器确认本地歌曲数据已是最新版本。")
            return {"status": "not_modified", "message": "本地歌曲数据已是最新版本，无需更新。"}
        
        else:
            # --- 其他 HTTP 错误 ---
            error_message = f"检查更新失败，服务器返回非预期的状态码: {response.status_code}"
            print(error_message)
            return {"status": "error", "message": error_message}

    except requests.exceptions.Timeout:
        error_message = "检查更新时网络连接超时，请稍后重试。"
        print(error_message)
        return {"status": "error", "message": error_message}
    except requests.exceptions.RequestException as e:
        error_message = f"检查更新时发生网络错误: {e}"
        print(error_message)
        return {"status": "error", "message": error_message}
    except json.JSONDecodeError:
        error_message = "无法解析从服务器返回的数据，响应可能不是有效的JSON格式。"
        print(error_message)
        return {"status": "error", "message": error_message}
    except Exception as e:
        error_message = f"更新过程中发生未知错误: {e}"
        print(error_message)
        return {"status": "error", "message": error_message}

if __name__ == '__main__':
    # 用于直接运行此脚本进行测试
    print("手动执行歌曲数据更新脚本...")
    result = check_and_update_songs()
    print(f"更新结果: {result['message']}")
