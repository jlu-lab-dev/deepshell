import os
import json
import platform
import shutil
import subprocess
import ctypes

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

def atomic_result(success, message, data=None):
    return {"success": success, "message": message, "data": data}

def open_calculator():
    try:
        os.system("calc")
        return atomic_result(True, "已打开计算器")
    except Exception as e:
        return atomic_result(False, f"打开计算器失败: {e}")

def open_file(path):
    try:
        full_path = expanduser(os.path.normpath(path))
        if not os.path.exists(full_path):
            return atomic_result(False, f"文件不存在: {full_path}")
        if os.name == 'nt':
            os.startfile(full_path)
        elif os.name == 'posix':
            if platform.system() == 'Darwin':
                os.system(f"open '{full_path}'")
            else:
                os.system(f"xdg-open '{full_path}'")
        return atomic_result(True, f"文件已打开: {full_path}")
    except Exception as e:
        return atomic_result(False, f"打开文件失败: {e}")

def list_directory(path='.'):
    try:
        full_path = expanduser(os.path.normpath(path))
        files = os.listdir(full_path)
        return atomic_result(True, f"目录内容获取成功", files)
    except Exception as e:
        return atomic_result(False, f"获取目录内容失败: {e}")

def create_file(path, content=None):
    """
    跨平台创建文件函数。

    :param path: 文件路径（支持绝对/相对路径）
    :param content: 要写入的内容（可选），默认为空文件
    :return: 成功时返回提示信息；失败返回错误信息
    """
    try:
        file_path = expanduser(os.path.normpath(path))
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(file_path):
            return atomic_result(False, f"文件已存在：{file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            if content is not None:
                f.write(content)
        return atomic_result(True, f"文件已创建：{file_path}")
    except Exception as e:
        return atomic_result(False, f"创建文件失败: {e}")

def read_file(path):
    try:
        file_path = expanduser(os.path.normpath(path))
        if not os.path.exists(file_path):
            return atomic_result(False, f"文件不存在：{file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return atomic_result(True, f"文件读取成功", content)
    except Exception as e:
        return atomic_result(False, f"读取文件失败: {e}")

def write_file(path, content):
    try:
        file_path = expanduser(os.path.normpath(path))
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return atomic_result(True, f"文件写入成功：{file_path}")
    except Exception as e:
        return atomic_result(False, f"写入文件失败: {e}")

def rename_file(src, dst):
    try:
        src_path = expanduser(os.path.normpath(src))
        dst_path = expanduser(os.path.normpath(dst))
        os.rename(src_path, dst_path)
        return atomic_result(True, f"文件已重命名为：{dst_path}")
    except Exception as e:
        return atomic_result(False, f"重命名文件失败: {e}")

def copy_file(src, dst):
    try:
        src_path = expanduser(os.path.normpath(src))
        dst_path = expanduser(os.path.normpath(dst))
        shutil.copy2(src_path, dst_path)
        return atomic_result(True, f"文件已复制到：{dst_path}")
    except Exception as e:
        return atomic_result(False, f"复制文件失败: {e}")

def move_file(src, dst):
    try:
        src_path = expanduser(os.path.normpath(src))
        dst_path = expanduser(os.path.normpath(dst))
        shutil.move(src_path, dst_path)
        return atomic_result(True, f"文件已移动到：{dst_path}")
    except Exception as e:
        return atomic_result(False, f"移动文件失败: {e}")

def create_directory(path):
    try:
        dir_path = expanduser(os.path.normpath(path))
        os.makedirs(dir_path, exist_ok=True)
        return atomic_result(True, f"目录已创建：{dir_path}")
    except Exception as e:
        return atomic_result(False, f"创建目录失败: {e}")

def delete_file(path):
    try:
        file_path = expanduser(os.path.normpath(path))
        os.remove(file_path)
        return atomic_result(True, f"文件已删除：{file_path}")
    except Exception as e:
        return atomic_result(False, f"删除文件失败: {e}")

def get_current_directory():
    try:
        cwd = os.getcwd()
        return atomic_result(True, "获取当前工作目录成功", cwd)
    except Exception as e:
        return atomic_result(False, f"获取当前工作目录失败: {e}")

def shutdown_system():
    try:
        if os.name == 'nt':
            os.system("shutdown /s /t 1")
        else:
            os.system("sudo shutdown now")
        return atomic_result(True, "系统已关机")
    except Exception as e:
        return atomic_result(False, f"关机失败: {e}")

def run_program(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return atomic_result(True, "命令执行完成", result.stdout + result.stderr)
    except Exception as e:
        return atomic_result(False, f"命令执行失败: {e}")

def find_file(filename, path=".", nums=-1):
    """
    在指定目录及其子目录下查找文件，返回所有匹配的文件路径列表。
    :param filename: 要查找的文件名（支持部分匹配或全名）
    :param path: 起始查找目录，默认为当前目录
    :param nums: 最多返回的匹配文件数，-1 表示不限制
    :return: 匹配到的文件路径列表
    """
    try:
        full_path = expanduser(os.path.normpath(path))
        matches = []
        for root, dirs, files in os.walk(full_path):
            for f in files:
                if filename in f:
                    matches.append(os.path.join(root, f))
                    if nums > 0 and len(matches) >= nums:
                        return atomic_result(True, f"找到{len(matches)}个匹配文件", matches)
        if matches:
            return atomic_result(True, f"找到{len(matches)}个匹配文件", matches)
        else:
            return atomic_result(False, "未找到匹配文件", [])
    except Exception as e:
        return atomic_result(False, f"查找文件失败: {e}")

def set_wallpaper(image_path):
    try:
        image_path = expanduser(os.path.normpath(image_path))
        if not os.path.exists(image_path):
            return atomic_result(False, f"图片文件不存在: {image_path}")
        # SPI_SETDESKWALLPAPER = 20
        ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 3)
        return atomic_result(True, "壁纸设置成功")
    except Exception as e:
        return atomic_result(False, f"设置壁纸失败: {e}")

def open_control_panel():
    try:
        if os.name == 'nt':
            os.system("control")
            return atomic_result(True, "已打开控制面板")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"打开控制面板失败: {e}")

def open_network_settings():
    try:
        if os.name == 'nt':
            os.system("start ms-settings:network")
            return atomic_result(True, "已打开网络设置")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"打开网络设置失败: {e}")

