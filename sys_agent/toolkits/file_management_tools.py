import os
import platform
import shutil
from pathlib import Path

import docx
import pandas as pd


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


def get_user_folder_path(folder_name: str):
    """获取用户特定文件夹（如 'Downloads', 'Documents'）的跨平台路径。"""
    try:
        # Path.home() 会获取用户的主目录
        folder_path = Path.home() / folder_name
        return atomic_result(True, f"成功获取 '{folder_name}' 文件夹路径。", path=str(folder_path))
    except Exception as e:
        return atomic_result(False, f"获取用户文件夹路径失败: {e}")


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
        return atomic_result(True, f"目录内容获取成功", files=files)
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
        return atomic_result(True, f"文件读取成功", content=content)
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
        return atomic_result(True, "获取当前工作目录成功", path=cwd)
    except Exception as e:
        return atomic_result(False, f"获取当前工作目录失败: {e}")


def find_file(filename, path=".", nums=-1):
    """
    在指定目录及其子目录下查找文件，返回所有匹配的文件路径列表。
    (版本 2.0 - 增强了对 None 输入的健壮性)
    """
    try:
        # --- 关键修改：在这里添加防御性检查 ---
        # 如果AI没有提供路径(传入了None)，我们就使用一个合理的默认值。
        # 这里我们仍然使用当前目录 "."，但更好的选择可能是用户的主目录。
        if path is None:
            print("警告: 未指定查找路径，将默认从当前目录开始查找。")
            search_path = "."
        else:
            search_path = path

        # 使用经过检查和处理的路径
        full_path = expanduser(os.path.normpath(search_path))

        matches = []
        for root, dirs, files in os.walk(full_path):
            for f in files:
                if filename in f:
                    matches.append(os.path.join(root, f))
                    if nums > 0 and len(matches) >= nums:
                        return atomic_result(True, f"找到{len(matches)}个匹配文件", found_files=matches)

        if matches:
            return atomic_result(True, f"找到{len(matches)}个匹配文件: " + ", ".join(m for m in matches), found_files=matches)
        else:
            return atomic_result(False, "未找到匹配文件", found_files=[])

    except Exception as e:
        # 现在的错误信息会更具体，因为我们已经处理了 NoneType 的情况
        return atomic_result(False, f"查找文件时发生意外错误: {e}", found_files=[])

def read_table_data(path: str):
    try:
        full_path = expanduser(os.path.normpath(path))
        if not os.path.exists(full_path):
            return atomic_result(False, f"文件不存在: {full_path}")

        if full_path.endswith('.csv'):
            df = pd.read_csv(full_path)
        elif full_path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(full_path)
        else:
            return atomic_result(False, "不支持的文件类型，仅支持 .csv, .xlsx, .xls")

        # 将DataFrame转换为JSON格式字符串，方便后续LLM处理
        # to_dict('records') 会生成 [{col1: val1, col2: val2}, ...] 的格式
        table_json = df.to_dict(orient='records')
        return atomic_result(True, f"成功读取表格数据，共 {len(df)} 行", table_data=table_json)

    except Exception as e:
        return atomic_result(False, f"读取表格数据失败: {e}")


def save_text_as_word_doc(directory: str, filename: str, content: str):
    """将给定的文本内容保存为 Word (.docx) 文件。"""
    try:
        # 确保文件名以 .docx 结尾
        if not filename.lower().endswith('.docx'):
            filename += '.docx'

        full_path = os.path.join(directory, filename)

        doc = docx.Document()
        doc.add_paragraph(content)
        doc.save(full_path)

        return atomic_result(True, f"文件已成功保存为 Word 文档。", file_path=full_path)
    except Exception as e:
        return atomic_result(False, f"保存 Word 文件失败: {e}")


def clean_system_cache():
    """
    清理操作系统默认的临时/缓存文件夹，以释放磁盘空间。
    能够自动识别 Windows, macOS, 和 Linux 的临时目录。
    """
    try:
        system = platform.system()
        if system == "Windows":
            temp_dir = Path(os.environ.get('TEMP', 'C:/Windows/Temp'))
        elif system == "Darwin":  # macOS
            temp_dir = Path.home() / "Library/Caches"
        else:  # Linux
            temp_dir = Path.home() / ".cache"

        if not temp_dir.exists() or not temp_dir.is_dir():
            return atomic_result(False, f"缓存目录 '{temp_dir}' 不存在。")

        cleaned_files_count = 0
        cleaned_folders_count = 0
        total_freed_space = 0

        for item in temp_dir.iterdir():
            try:
                item_size = os.path.getsize(item) if item.is_file() else sum(
                    f.stat().st_size for f in item.glob('**/*') if f.is_file())
                if item.is_dir():
                    shutil.rmtree(item)
                    cleaned_folders_count += 1
                else:
                    item.unlink()
                    cleaned_files_count += 1
                total_freed_space += item_size
            except Exception:
                # 忽略正在被使用的文件
                continue

        freed_space_mb = round(total_freed_space / (1024 * 1024), 2)
        message = (f"成功清理缓存。删除了 {cleaned_files_count} 个文件和 "
                   f"{cleaned_folders_count} 个文件夹，释放了约 {freed_space_mb} MB 空间。")
        return atomic_result(True, message,
                             cleaned_files_count=cleaned_files_count,
                             cleaned_folders_count=cleaned_folders_count,
                             freed_space_mb=freed_space_mb)
    except Exception as e:
        return atomic_result(False, f"清理系统缓存时发生错误: {e}")


# 工具映射表
FUNCTION_MAP = {
    "get_user_folder_path": get_user_folder_path,
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
    "find_file": find_file,
    "read_table_data": read_table_data,
    "save_text_as_word_doc": save_text_as_word_doc,
    "clean_system_cache": clean_system_cache,
}
