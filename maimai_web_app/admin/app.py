import os
import subprocess
import psutil
import shutil
import json # **反馈功能**: 导入json模块
from flask import Flask, render_template, jsonify, request
from datetime import datetime
import threading
# **终极进程管理**: 导入Windows特定的模块
if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    # **健壮性修复**: 手动定义subprocess模块缺少的Windows常量
    CREATE_SUSPENDED = 0x00000400
from .updater import check_and_update_songs # **版本更新**: 导入新模块 (使用相对导入修复ModuleNotFoundError)

# --- 配置 ---
MAIN_APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG_ARCHIVE_PATH = os.path.join(MAIN_APP_ROOT, 'logs')
UPLOADS_PATH = os.path.join(MAIN_APP_ROOT, 'uploads')
RUNS_PATH = os.path.join(MAIN_APP_ROOT, 'runs', 'detect')
START_SCRIPT_PATH = os.path.join(MAIN_APP_ROOT, 'start_server.bat')

app = Flask(__name__)

# --- 全局变量 ---
main_app_process = None
log_thread = None
current_log_file = None
MONITORING_FLAG_PATH = os.path.join(MAIN_APP_ROOT, 'monitoring.flag')
monitoring_enabled = os.path.exists(MONITORING_FLAG_PATH)
# **终极进程管理**: 作业对象句柄
g_job_handle = None

# **守护进程改造**
app_should_be_running = False  # 标记应用是否应该处于运行状态
auto_restart_enabled = False   # 标记是否开启自动重启
guardian_thread = None         # 守护线程的句柄

# --- 辅助函数 ---
def is_process_running(pid):
    """检查给定PID的进程是否仍在运行"""
    if pid is None:
        return False
    return psutil.pid_exists(pid)