def open_display_settings():
    try:
        if os.name == 'nt':
            os.system("start ms-settings:display")
            return atomic_result(True, "已打开显示设置")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"打开显示设置失败: {e}")

def open_sound_settings():
    try:
        if os.name == 'nt':
            os.system("start ms-settings:sound")
            return atomic_result(True, "已打开声音设置")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"打开声音设置失败: {e}")

def open_bluetooth_settings():
    try:
        if os.name == 'nt':
            os.system("start ms-settings:bluetooth")
            return atomic_result(True, "已打开蓝牙设置")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"打开蓝牙设置失败: {e}")

def lock_screen():
    try:
        if os.name == 'nt':
            ctypes.windll.user32.LockWorkStation()
            return atomic_result(True, "已锁定屏幕")
        else:
            return atomic_result(False, "当前系统不支持此操作")
    except Exception as e:
        return atomic_result(False, f"锁定屏幕失败: {e}")

# 工具映射表
FUNCTION_MAP = {
    "open_calculator": open_calculator,
    "open_file": open_file,
    "list_directory": list_directory,
    "create_file": create_file,
    "read_file": read_file,
    "write_file": write_file,
    "rename_file": rename_file,
    "copy_file": copy_file,
    "move_file": move_file,
    "create_directory": create_directory,
    "delete_file": delete_file,
    "get_current_directory": get_current_directory,
    "shutdown_system": shutdown_system,
    "run_program": run_program,
    "find_file": find_file,
    "set_wallpaper": set_wallpaper,
    "open_control_panel": open_control_panel,
    "open_network_settings": open_network_settings,
    "open_display_settings": open_display_settings,
    "open_sound_settings": open_sound_settings,
    "open_bluetooth_settings": open_bluetooth_settings,
    "lock_screen": lock_screen,
}

def get_function_schemas():
    """返回所有函数的 json schema 字符串，可用于 prompt 动态插入"""
    json_path = os.path.join(os.path.dirname(__file__), "functions.json")
    with open(json_path, "r", encoding="utf-8") as f:
        FUNCTION_SCHEMAS = json.load(f)
        return json.dumps(FUNCTION_SCHEMAS, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    set_wallpaper(r"D:\AS\书影音\照片\cloud.jpg")

    