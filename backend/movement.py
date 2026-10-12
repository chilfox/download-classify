"""macOS atomic no-replace movement, anchored to verified directory descriptors.

No portable rename fallback: os.rename can overwrite a late collision. Filesystem
stability is a heuristic; this is not protection against a hostile local process
mutating open files or relocating directories concurrently with the syscall.
"""
import ctypes
import errno
import os
import stat
import sys
from pathlib import Path


def signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class SourceChanged(OSError):
    pass


def open_directory(path):
    # Walk from / with O_NOFOLLOW, including every ancestor, not just the leaf.
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in Path(path).parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def move_document(root, root_identity, name, expected, topic):
    if topic in {"", ".", ".."} or any(char in topic for char in "/\\:"):
        raise ValueError("Unsafe destination folder")
    if sys.platform != "darwin":
        raise OSError("Automatic movement requires macOS exclusive rename; use suggestions-only mode")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameatx_np
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    root_fd = open_directory(root)
    try:
        info = os.fstat(root_fd)
        if (info.st_dev, info.st_ino) != root_identity:
            raise OSError("Monitored folder identity changed")
        source = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        if not stat.S_ISREG(source.st_mode) or signature(source) != expected:
            raise SourceChanged("Source changed before movement")
        try:
            os.mkdir(topic, dir_fd=root_fd)
        except FileExistsError:
            pass
        destination_fd = os.open(topic, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        try:
            for counter in range(10000):
                source = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if not stat.S_ISREG(source.st_mode) or signature(source) != expected:
                    raise SourceChanged("Source changed before movement")
                # Revalidate root and destination path bindings, while the syscall
                # itself uses descriptors so a symlink swap cannot redirect it.
                root_info = os.stat(root, follow_symlinks=False)
                folder_info = os.stat(topic, dir_fd=root_fd, follow_symlinks=False)
                opened = os.fstat(destination_fd)
                if (root_info.st_dev, root_info.st_ino) != root_identity or not stat.S_ISDIR(folder_info.st_mode) or (folder_info.st_dev, folder_info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise OSError("Unsafe destination: directory binding changed")
                original = Path(name)
                candidate = name if counter == 0 else f"{original.stem} ({counter}){original.suffix}"
                # RENAME_EXCL = 0x4. Atomic EEXIST for any existing entry,
                # including symlinks. Never use an availability check here.
                if rename(root_fd, os.fsencode(name), destination_fd, os.fsencode(candidate), 0x4) == 0:
                    return root / topic / candidate
                error = ctypes.get_errno()
                if error != errno.EEXIST:
                    raise OSError(error, os.strerror(error))
            raise OSError("Too many destination filename collisions")
        finally:
            os.close(destination_fd)
    finally:
        os.close(root_fd)