def _start_app_internal():
    """
    **守护进程改造**: 内部启动函数，不处理HTTP请求，只负责启动逻辑。
    返回一个包含状态和消息的字典。
    """
    global main_app_process, log_thread, current_log_file, app_should_be_running
    
    try:
        os.makedirs(LOG_ARCHIVE_PATH, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_filename = f"app-{timestamp}.log"
        current_log_file = os.path.join(LOG_ARCHIVE_PATH, log_filename)

        # **终极进程管理**: 在Windows上，使用作业对象确保子进程随父进程退出
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        if os.name == 'nt':
            # 启动时挂起，以便我们能将其加入作业
            creationflags |= CREATE_SUSPENDED # **健壮性修复**: 使用我们自己定义的常量
            
        main_app_process = subprocess.Popen(
            [START_SCRIPT_PATH],
            cwd=MAIN_APP_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            creationflags=creationflags,
            bufsize=1
        )

        if os.name == 'nt':
            # 将子进程加入到我们的作业对象中
            ctypes.windll.kernel32.AssignProcessToJobObject(g_job_handle, int(main_app_process._handle))
            # **健壮性修复**: 使用psutil来恢复进程，而不是调用不存在的方法
            psutil.Process(main_app_process.pid).resume()

        log_thread = threading.Thread(
            target=log_writer,
            args=(main_app_process.stdout, current_log_file)
        )
        log_thread.daemon = True
        log_thread.start()
        
        app_should_be_running = True # 标记为应该运行
        
        message = f"主应用已启动，进程ID: {main_app_process.pid}，日志记录于 {log_filename}"
        print(message) # 在后台日志中也打印一份
        return {"status": "success", "message": message}
    except Exception as e:
        message = f"内部启动失败: {str(e)}"
        print(message)
        return {"status": "error", "message": message}

def guardian_thread_func():
    """
    **守护进程改造**: 守护线程的核心逻辑。
    """
    import time
    print("守护线程已启动，将每10秒检查一次主应用状态。")
    while True:
        time.sleep(10)
        
        # 仅当开关开启，且应用本应在运行时才进行检查
        if not auto_restart_enabled or not app_should_be_running:
            continue

        # 如果进程句柄存在，但通过PID检查发现进程已不存在
        if main_app_process and not is_process_running(main_app_process.pid):
            print("守护线程：检测到主应用意外终止！正在尝试自动重启...")
            _start_app_internal()

def log_writer(pipe, log_file_path):
    """一个在后台线程中运行的函数，用于将管道内容写入日志文件"""
    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            for line in iter(pipe.readline, ''):
                f.write(line)
                f.flush()
    except Exception as e:
        print(f"Log writer thread encountered an error: {e}")
    finally:
        pipe.close()
        print("Log writer thread finished.")

# --- API 路由 ---

@app.route('/')
def index():
    """渲染管理主页"""
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_app():
    """
    **守护进程改造**: 启动主应用的API端点。
    """
    if main_app_process and is_process_running(main_app_process.pid):
        return jsonify({"status": "error", "message": "主应用已在运行中。"}), 400
    
    result = _start_app_internal()
    
    if result['status'] == 'success':
        return jsonify(result)
    else:
        return jsonify(result), 500

@app.route('/api/stop', methods=['POST'])
def stop_app():
    """
    **守护进程改造**: 停止主应用，并更新状态标志。
    """
    global main_app_process, log_thread, current_log_file, app_should_be_running
    if not main_app_process or not is_process_running(main_app_process.pid):
        return jsonify({"status": "error", "message": "主应用未在运行或进程信息丢失。"}), 400

    try:
        # 标记为不应该运行，这样守护线程就不会重启它
        app_should_be_running = False
        
        subprocess.run(f"taskkill /F /PID {main_app_process.pid} /T", check=True, shell=True, capture_output=True)
        
        if log_thread and log_thread.is_alive():
            log_thread.join(timeout=2)

        main_app_process = None
        log_thread = None
        
        return jsonify({"status": "success", "message": "主应用已手动停止。"})
    except Exception as e:
        # 如果停止失败，恢复标记，因为应用可能还在运行
        app_should_be_running = True
        return jsonify({"status": "error", "message": f"停止失败: {str(e)}"}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """
    **守护进程改造**: 获取主应用运行状态，并附带自动重启状态。
    """
    global main_app_process, auto_restart_enabled
    
    is_running = main_app_process and is_process_running(main_app_process.pid)
    
    # 如果进程不在了，但标记是应该运行，说明可能已崩溃
    status_text = "Running"
    if not is_running and app_should_be_running:
        status_text = "Crashed" # 前端可以根据这个状态显示不同颜色
    elif not is_running:
        status_text = "Stopped"

    return jsonify({
        "status": status_text,
        "pid": main_app_process.pid if is_running else None,
        "log_file": os.path.basename(current_log_file) if current_log_file else None,
        "auto_restart_enabled": auto_restart_enabled
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取当前日志文件的内容"""
    global current_log_file
    if not current_log_file or not os.path.exists(current_log_file):
        return jsonify({"logs": "当前没有活动的日志文件。"})
    
    try:
        with open(current_log_file, 'r', encoding='utf-8') as f:
            # 读取最多最后200行
            lines = f.readlines()
            log_content = "".join(lines[-200:])
        return jsonify({"logs": log_content})
    except Exception as e:
        return jsonify({"error": f"读取日志失败: {str(e)}"}), 500

@app.route('/api/monitoring_status', methods=['GET'])
def get_monitoring_status():
    """获取监控模式的当前状态"""
    global monitoring_enabled
    return jsonify({"enabled": monitoring_enabled})

@app.route('/api/toggle_auto_restart', methods=['POST'])
def toggle_auto_restart():
    """
    **守护进程改造**: 切换自动重启功能的开关。
    """
    global auto_restart_enabled
    auto_restart_enabled = not auto_restart_enabled
    message = "已开启自动重启守护" if auto_restart_enabled else "已关闭自动重启守护"
    return jsonify({"status": "success", "enabled": auto_restart_enabled, "message": message})

@app.route('/api/toggle_monitoring', methods=['POST'])
def toggle_monitoring():
    """切换监控模式的开关"""
    global monitoring_enabled
    monitoring_enabled = not monitoring_enabled
    
    try:
        if monitoring_enabled:
            # 开启监控：创建标志文件
            with open(MONITORING_FLAG_PATH, 'w') as f:
                f.write('on')
            message = "识别监控已开启，临时文件将被保留。"
        else:
            # 关闭监控：删除标志文件
            if os.path.exists(MONITORING_FLAG_PATH):
                os.remove(MONITORING_FLAG_PATH)
            message = "识别监控已关闭，临时文件将被自动删除。"
        
        return jsonify({"status": "success", "enabled": monitoring_enabled, "message": message})
    except Exception as e:
        # 如果操作失败，回滚状态
        monitoring_enabled = not monitoring_enabled
        return jsonify({"status": "error", "message": f"切换失败: {str(e)}"}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """列出 uploads 和 runs 目录下的文件和文件夹（仅在监控模式下）"""
    global monitoring_enabled
    if not monitoring_enabled:
        return jsonify({"uploads": [], "runs": [], "message": "监控模式已关闭，不显示文件列表。"})

    try:
        uploads_files = [f for f in os.listdir(UPLOADS_PATH)] if os.path.exists(UPLOADS_PATH) else []
        runs_files = [f for f in os.listdir(RUNS_PATH)] if os.path.exists(RUNS_PATH) else []
        return jsonify({
            "uploads": uploads_files,
            "runs": runs_files
        })
    except Exception as e:
        return jsonify({"error": f"获取文件列表失败: {str(e)}"}), 500

@app.route('/api/update_songs', methods=['POST'])
def update_songs_data():
    """
    **版本更新**: 触发歌曲数据的检查与更新。
    """
    global main_app_process
    # 健壮性检查：如果主应用正在运行，则不允许更新，防止文件被占用或数据不一致
    if main_app_process and is_process_running(main_app_process.pid):
        return jsonify({"status": "error", "message": "主应用正在运行中，请先停止应用再更新数据。"}), 409 # 409 Conflict

    # 调用更新逻辑
    result = check_and_update_songs()
    
    # 根据更新结果返回不同的状态码
    if result['status'] == 'error':
        return jsonify(result), 500
    else:
        return jsonify(result), 200

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    """删除指定的文件或文件夹"""
    data = request.get_json()
    dir_type = data.get('type')
    filename = data.get('name')

    if not dir_type or not filename:
        return jsonify({"status": "error", "message": "参数不完整。"}), 400

    if dir_type == 'uploads':
        base_path = UPLOADS_PATH
    elif dir_type == 'runs':
        base_path = RUNS_PATH
    else:
        return jsonify({"status": "error", "message": "无效的目录类型。"}), 400

    path_to_delete = os.path.join(base_path, filename)
    
    if not os.path.abspath(path_to_delete).startswith(os.path.abspath(base_path)):
        return jsonify({"status": "error", "message": "检测到非法路径。"}), 400

    try:
        if os.path.isfile(path_to_delete):
            os.remove(path_to_delete)
            message = f"文件 '{filename}' 已删除。"
        elif os.path.isdir(path_to_delete):
            shutil.rmtree(path_to_delete)
            message = f"文件夹 '{filename}' 已删除。"
        else:
            return jsonify({"status": "error", "message": "文件或文件夹不存在。"}), 404
        
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        return jsonify({"status": "error", "message": f"删除失败: {str(e)}"}), 500

# --- **反馈功能**: 新增获取反馈信息的API ---
@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    """读取并返回 feedback.json 的内容"""
    feedback_file_path = os.path.join(MAIN_APP_ROOT, 'feedback.json')
    
    if not os.path.exists(feedback_file_path):
        return jsonify([]) # 如果文件不存在，返回空列表

    try:
        with open(feedback_file_path, 'r', encoding='utf-8') as f:
            # **健壮性修复**: 处理空文件或格式错误的文件
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    return jsonify([]) # 如果不是列表，也返回空
            except json.JSONDecodeError:
                return jsonify([]) # 如果JSON解析失败，返回空列表
        
        # **数据处理**: 按时间戳倒序排序，最新的在最前面
        sorted_data = sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
        return jsonify(sorted_data)
    except Exception as e:
        return jsonify({"error": f"读取反馈文件失败: {str(e)}"}), 500

# --- **守护进程改造**: 在应用加载时启动守护线程 ---
guardian_thread = threading.Thread(target=guardian_thread_func)
guardian_thread.daemon = True
guardian_thread.start()

# --- **终极进程管理**: 创建并配置作业对象 ---
def setup_job_object():
    """在Windows上创建并配置一个作业对象，用于管理子进程生命周期"""
    global g_job_handle
    if os.name != 'nt':
        return

    # 定义Windows API结构体和常量
    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ('BasicLimitInformation', wintypes.DWORD64), # Simplified for this use case
            ('IoInfo', wintypes.DWORD64),
            ('ProcessMemoryLimit', ctypes.c_size_t),
            ('JobMemoryLimit', ctypes.c_size_t),
            ('PeakProcessMemoryUsed', ctypes.c_size_t),
            ('PeakJobMemoryUsed', ctypes.c_size_t),
            ('ExtendedLimitInformation', wintypes.DWORD64),
            ('CompletionKey', wintypes.LPVOID),
        ]

    JobObjectExtendedLimitInformation = 9
    JOBOBJECT_EXTENDED_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

    # 创建作业对象
    g_job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
    if not g_job_handle:
        raise ctypes.WinError()

    # 获取当前进程句柄并加入作业
    h_process = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.kernel32.AssignProcessToJobObject(g_job_handle, h_process):
        raise ctypes.WinError()

    # 设置作业对象的限制信息
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.ExtendedLimitInformation = JOBOBJECT_EXTENDED_LIMIT_KILL_ON_JOB_CLOSE
    
    if not ctypes.windll.kernel32.SetInformationJobObject(
        g_job_handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info)
    ):
        raise ctypes.WinError()
    
    print("作业对象已成功创建并配置，子进程将随后台一同退出。")

if __name__ == '__main__':
    # 在启动Web服务器之前，先设置好作业对象
    setup_job_object()
    # 这个块在通过 waitress 启动时不会执行，但为了直接运行测试，保留它
    app.run(host='0.0.0.0', port=8081, debug=False)
