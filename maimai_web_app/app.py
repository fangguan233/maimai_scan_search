import os
import json
import shutil
import time
import traceback
from flask import Flask, request, jsonify, render_template
from ultralytics import YOLO
from paddleocr import PaddleOCR
from fuzzywuzzy import process

# --- 1. 创建Flask应用 ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- 2. 在应用启动时加载所有模型 (只运行一次) ---
print("正在加载YOLOv8模型...")
YOLO_MODEL_PATH = r"C:\myself_prodect\maimai_scan_search\ultralytics-main\runs\detect\train2\weights\best.pt"
yolo_model = YOLO(YOLO_MODEL_PATH)
print("YOLOv8模型加载成功！")

print("正在加载PaddleOCR模型...")
# 使用经过我们调试验证的最优配置
ocr_instance = PaddleOCR(
    device="cpu", # 官方指定参数：强制使用CPU，避免与YOLO的GPU资源冲突
    enable_mkldnn=True,
    cpu_threads=2,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    text_detection_model_name="PP-OCRv5_mobile_det",
)
print("PaddleOCR模型加载成功！")
# ----------------------------------------------------

def find_best_match(ocr_text, songs_data):
    """使用 fuzzywuzzy 查找最佳匹配的歌曲"""
    song_names = [song['title'] for song in songs_data]
    best_match = process.extractOne(ocr_text, song_names)
    if best_match and best_match[1] > 60:
        for song in songs_data:
            if song['title'] == best_match[0]:
                return song
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # 保存上传的文件
    filename = "test_upload.jpg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    save_dir = None # 初始化保存目录变量
    try:
        # --- 3. 直接使用全局的YOLO模型进行预测和裁剪 ---
        print("Running YOLOv8 prediction...")
        yolo_results = yolo_model.predict(source=filepath, save_crop=True)
        if not yolo_results:
            return jsonify({"error": "YOLO did not produce any results."}), 500
        
        save_dir = yolo_results[0].save_dir
        crop_dir = os.path.join(save_dir, 'crops', 'name')
        print(f"Crops saved to: {crop_dir}")

        if not os.path.exists(crop_dir) or not os.listdir(crop_dir):
            return jsonify({"error": "YOLO did not generate any crops."}), 500

        # --- 4. 直接使用全局的PaddleOCR模型进行识别 ---
        ocr_text = ""
        for crop_image_name in os.listdir(crop_dir):
            crop_image_path = os.path.join(crop_dir, crop_image_name)
            
            # **遵从指示**：移除服务器端重试，让其快速失败
            print(f"Processing with OCR: {crop_image_path}")
            ocr_result = ocr_instance.predict(crop_image_path)
            
            if ocr_result and ocr_result[0] is not None:
                texts = ocr_result[0].get('rec_texts', [])
                filtered_texts = [text for text in texts if '等级' not in text]
                ocr_text += "".join(filtered_texts)
                print(f"OCR Result for {crop_image_name}: {''.join(filtered_texts)}")

        if not ocr_text:
            return jsonify({"error": "OCR did not recognize any text."}), 500

        # --- 5. 加载歌曲数据并进行匹配 ---
        songs_json_path = r"C:\myself_prodect\maimai_scan_search\maimai_web_app\songs.json"
        with open(songs_json_path, 'r', encoding='utf-8') as f:
            songs_data = json.load(f)
        
        best_match_song = find_best_match(ocr_text, songs_data)

        # --- 6. 返回结果 ---
        if best_match_song:
            return jsonify(best_match_song)
        else:
            return jsonify({"error": "No matching song found.", "ocr_text": ocr_text})

    except BaseException as e: # 使用BaseException捕获所有类型的异常
        error_message = f"An unexpected error occurred: {str(e)}"
        print("--- FATAL ERROR ---")
        traceback.print_exc() # 打印完整的错误日志
        print("-------------------")
        return jsonify({'error': 'An unexpected error occurred', 'details': error_message}), 500
    finally:
        # --- 7. 清理 ---
        if save_dir and os.path.exists(save_dir):
            shutil.rmtree(save_dir)

if __name__ == '__main__':
    # debug=False, 因为这会加载两次模型，导致端口占用和内存问题
    app.run(host='0.0.0.0', port=5000, debug=False)
