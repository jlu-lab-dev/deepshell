import os
import json
import platform
import subprocess

def open_calculator():
    os.system("calc")

def expanduser(path):
    """兼容 Windows 的 os.path.expanduser 实现"""
    if "~" in path:
        if platform.system() == "Windows":
            import getpass
            username = getpass.getuser()
            home = os.path.join("C:\\Users", username)
            path = path.replace("~", home)
        else:
            path = os.path.expanduser(path)
    return path

def open_file(path):
    full_path = expanduser(path)
    full_path = os.path.normpath(full_path)  # 规范化路径格式

    if not os.path.exists(full_path):
        return f"文件不存在: {full_path}"

    if os.name == 'nt':  # Windows
        os.startfile(full_path)
    elif os.name == 'posix':
        if platform.system() == 'Darwin':  # macOS
            os.system(f"open '{full_path}'")
        else:  # Linux
            os.system(f"xdg-open '{full_path}'")
    return f"文件已打开: {full_path}"

def list_directory(path='.'):
    return "\n".join(os.listdir(path))

def create_file(path, content=None):
    """
    跨平台创建文件函数。

    :param path: 文件路径（支持绝对/相对路径）
    :param content: 要写入的内容（可选），默认为空文件
    :return: 成功时返回提示信息；失败返回错误信息
    """
    try:
        # 规范化路径格式
        file_path = os.path.normpath(path)

        # 扩展用户路径（如 ~/ 替换为用户主目录）
        file_path = os.path.expanduser(file_path)

        # 获取文件所在目录
        directory = os.path.dirname(file_path)

        # 如果目录不存在，则创建
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # 如果文件已存在
        if os.path.exists(file_path):
            return True, f"文件已存在：{file_path}"

        # 写入内容（如果提供）
        mode = 'w' if isinstance(content, str) else 'wb'
        with open(file_path, mode) as f:
            if content is not None:
                f.write(content)

        return f"文件已创建：{file_path}"

    except Exception as e:
        return f"创建文件失败: {str(e)}"

def create_directory(path):
    os.makedirs(path, exist_ok=True)
    return f"目录已创建：{path}"

def delete_file(path):
    os.remove(path)
    return f"文件已删除：{path}"

def get_current_directory():
    return os.getcwd()

def shutdown_system():
    if os.name == 'nt':
        os.system("shutdown /s /t 1")
    else:
        os.system("sudo shutdown now")
    return f"系统已关机"

def run_program(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

# 工具映射表
FUNCTION_MAP = {
    "open_calculator": open_calculator,
    "open_file": open_file,
    "list_directory": list_directory,
    "create_directory": create_directory,
    "create_file": create_file,
    "delete_file": delete_file,
    "get_current_directory": get_current_directory,
    "shutdown_system": shutdown_system,
    "run_program": run_program,
}

def load_function_schemas():
    json_path = os.path.join(os.path.dirname(__file__), "functions.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_function_schemas():
    """返回所有函数的 json schema 字符串，可用于 prompt 动态插入"""
    FUNCTION_SCHEMAS = load_function_schemas()
    return json.dumps(FUNCTION_SCHEMAS, ensure_ascii=False, indent=2)