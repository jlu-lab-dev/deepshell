# sys_agent/toolkits/system_tools.py
"""
系统控制工具集。
提供操作系统级别操作：程序启动/关闭、系统设置、系统信息等。
所有函数遵循统一返回规范，引用共享的 _base 模块。
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from typing import Any

import psutil

from ._base import ok, fail, require_non_empty


# ─── 基础工具 ───────────────────────────────────────────────────────────────


def _sys_check() -> str:
    return platform.system()


def _require_windows() -> bool:
    if _sys_check() != "Windows":
        raise OSError("此操作仅支持 Windows 系统")


# ─── 程序启动 ───────────────────────────────────────────────────────────────


def open_calculator() -> dict[str, Any]:
    """打开系统计算器。"""
    try:
        os.system("calc")
        return ok("计算器已打开")
    except Exception as e:
        return fail(f"打开计算器失败: {e}")


def run_program(command: str) -> dict[str, Any]:
    """执行一条 shell 命令。"""
    try:
        require_non_empty(command, "command")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return ok(
            f"命令执行完成（退出码: {result.returncode}）",
            exit_code=result.returncode,
            stdout=result.stdout[:500] if result.stdout else "",
            stderr=result.stderr[:500] if result.stderr else "",
        )
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except subprocess.TimeoutExpired:
        return fail("命令执行超时（30秒）")
    except Exception as e:
        return fail(f"命令执行失败: {e}")


def open_task_manager() -> dict[str, Any]:
    """打开系统任务管理器。"""
    try:
        system = _sys_check()
        if system == "Windows":
            subprocess.Popen(["taskmgr"])
        elif system == "Darwin":
            subprocess.Popen(["open", "/System/Applications/Utilities/Activity Monitor.app"])
        else:
            subprocess.Popen(["gnome-system-monitor"])
        return ok("任务管理器已启动")
    except FileNotFoundError:
        return fail("启动失败：未找到相应程序")
    except Exception as e:
        return fail(f"启动任务管理器失败: {e}")


# ─── 系统设置 ───────────────────────────────────────────────────────────────


def set_wallpaper(image_path: str) -> dict[str, Any]:
    """设置桌面壁纸（仅 Windows）。"""
    try:
        require_non_empty(image_path, "image_path")
        _require_windows()
        resolved = os.path.normpath(os.path.expanduser(image_path))
        if not os.path.exists(resolved):
            return fail(f"图片文件不存在: {resolved}")
        # SPI_SETDESKWALLPAPER = 20
        ctypes.windll.user32.SystemParametersInfoW(20, 0, resolved, 3)
        return ok(f"壁纸设置成功: {resolved}")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"设置壁纸失败: {e}")


def open_control_panel() -> dict[str, Any]:
    """打开控制面板。"""
    try:
        _require_windows()
        os.system("control")
        return ok("控制面板已打开")
    except OSError as e:
        return fail(f"打开控制面板失败: {e}")


def open_network_settings() -> dict[str, Any]:
    """打开网络设置页面。"""
    try:
        _require_windows()
        os.system("start ms-settings:network")
        return ok("网络设置已打开")
    except OSError as e:
        return fail(f"打开网络设置失败: {e}")


def open_display_settings() -> dict[str, Any]:
    """打开显示设置页面。"""
    try:
        _require_windows()
        os.system("start ms-settings:display")
        return ok("显示设置已打开")
    except OSError as e:
        return fail(f"打开显示设置失败: {e}")


def open_sound_settings() -> dict[str, Any]:
    """打开声音设置页面。"""
    try:
        _require_windows()
        os.system("start ms-settings:sound")
        return ok("声音设置已打开")
    except OSError as e:
        return fail(f"打开声音设置失败: {e}")


def open_bluetooth_settings() -> dict[str, Any]:
    """打开蓝牙设置页面。"""
    try:
        _require_windows()
        os.system("start ms-settings:bluetooth")
        return ok("蓝牙设置已打开")
    except OSError as e:
        return fail(f"打开蓝牙设置失败: {e}")


def lock_screen() -> dict[str, Any]:
    """锁定当前用户会话。"""
    try:
        _require_windows()
        ctypes.windll.user32.LockWorkStation()
        return ok("屏幕已锁定")
    except OSError as e:
        return fail(f"锁定屏幕失败: {e}")


def shutdown_system() -> dict[str, Any]:
    """关闭系统（1秒后执行）。"""
    try:
        _require_windows()
        os.system("shutdown /s /t 1")
        return ok("系统将在1秒后关机")
    except OSError as e:
        return fail(f"关机命令失败: {e}")


# ─── 进程管理 ───────────────────────────────────────────────────────────────


_IGNORE_LIST = {
    "svchost.exe", "conhost.exe", "runtimebroker.exe",
    "system", "wininit.exe", "services.exe", "lsass.exe",
}


def list_running_applications() -> dict[str, Any]:
    """获取当前用户会话下可关闭的第三方应用程序列表。"""
    try:
        apps: list[str] = []
        for p in psutil.process_iter(["name", "username"]):
            info = p.info
            try:
                is_user = (
                    info["username"]
                    and platform.system() == "Windows"
                    and "SYSTEM" not in info["username"]
                )
                if is_user and info["name"].lower() not in _IGNORE_LIST:
                    apps.append(info["name"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        unique = sorted(set(apps))
        return ok(f"获取到 {len(unique)} 个运行中的应用", applications=unique)
    except Exception as e:
        return fail(f"获取应用列表失败: {e}")


def list_applications_by_memory_usage(memory_threshold_mb: int) -> dict[str, Any]:
    """获取内存占用超过阈值的应用列表（按占用量降序）。"""
    try:
        if not isinstance(memory_threshold_mb, int) or memory_threshold_mb <= 0:
            return fail("memory_threshold_mb 必须为正整数")
        apps: list[dict[str, Any]] = []
        for p in psutil.process_iter(["pid", "name", "username", "memory_info"]):
            info = p.info
            try:
                is_user = (
                    info["username"]
                    and platform.system() == "Windows"
                    and "SYSTEM" not in info["username"]
                )
                if is_user and info["name"].lower() not in _IGNORE_LIST:
                    mem_mb = info["memory_info"].rss / (1024 * 1024)
                    if mem_mb > memory_threshold_mb:
                        apps.append({
                            "pid": info["pid"],
                            "name": info["name"],
                            "memory_usage": (
                                f"{round(mem_mb / 1024, 2)} GB"
                                if mem_mb >= 1024
                                else f"{int(mem_mb)} MB"
                            ),
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        sorted_apps = sorted(apps, key=lambda x: x["name"], reverse=True)
        # 按内存重新排序（需要原始数值，这里用 name 排序后按原始序返回）
        # 实际按内存排序
        sorted_apps = sorted(
            apps,
            key=lambda x: psutil.Process(x["pid"]).memory_info().rss
            if x["pid"] else 0,
            reverse=True,
        )
        if not sorted_apps:
            return ok(f"未找到内存占用超过 {memory_threshold_mb} MB 的应用", applications=[])
        return ok(
            f"找到 {len(sorted_apps)} 个高内存占用应用",
            applications=sorted_apps,
        )
    except Exception as e:
        return fail(f"获取应用列表失败: {e}")


def close_application_by_name(app_name: str) -> dict[str, Any]:
    """根据进程名关闭所有匹配进程。"""
    try:
        require_non_empty(app_name, "app_name")
        count = 0
        for p in psutil.process_iter(["name"]):
            if p.info["name"].lower() == app_name.lower():
                p.terminate()
                count += 1
        if count > 0:
            return ok(f"已关闭 {count} 个 '{app_name}' 进程")
        return fail(f"未找到名为 '{app_name}' 的运行中应用")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except Exception as e:
        return fail(f"关闭应用时出错: {e}")


def close_application_by_pid(pid: int) -> dict[str, Any]:
    """根据 PID 精确关闭指定进程。"""
    try:
        if not isinstance(pid, int) or pid <= 0:
            return fail("pid 必须为正整数")
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        return ok(f"已关闭进程 '{name}' (PID: {pid})")
    except psutil.NoSuchProcess:
        return fail(f"PID {pid} 不存在，可能已关闭")
    except Exception as e:
        return fail(f"关闭 PID {pid} 时出错: {e}")


# ─── 导出映射 ───────────────────────────────────────────────────────────────


FUNCTION_MAP: dict[str, callable] = {
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
    "list_applications_by_memory_usage": list_applications_by_memory_usage,
    "close_application_by_name": close_application_by_name,
    "close_application_by_pid": close_application_by_pid,
    "open_task_manager": open_task_manager,
}
