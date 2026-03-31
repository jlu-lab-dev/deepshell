# sys_agent/toolkits/file_management_tools.py
"""
文件管理工具集。
提供文件/目录的创建、读写、复制、移动、删除、查找等操作。
所有函数遵循统一返回规范，引用共享的 _base 模块。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import docx
import pandas as pd

from ._base import expanduser, resolve_path, ok, fail, require_non_empty


# ─── 基础路径工具 ────────────────────────────────────────────────────────────


def _resolve(path: str) -> str:
    return resolve_path(path)


def _parent_exists(path: str) -> str:
    """确保父目录存在，返回规范化后的路径。"""
    resolved = _resolve(path)
    parent = os.path.dirname(resolved)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    return resolved


# ─── 文件夹操作 ─────────────────────────────────────────────────────────────


def get_user_folder_path(folder_name: str) -> dict[str, Any]:
    """获取用户系统标准文件夹的完整路径。"""
    try:
        require_non_empty(folder_name, "folder_name")
        path = str(Path.home() / folder_name)
        return ok(f"成功获取 '{folder_name}' 文件夹路径。", path=path)
    except ValueError as e:
        return fail(f"参数错误: {e}")


def create_directory(path: str, base_directory: str | None = None) -> dict[str, Any]:
    """创建目录，支持在指定父目录下创建子目录。"""
    try:
        require_non_empty(path, "path")
        if base_directory:
            full_path = _resolve(os.path.join(base_directory, path))
        else:
            full_path = _resolve(path)
        os.makedirs(full_path, exist_ok=True)
        return ok(f"目录已成功创建或已存在: {full_path}", directory_path=full_path)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"创建目录失败: {e}")


# ─── 文件操作 ────────────────────────────────────────────────────────────────


def open_file(path: str) -> dict[str, Any]:
    """使用系统默认程序打开文件。"""
    try:
        require_non_empty(path, "path")
        full_path = _resolve(path)
        if not os.path.exists(full_path):
            return fail(f"文件不存在: {full_path}")
        if os.name == "nt":
            os.startfile(full_path)
        elif os.name == "posix":
            import platform
            if platform.system() == "Darwin":
                os.system(f"open '{full_path}'")
            else:
                os.system(f"xdg-open '{full_path}'")
        return ok(f"文件已打开: {full_path}")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"打开文件失败: {e}")


def create_file(path: str, content: str | None = None) -> dict[str, Any]:
    """创建新文件，可选写入初始内容。"""
    try:
        require_non_empty(path, "path")
        full_path = _parent_exists(path)
        if os.path.exists(full_path):
            return fail(f"文件已存在，无法覆盖: {full_path}")
        with open(full_path, "w", encoding="utf-8") as f:
            if content is not None:
                f.write(content)
        return ok(f"文件已创建: {full_path}")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"创建文件失败: {e}")


def read_file(path: str) -> dict[str, Any]:
    """读取文本文件内容（UTF-8）。"""
    try:
        require_non_empty(path, "path")
        full_path = _resolve(path)
        if not os.path.exists(full_path):
            return fail(f"文件不存在: {full_path}")
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return ok(f"文件读取成功（共 {len(content)} 字符）", content=content)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"读取文件失败: {e}")


def write_file(path: str, content: str) -> dict[str, Any]:
    """向文件写入内容（覆盖模式）。"""
    try:
        require_non_empty(path, "path")
        full_path = _parent_exists(path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return ok(f"文件写入成功: {full_path}")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"写入文件失败: {e}")


def rename_file(src: str, dst: str) -> dict[str, Any]:
    """在同一目录下重命名文件或文件夹。"""
    try:
        require_non_empty(src, "src")
        require_non_empty(dst, "dst")
        src_path = _resolve(src)
        dst_path = os.path.join(os.path.dirname(src_path), dst)
        os.rename(src_path, dst_path)
        return ok(f"已重命名: {os.path.basename(src_path)} → {dst}", renamed_to=dst_path)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"重命名失败: {e}")


def copy_file(src: str, dst: str) -> dict[str, Any]:
    """复制文件到目标路径。"""
    try:
        require_non_empty(src, "src")
        require_non_empty(dst, "dst")
        src_path = _resolve(src)
        dst_path = _resolve(dst)
        shutil.copy2(src_path, dst_path)
        return ok(f"文件已复制到: {dst_path}", copied_to=dst_path)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"复制文件失败: {e}")


def move_file(src: str, dst: str) -> dict[str, Any]:
    """移动文件到目标路径。"""
    try:
        require_non_empty(src, "src")
        require_non_empty(dst, "dst")
        src_path = _resolve(src)
        dst_path = _resolve(dst)
        shutil.move(src_path, dst_path)
        return ok(f"文件已移动到: {dst_path}", moved_to=dst_path)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"移动文件失败: {e}")


def batch_move_files(
    file_paths: list[str], destination_directory: str,
) -> dict[str, Any]:
    """将多个文件一次性移动到目标目录。"""
    try:
        if not file_paths:
            return fail("文件列表不能为空")
        require_non_empty(destination_directory, "destination_directory")
        dest = _resolve(destination_directory)
        if not os.path.isdir(dest):
            return fail(f"目标路径不是有效目录: {dest}")

        success_log: list[dict[str, str]] = []
        failure_log: list[dict[str, str]] = []
        for fp in file_paths:
            try:
                shutil.move(_resolve(fp), os.path.join(dest, os.path.basename(_resolve(fp))))
                success_log.append({"file": os.path.basename(fp), "moved_to": dest})
            except OSError as e:
                failure_log.append({"file": fp, "error": str(e)})

        return ok(
            f"批量移动完成。成功: {len(success_log)} 个，失败: {len(failure_log)} 个。",
            success_details=success_log,
            failure_details=failure_log,
        )
    except ValueError as e:
        return fail(f"参数错误: {e}")


def delete_file(path: str) -> dict[str, Any]:
    """删除指定文件。"""
    try:
        require_non_empty(path, "path")
        full_path = _resolve(path)
        if not os.path.exists(full_path):
            return fail(f"文件不存在: {full_path}")
        os.remove(full_path)
        return ok(f"文件已删除: {full_path}")
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"删除文件失败: {e}")


def get_current_directory() -> dict[str, Any]:
    """获取当前工作目录。"""
    try:
        cwd = os.getcwd()
        return ok("获取当前工作目录成功", path=cwd)
    except OSError as e:
        return fail(f"获取当前工作目录失败: {e}")


# ─── 搜索查找 ───────────────────────────────────────────────────────────────


def find_file(
    filename: str, path: str = ".", nums: int = -1,
) -> dict[str, Any]:
    """在目录树中递归搜索文件名含关键词的文件。"""
    try:
        require_non_empty(filename, "filename")
        search_root = _resolve(path) if path else os.getcwd()
        matches: list[str] = []
        for root, _, files in os.walk(search_root):
            for f in files:
                if filename in f:
                    matches.append(os.path.join(root, f))
                    if nums > 0 and len(matches) >= nums:
                        return ok(f"找到 {len(matches)} 个匹配文件", found_paths=matches)
        if matches:
            return ok(f"找到 {len(matches)} 个匹配文件", found_paths=matches)
        return ok("未找到匹配文件", found_paths=[])
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"搜索文件时出错: {e}")


def find_files_by_extension(
    directory: str, extensions: list[str],
) -> dict[str, Any]:
    """在指定目录（不含子目录）中按扩展名筛选文件。"""
    try:
        require_non_empty(directory, "directory")
        if not extensions:
            return fail("扩展名列表不能为空")
        full_path = _resolve(directory)
        if not os.path.isdir(full_path):
            return fail(f"指定的路径不是一个有效目录: {full_path}")

        lower_exts = [ext.lower() for ext in extensions]
        found: list[str] = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isfile(item_path):
                ext = Path(item).suffix.lower()
                if ext in lower_exts:
                    found.append(item_path)

        if not found:
            return ok("操作成功，但未找到匹配扩展名的文件", file_paths=[])
        return ok(f"成功找到 {len(found)} 个匹配文件", file_paths=found)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"按扩展名查找时出错: {e}")


def find_path_by_keywords(
    keywords: list[str], search_directory: str, search_depth: int = 3,
) -> dict[str, Any]:
    """通过关键词模糊匹配查找文件和文件夹，按匹配度排序。"""
    try:
        if not keywords:
            return fail("关键词列表不能为空")
        require_non_empty(search_directory, "search_directory")
        full_path = _resolve(search_directory)
        if not os.path.isdir(full_path):
            return fail(f"搜索目录无效: {full_path}", found_paths=[])

        matches: list[dict[str, Any]] = []
        for root, dirs, files in os.walk(full_path):
            # 深度控制
            rel = os.path.relpath(root, full_path)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth >= search_depth:
                dirs[:] = []  # 不继续遍历子目录

            for name in dirs + files:
                score = sum(1 for kw in keywords if kw.lower() in name.lower())
                if score > 0:
                    matches.append({"path": os.path.join(root, name), "score": score})

        if not matches:
            return ok("未找到与关键词匹配的文件或文件夹", found_paths=[])

        sorted_paths = [m["path"] for m in sorted(matches, key=lambda x: x["score"], reverse=True)]
        return ok(f"成功找到 {len(sorted_paths)} 个匹配项", found_paths=sorted_paths)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except OSError as e:
        return fail(f"关键词查找出错: {e}")


# ─── 批量重命名 ─────────────────────────────────────────────────────────────


def batch_rename_files(
    file_paths: list[str], rename_pattern: str, start_number: int = 1,
) -> dict[str, Any]:
    """批量重命名文件，pattern 中必须含 {num} 占位符。"""
    try:
        if not file_paths:
            return fail("文件列表不能为空")
        if "{num}" not in rename_pattern:
            return fail("重命名模式中必须包含编号占位符 '{num}'")

        success_log: list[dict[str, str]] = []
        failure_log: list[dict[str, str]] = []
        for i, fp in enumerate(file_paths):
            try:
                p = Path(_resolve(fp))
                new_name = rename_pattern.format(num=start_number + i) + p.suffix
                new_path = p.parent / new_name
                os.rename(p, new_path)
                success_log.append({"from": str(p), "to": str(new_path)})
            except OSError as e:
                failure_log.append({"file": str(fp), "error": str(e)})

        return ok(
            f"批量重命名完成。成功: {len(success_log)} 个，失败: {len(failure_log)} 个。",
            success_details=success_log,
            failure_details=failure_log,
        )
    except ValueError as e:
        return fail(f"参数错误: {e}")


def batch_add_prefix_to_filenames(
    file_paths: list[str], prefix: str,
) -> dict[str, Any]:
    """为文件列表统一添加前缀。"""
    try:
        if not file_paths:
            return fail("文件列表不能为空")

        success_log: list[dict[str, str]] = []
        failure_log: list[dict[str, str]] = []
        for fp in file_paths:
            try:
                p = Path(_resolve(fp))
                new_path = p.parent / (prefix + p.name)
                os.rename(p, new_path)
                success_log.append({"from": str(p), "to": str(new_path)})
            except OSError as e:
                failure_log.append({"file": str(fp), "error": str(e)})

        return ok(
            f"批量添加前缀完成。成功: {len(success_log)} 个，失败: {len(failure_log)} 个。",
            success_details=success_log,
            failure_details=failure_log,
        )
    except ValueError as e:
        return fail(f"参数错误: {e}")


# ─── 表格文档 ────────────────────────────────────────────────────────────────


def read_table_data(path: str) -> dict[str, Any]:
    """读取 CSV 或 Excel 表格并返回 JSON 结构。"""
    try:
        require_non_empty(path, "path")
        full_path = _resolve(path)
        if not os.path.exists(full_path):
            return fail(f"文件不存在: {full_path}")
        if full_path.endswith(".csv"):
            df = pd.read_csv(full_path)
        elif full_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(full_path)
        else:
            return fail("不支持的文件类型，仅支持 .csv、.xlsx、.xls")
        table_json: list[dict[str, Any]] = df.to_dict(orient="records")
        return ok(f"成功读取表格数据，共 {len(df)} 行", table_data=table_json)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except Exception as e:
        return fail(f"读取表格数据失败: {e}")


def save_text_as_word_doc(
    directory: str, filename: str, content: str,
) -> dict[str, Any]:
    """将文本保存为 Word 文档。"""
    try:
        require_non_empty(directory, "directory")
        require_non_empty(filename, "filename")
        require_non_empty(content, "content")
        full_dir = _resolve(directory)
        if not os.path.isdir(full_dir):
            return fail(f"目录不存在: {full_dir}")
        if not filename.lower().endswith(".docx"):
            filename += ".docx"
        full_path = os.path.join(full_dir, filename)
        doc = docx.Document()
        doc.add_paragraph(content)
        doc.save(full_path)
        return ok(f"Word 文档已保存: {full_path}", file_path=full_path)
    except ValueError as e:
        return fail(f"参数错误: {e}")
    except Exception as e:
        return fail(f"保存 Word 文件失败: {e}")


# ─── 系统维护 ───────────────────────────────────────────────────────────────


def clean_system_cache() -> dict[str, Any]:
    """清理操作系统临时缓存目录。"""
    try:
        import platform
        system = platform.system()
        if system == "Windows":
            temp_dir = Path(os.environ.get("TEMP", "C:/Windows/Temp"))
        elif system == "Darwin":
            temp_dir = Path.home() / "Library/Caches"
        else:
            temp_dir = Path.home() / ".cache"

        if not temp_dir.exists():
            return fail(f"缓存目录不存在: {temp_dir}")

        files, folders = 0, 0
        freed: int = 0
        for item in temp_dir.iterdir():
            try:
                size = os.path.getsize(item) if item.is_file() else sum(
                    f.stat().st_size for f in item.glob("**/*") if f.is_file()
                )
                if item.is_dir():
                    shutil.rmtree(item)
                    folders += 1
                else:
                    item.unlink()
                    files += 1
                freed += size
            except OSError:
                continue

        freed_mb = round(freed / (1024 * 1024), 2)
        return ok(
            f"清理完成。删除了 {files} 个文件和 {folders} 个文件夹，释放约 {freed_mb} MB。",
            cleaned_files_count=files,
            cleaned_folders_count=folders,
            freed_space_mb=freed_mb,
        )
    except Exception as e:
        return fail(f"清理系统缓存时发生错误: {e}")


# ─── 导出映射 ───────────────────────────────────────────────────────────────


FUNCTION_MAP: dict[str, callable] = {
    "get_user_folder_path": get_user_folder_path,
    "open_file": open_file,
    "create_file": create_file,
    "read_file": read_file,
    "write_file": write_file,
    "rename_file": rename_file,
    "copy_file": copy_file,
    "move_file": move_file,
    "batch_move_files": batch_move_files,
    "create_directory": create_directory,
    "delete_file": delete_file,
    "get_current_directory": get_current_directory,
    "find_file": find_file,
    "find_files_by_extension": find_files_by_extension,
    "find_path_by_keywords": find_path_by_keywords,
    "batch_rename_files": batch_rename_files,
    "batch_add_prefix_to_filenames": batch_add_prefix_to_filenames,
    "read_table_data": read_table_data,
    "save_text_as_word_doc": save_text_as_word_doc,
    "clean_system_cache": clean_system_cache,
}
