"""Prepare an explicit cache deletion plan before the GUI asks for approval."""
import os
import platform
import shutil
import stat
from pathlib import Path


def _check_directory(path):
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('缓存目录不能经过链接或重解析点')
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('缓存路径不是目录')


def prepare_cache_cleanup():
    system = platform.system()
    root = Path(os.environ.get('TEMP', 'C:/Windows/Temp')) if system == 'Windows' else (
        Path.home() / ('Library/Caches' if system == 'Darwin' else '.cache'))
    root = Path(os.path.abspath(root))
    if root == Path(root.anchor) or root == Path.home() or root == Path.cwd():
        raise ValueError('拒绝把根目录、用户目录或工作目录作为缓存目录')
    _check_directory(root)
    root_identity = (root.stat().st_dev, root.stat().st_ino)
    items = []
    for item in root.iterdir():
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            continue
        items.append((str(item), info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size))
    # Freeze the plan; newly added root entries cannot join an approved operation.
    plan = tuple(items)

    def execute():
        _check_directory(root)
        if (root.stat().st_dev, root.stat().st_ino) != root_identity:
            raise ValueError('缓存目录已改变，请重新申请')
        deleted, skipped = [], []
        for name, device, inode, modified, size in plan:
            item = Path(name)
            try:
                _check_directory(item.parent)
                info = item.lstat()
                if (item.parent != root or item.resolve().parent != root or
                    stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or
                    (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size) != (device, inode, modified, size)):
                    skipped.append(name)
                    continue
                if stat.S_ISDIR(info.st_mode):
                    # Do not recursively traverse any reparse point in an approved directory.
                    for current, directories, files in os.walk(item, followlinks=False):
                        for child in directories + files:
                            child_info = (Path(current) / child).lstat()
                            if stat.S_ISLNK(child_info.st_mode) or getattr(child_info, 'st_file_attributes', 0) & 0x400:
                                raise ValueError('目录包含链接，跳过此项')
                    shutil.rmtree(item)
                else:
                    item.unlink()
                deleted.append(name)
            except (OSError, ValueError):
                skipped.append(name)
        return dict(success=bool(deleted) or not plan,
                    message=f'缓存清理完成：删除 {len(deleted)} 项，跳过 {len(skipped)} 项',
                    deleted=deleted, skipped=skipped)

    return execute, {'cache_root': str(root), 'targets': [item[0] for item in plan]}
