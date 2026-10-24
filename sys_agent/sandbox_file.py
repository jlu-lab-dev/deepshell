"""DeepShell Agent 文件沙箱。

所属模块：sys_agent。
职责：将写入限制在专用目录的直接子级，拒绝路径、设备名、覆盖与符号链接。
当前只支持创建新的纯文本 .txt 文件，不支持删除、覆盖或任意命令。
"""
from __future__ import annotations

import os
import re
import stat
import ntpath
from pathlib import Path

MAX_CONTENT_BYTES = 2048
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}\.txt", re.ASCII)
_WINDOWS_DEVICE = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)


class SandboxError(ValueError):
    """无效路径、内容或不满足沙箱边界。"""


def reject_link_chain(target: Path, *, directory: bool = False) -> None:
    """Shared reparse/link check for real scoped access and the text writer."""
    for candidate in reversed((target, *target.parents)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise SandboxError('路径不能包含符号链接或重解析点')
        if (candidate != target or directory) and not stat.S_ISDIR(info.st_mode):
            raise SandboxError('父路径必须是目录')


def resolve_object_path(value: str, root: str, *, virtual: bool = False) -> str:
    """Resolve a Windows task object, refusing traversal, ADS, devices and sibling roots.

    Virtual mode uses identical lexical rules without touching the host filesystem.
    Real mode additionally rechecks existing parents for symlinks/junctions.
    """
    if not isinstance(value, str) or not value or '\x00' in value or len(value) > 4096:
        raise SandboxError('无效对象路径')
    value = value.replace('/', '\\')
    drive, tail = ntpath.splitdrive(value)
    if not drive or len(drive) != 2 or drive[1] != ':' or not tail.startswith('\\'):
        raise SandboxError('对象必须使用绝对本地磁盘路径')
    for part in tail.split('\\'):
        if not part:
            continue
        if part in ('.', '..') or ':' in part or any(c in part for c in '<>"|?*') or part.endswith((' ', '.')) or _WINDOWS_DEVICE.match(part):
            raise SandboxError('路径穿越、设备名或别名不允许')
    canonical = ntpath.normcase(ntpath.normpath(value))
    boundary = ntpath.normcase(ntpath.normpath(str(root)))
    try:
        inside = ntpath.commonpath([boundary, canonical]) == boundary
    except ValueError:
        inside = False
    if not inside:
        raise SandboxError('对象位于任务根目录之外')
    if not virtual:
        reject_link_chain(Path(boundary), directory=True)
        reject_link_chain(Path(canonical))
    return canonical


def validate_payload(filename: str, content: str) -> bytes:
    """先验证参数，再返回用于写入和计算摘要的精确 UTF-8 字节。"""
    if not isinstance(filename, str) or not _FILENAME.fullmatch(filename):
        raise SandboxError("仅允许工作区根目录内的 ASCII 文件名（例如 notes.txt），不接受路径")
    if filename.endswith((' ', '.')) or _WINDOWS_DEVICE.match(filename):
        raise SandboxError("Windows 保留文件名或末尾空格/句点不允许")
    if not isinstance(content, str) or '\x00' in content:
        raise SandboxError("文本内容必须为字符串，且不能包含 NUL 字符")
    try:
        data = content.encode('utf-8')
    except UnicodeError as exc:
        raise SandboxError('内容必须能编码为 UTF-8') from exc
    if not data or len(data) > MAX_CONTENT_BYTES:
        raise SandboxError(f"内容必须为 1～{MAX_CONTENT_BYTES} 个 UTF-8 字节")
    return data


class SandboxedTextWriter:
    """不接受任意路径：所有目标都是 root / filename 的直接子级。"""

    def __init__(self, root: str | Path):
        self.root = Path(os.path.abspath(root))

    def _check_parents(self) -> None:
        # Windows junction 不是普通符号链接；所有已存在的父目录也必须检查。
        reject_link_chain(self.root, directory=True)

    def _ensure_root(self) -> Path:
        # 拒绝根目录本身为软链接。建议将 root 放在只有当前用户可修改的目录下。
        self._check_parents()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir() or self.root.is_symlink():
            raise SandboxError("工作区根目录不安全")
        self._check_parents()
        return self.root

    def create(self, filename: str, content: str) -> str:
        """原子排他创建，已存在的文件或同名符号链接均不能被覆盖。"""
        data = validate_payload(filename, content)
        root = self._ensure_root()
        target = root / filename
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, 'O_BINARY', 0)
        flags |= getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(target, flags, 0o600)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            # 只在新文件创建后出现写入失败时清理不完整文件。
            try:
                target.unlink()
            except OSError:
                pass
            raise
        return str(target)
