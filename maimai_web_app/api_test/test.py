import requests
import os

# --- 配置 ---
API_URL = "http://www.maiscan.top/api/recognize"
API_KEY = "c74cd5ccad0784a2077e444715881a2c3d77d528fd1a7049635552096370eb67" # 替换为你的密钥
IMAGE_PATH = "C:\\myself_prodect\\test.jpg" # 替换为你的图片路径

# --- 检查文件是否存在 ---
if not os.path.exists(IMAGE_PATH):
    print(f"错误: 图片文件未找到 at {IMAGE_PATH}")
else:
    # --- 准备请求 ---
    headers = {
        "X-API-Key": API_KEY
    }
    files = {
        "file": (os.path.basename(IMAGE_PATH), open(IMAGE_PATH, 'rb'), 'image/jpeg')
    }

    # --- 发送请求 ---
    try:
        response = requests.post(API_URL, headers=headers, files=files, timeout=60)
        
        print(f"状态码: {response.status_code}")
        
        # --- 处理响应 ---
        if response.status_code == 200:
            print("识别成功!")
            print("响应内容:")
            print(response.json())
        else:
            print("识别失败或发生错误。")
            try:
                print("错误信息:")
                print(response.json())
            except requests.exceptions.JSONDecodeError:
                print("无法解析响应内容。")
                print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"请求时发生网络错误: {e}")