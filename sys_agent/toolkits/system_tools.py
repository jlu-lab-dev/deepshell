import os
import json
import platform
import shutil
import subprocess
import ctypes
import webbrowser
import urllib.parse


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


def atomic_result(success, message, **kwargs):
    """
    一个更灵活的结果生成器。

    Args:
        success (bool): 操作是否成功。
        message (str): 操作结果的消息。
        **kwargs: 任意数量的关键字参数，将作为返回字典的核心数据。
                  例如: found_files=["path1", "path2"]

    Returns:
        dict: 一个包含执行状态和所有传入数据的字典。
    """
    result = {
        "success": success,
        "message": message
    }
    # 将所有传入的关键字参数合并到结果字典中
    result.update(kwargs)
    return result


def open_calculator():
    try:
        os.system("calc")
        return atomic_result(True, "已打开计算器")
    except Exception as e:
        return atomic_result(False, f"打开计算器失败: {e}")


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
    "shutdown_system": shutdown_system,
    "run_program": run_program,
    "set_wallpaper": set_wallpaper,
    "open_control_panel": open_control_panel,
    "open_network_settings": open_network_settings,
    "open_display_settings": open_display_settings,
    "open_sound_settings": open_sound_settings,
    "open_bluetooth_settings": open_bluetooth_settings,
    "lock_screen": lock_screen,
}


