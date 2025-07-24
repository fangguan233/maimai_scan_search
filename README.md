# maimai_scan_search
# Maimai 歌曲名称识别器

通过wmc们上传的手机截图或照片，自动识别出《Maimai》（舞萌DX）中的歌曲名称，并返回该歌曲的详细数据。
## 使用方式
## 环境搭建

为了运行此项目，您需要一个正确配置的 Conda 虚拟环境。

1.  **创建 Conda 环境**
    ```bash
    conda create -n yolov8 python=3.9
    ```

2.  **激活（进入）环境**
    ```bash
    conda activate yolov8
    ```

3.  **安装核心依赖**
    目前仅支持cuda版本，其他环境未作尝试可自行尝试
        ```bash
        # 安装与CUDA兼容的PyTorch（注意选择cuda版本，cuda可向下兼容不可向上兼容）（能用11.8就用11，8）
        cuda版本查询 nvidia-smi
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

        # 安装cpu版本的PaddlePaddle（把显卡性能让给yolo，cpu版本的ocr性能并不差）（用gpu版本目前存在bug）
        python -m pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

        # 安装yolo
        cd 到maimai_scan_search\ultralytics-main下
        pip install -e .

        # 安装其他依赖
        pip install paddleocr fuzzywuzzy flask
        ```

5.  **模型准备**
    - **YOLOv8 模型**: 请确保您的YOLOv8模型权重文件位于 `maimai_scan_search\ultralytics-main\runs\detect\train2\weights\best.pt`。（暂时默认）
    - **歌曲数据**: 请确保歌曲数据库文件 `songs.json` 位于 `maimai_web_app` 目录下。（暂时默认）
  
      
## 运行方法

1.  确保您已经激活了正确的 `yolov8` Conda环境。
2.  在项目根目录 `maimai_web_app` 下，直接双击运行 `start_server.bat` 批处理文件。
3.  该脚本会自动激活环境、启动Flask服务器，并用默认浏览器打开 `http://127.0.0.1:5000`。


## 核心技术
- **后端框架**: [Flask](https://flask.palletsprojects.com/) - 一个轻量级的Python Web框架。
- **目标检测**: [YOLOv8](https://github.com/ultralytics/ultralytics) - 用于从上传的图片中精确定位歌曲名称所在的区域。
- **文字识别 (OCR)**: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 用于从YOLO裁剪出的图像中识别出具体的歌曲名称文字。
- **模糊匹配**: [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) - 用于将OCR识别出的文字与歌曲数据库进行模糊匹配，以提高识别的准确率和容错性。
- **前端**: 原生 HTML, CSS, 和 JavaScript，实现了健壮的客户端重试逻辑，以应对网络波动和服务器偶发错误。
