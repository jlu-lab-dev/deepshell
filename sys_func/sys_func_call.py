import os
import sys
import subprocess


def sys_func_call(command):
    """执行 Python 系统调用代码"""
    try:
        exec(command)
    except Exception as e:
        print(f"执行失败: {e}")

