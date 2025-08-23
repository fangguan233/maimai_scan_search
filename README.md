# Maimai_Scan_Search

本项目是是一款 Web 应用程序，允许用户上传他们的 Maimai DX 游戏截图，并自动识别歌曲名称。
本项目还提供了一个受保护的 API 端点，允许开发者以接口方式调用核心的图像识别功能。

## 功能

*   **网页界面**: 将图片查询和搜索的图像识别功能集成到网页中，提供用户友好的界面。
*   **API 访问**: 为开发者提供一个安全的 API 端点，用于集成到其他应用中。
*   **个人成绩查询 (查分器)**: 用户登录后，应用能够：
    *   **同步 Diving-Fish 数据**: 通过代理登录到 `diving-fish.com`，拉取并缓存用户的个人资料、游玩记录、B50 等数据并合理展示。
    *   **成绩展示**: 在识别出歌曲后，能立刻显示玩家在该歌曲上所有谱面的最佳成绩。
    *   **推分计算**: 提供了易用的推分计算方式。
    *   **B50 查询**: 提供专门的页面展示可交互的 Best 50 成绩列表（包含新旧版本）。
    *   **数据刷新**: 用户可以手动触发，从 Diving-Fish 服务器同步最新的成绩，保持本地缓存数据为最新。
 
![图片1](./image/image1.jpg)
![图片2](./image/image2.jpg)
![图片3](./image/image3.jpg)

## 安装与启动

### 1. 环境准备
-   **Conda**: 必须使用 Conda 来管理环境，因为项目的依赖（如 PyTorch）通过 Conda 安装能获得最好的兼容性。
-   **Python**: 版本必须为 `3.9`。
-   **Git**: 用于克隆项目。

### 2. 克隆与安装依赖

```bash
# 克隆项目 (如果尚未克隆)
# git clone https://github.com/fangguan233/maimai_scan_search
# cd maimai_web_app

# 1. 使用 Conda 创建并激活一个新环境
#    (我们指定 python=3.9)
conda create --name newyolo python=3.9
conda activate newyolo

# 2. 安装核心依赖
#    目前仅支持cuda版本，其他环境未作尝试可自行尝试
#    a. 安装与CUDA兼容的PyTorch（注意选择cuda版本，cuda可向下兼容不可向上兼容）
#       首先通过 `nvidia-smi` 查询你的CUDA版本
#       例如: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
#
#    b. 安装cpu版本的PaddlePaddle（把显卡性能让给yolo，cpu版本的ocr性能并不差）
#       python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
#
#    c. 安装yolo
#       cd 到maimai_scan_search\ultralytics-main下
#       pip install -e .
#
#    d. 安装其他依赖
#       pip install paddleocr fuzzywuzzy flask
```

## API 使用

### 接口: `/api/recognize`

#### 1. 请求

-   **方法**: `POST`
-   **URL**: `http://www.maiscan.top/api/recognize`
-   **头部 (Headers)**:
    -   `X-API-Key`: `c74cd5ccad0784a2077e444715881a2c3d77d528fd1a7049635552096370eb67` - 
-   **正文 (Body)**: `multipart/form-data`
    -   `file`: `C:\\myself_prodect\\test.jpg` - 

#### 2. 响应

##### 成功 (200 OK)

如果识别成功，服务器将返回一个包含所有匹配版本的歌曲信息的 JSON 数组。

**示例:**
```json
[
    {
        "basic_info": {
            "artist": "Mameyudoufu",
            "bpm": 143,
            "from": "maimai でらっくす BUDDiES",
            "genre": "其他游戏",
            "is_new": false,
            "release_date": "",
            "title": "Sunday Night feat Kanata.N"
        },
        "charts": [
            {
                "charter": "-",
                "notes": [ 102, 12, 4, 26, 8 ]
            },
            {
                "charter": "-",
                "notes": [ 207, 14, 17, 25, 7 ]
            },
            {
                "charter": "みそかつ侍",
                "notes": [ 260, 112, 28, 22, 27 ]
            },
            {
                "charter": "ものくろっく",
                "notes": [ 431, 59, 57, 30, 33 ]
            }
        ],
        "cids": [ 8125, 8126, 8127, 8128 ],
        "cover_url": "/cover/11585",
        "ds": [ 3.0, 6.5, 10.8, 13.5 ],
        "id": "11585",
        "level": [ "3", "6", "10+", "13" ],
        "title": "Sunday Night feat Kanata.N",
        "type": "DX"
    }
]
```

##### 失败

-   **400 Bad Request**: 请求格式错误（例如，没有上传文件）。
    ```json
    { "error": "No file part" }
    ```
-   **401 Unauthorized**: API 密钥缺失。
    ```json
    { "error": "API key is missing" }
    ```
-   **403 Forbidden**: API 密钥无效或不匹配。
    ```json
    { "error": "Invalid API key" }
    ```
-   **404 Not Found**: 服务器成功处理了图片，但无法在数据库中找到匹配的歌曲。
    ```json
    { "error": "未能识别到歌曲名，请尝试调整拍摄角度，确保画面清晰、无反光。" }
    ```
-   **500 Internal Server Error**: 服务器在处理过程中发生意外错误（例如，模型加载失败，图片处理异常）。
    ```json
    { "error": "An unexpected error occurred", "details": "<具体的错误信息>" }
    ```


### Python 示例

```python
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

