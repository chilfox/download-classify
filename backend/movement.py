"""macOS/Linux atomic no-replace movement, anchored to verified directory descriptors.

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
    if sys.platform not in {"darwin", "linux"}:
        raise OSError("Automatic movement requires macOS or Linux safe rename; use suggestions-only mode")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renameatx_np if sys.platform == "darwin" else libc.renameat2
    except (AttributeError, OSError) as exc:
        raise OSError("Required safe rename is unavailable in the runtime library; "
                      "install a compatible runtime or use suggestions-only mode") from exc
    flags = 0x4 if sys.platform == "darwin" else 0x1  # RENAME_EXCL / RENAME_NOREPLACE
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
                candidate = name
                if counter:
                    suffix = f" ({counter}){original.suffix}"
                    stem = original.stem
                    name_max = os.fpathconf(destination_fd, "PC_NAME_MAX")
                    # Reserve space for the collision number and extension, and
                    # trim whole characters rather than splitting UTF-8 bytes.
                    while name_max > 0 and len(os.fsencode(stem + suffix)) > name_max and stem:
                        stem = stem[:-1]
                    candidate = stem + suffix
                # Atomic EEXIST for any existing entry, including symlinks.
                # Never use an availability check or overwrite-capable fallback.
                if rename(root_fd, os.fsencode(name), destination_fd, os.fsencode(candidate), flags) == 0:
                    return root / topic / candidate
                error = ctypes.get_errno()
                if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.ENOTSUP}:
                    raise OSError(error, "Required safe rename is unsupported by the kernel or filesystem; "
                                  "use a compatible filesystem/runtime or suggestions-only mode")
                if error != errno.EEXIST:
                    raise OSError(error, os.strerror(error))
            raise OSError("Too many destination filename collisions")
        finally:
            os.close(destination_fd)
    finally:
        os.close(root_fd)
