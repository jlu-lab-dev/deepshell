import os
import json
import platform
import shutil
import subprocess
import ctypes
import webbrowser
import urllib.parse

import psutil


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
        return atomic_result(True, "命令执行完成")
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


def list_running_applications():
    """获取当前正在运行的非系统关键进程列表。"""
    try:
        app_list = []
        # 定义一个简单的列表来过滤掉常见的系统/后台进程
        # This list can be expanded for more accuracy
        ignore_list = ['svchost.exe', 'conhost.exe', 'runtimebroker.exe',
                       'system', 'wininit.exe', 'services.exe', 'lsass.exe']

        for p in psutil.process_iter(['name', 'username']):
            # 只获取由当前用户启动的进程，并进行基本过滤
            if p.info['username'] and platform.system() == "Windows" and "SYSTEM" not in p.info['username']:
                if p.info['name'].lower() not in ignore_list:
                    app_list.append(p.info['name'])

        # 去重
        unique_apps = sorted(list(set(app_list)))

        return atomic_result(True, "成功获取正在运行的应用列表。", applications=unique_apps)
    except Exception as e:
        return atomic_result(False, f"获取应用列表失败: {e}")


def close_application_by_name(app_name: str):
    """根据提供的应用名称（例如 'chrome.exe'）关闭所有匹配的进程。"""
    if not app_name:
        return atomic_result(False, "应用名称不能为空。")

    try:
        closed_count = 0
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == app_name.lower():
                proc.terminate()  # 使用更温和的 terminate
                closed_count += 1

        if closed_count > 0:
            return atomic_result(True, f"成功关闭了 {closed_count} 个 '{app_name}' 进程。")
        else:
            return atomic_result(False, f"未找到名为 '{app_name}' 的正在运行的应用。")

    except Exception as e:
        return atomic_result(False, f"关闭应用 '{app_name}' 时发生错误: {e}")


def open_task_manager():
    """
    为用户打开操作系统的任务管理器。
    - Windows: 任务管理器 (taskmgr)
    - macOS: 活动监视器 (Activity Monitor)
    - Linux: 系统监视器 (System Monitor)
    """
    try:
        system = platform.system()
        command = []

        if system == "Windows":
            command = ['taskmgr']
            message = "任务管理器已启动。"
        elif system == "Darwin":  # macOS
            # 'open' 是macOS的命令行工具，用于打开文件和应用
            command = ['open', '/System/Applications/Utilities/Activity Monitor.app']
            message = "活动监视器已启动。"
        elif system == "Linux":
            # gnome-system-monitor 是GNOME桌面环境中最常见的系统监视器
            # 其他桌面环境可能有不同的命令，如 'ksysguard' (KDE)
            command = ['gnome-system-monitor']
            message = "系统监视器已启动。"
        else:
            return atomic_result(False, f"不支持在 {system} 操作系统上执行此操作。")

        # 使用 Popen 可以在不阻塞主程序的情况下启动应用
        subprocess.Popen(command)

        return atomic_result(True, message)

    except FileNotFoundError:
        # 如果找不到命令，比如在Linux上没有安装gnome-system-monitor
        return atomic_result(False, f"启动失败：未找到 '{command[0]}' 命令。请确保相关程序已安装。")
    except Exception as e:
        return atomic_result(False, f"启动任务管理器时发生未知错误: {e}")

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
    "list_running_applications": list_running_applications,
    "close_application_by_name": close_application_by_name,
    "open_task_manager": open_task_manager,
}


