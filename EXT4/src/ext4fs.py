# ext4fs.py
# Python ctypes wrapper for ext4shim.dll (libext2fs shim).
# Works on Windows (MSYS2 MinGW64-built DLL).
from __future__ import annotations

import ctypes as C
import json
import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ---------- Errors ----------

class Ext4Error(RuntimeError):
    pass


# ---------- Helpers ----------

def _b(s: Optional[str]) -> C.c_char_p:
    if s is None:
        return C.c_char_p(b"")
    if isinstance(s, bytes):
        return C.c_char_p(s)
    return C.c_char_p(s.encode("utf-8", errors="strict"))


def _load_dll(explicit_path: Optional[str] = None) -> C.CDLL:
    """
    Load ext4shim.dll. Search order:
    1. explicit_path (if given)
    2. ENV EXT4SHIM_DLL
    3. ./native/ext4shim/bin/ext4shim.dll relative to this file
    4. ./ext4shim.dll (cwd)
    """
    candidates: List[str] = []
    if explicit_path:
        candidates.append(explicit_path)
    envp = os.environ.get("EXT4SHIM_DLL")
    if envp:
        candidates.append(envp)

    here = os.path.abspath(os.path.dirname(__file__))
    candidates.append(os.path.join(here, "..", "native", "ext4shim", "bin", "ext4shim.dll"))
    candidates.append(os.path.join(here, "ext4shim.dll"))
    candidates.append(os.path.join(os.getcwd(), "ext4shim.dll"))

    for p in candidates:
        p = os.path.abspath(p)
        if os.path.exists(p):
            try:
                # WinDLL for stdcall-like semantics; our shim uses C-style exports: WinDLL is fine.
                return C.WinDLL(p)
            except Exception as e:
                last_err = f"Failed to load '{p}': {e}"
                continue
    raise Ext4Error("ext4shim.dll not found. Set EXT4SHIM_DLL or put DLL under native/ext4shim/bin/.")


# ---------- ctypes bindings ----------

def _bind(dll: C.CDLL):
    # int ext4_open(const char* image_path, int rw, void** fs_handle, char* err, int errlen)
    dll.ext4_open.argtypes = [C.c_char_p, C.c_int, C.POINTER(C.c_void_p), C.c_char_p, C.c_int]
    dll.ext4_open.restype = C.c_int

    # int ext4_close(void* fs_handle)
    dll.ext4_close.argtypes = [C.c_void_p]
    dll.ext4_close.restype = C.c_int

    # int ext4_listdir(void* fs_handle, const char* abs_path, char* json_utf8, int buflen, char* err, int errlen)
    dll.ext4_listdir.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_int, C.c_char_p, C.c_int]
    dll.ext4_listdir.restype = C.c_int

    # int ext4_stat(void* fs_handle, const char* abs_path, char* json_utf8, int buflen, char* err, int errlen)
    dll.ext4_stat.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_int, C.c_char_p, C.c_int]
    dll.ext4_stat.restype = C.c_int

    # int ext4_read(void* fs_handle, const char* abs_path, uint8_t* buf, uint64_t bufsize, uint64_t* out_read, char* err, int errlen)
    dll.ext4_read.argtypes = [C.c_void_p, C.c_char_p, C.c_void_p, C.c_uint64, C.POINTER(C.c_uint64), C.c_char_p, C.c_int]
    dll.ext4_read.restype = C.c_int

    # int ext4_write_overwrite(void* fs_handle, const char* abs_path, const uint8_t* data, uint64_t size, uint16_t mode, char* err, int errlen)
    dll.ext4_write_overwrite.argtypes = [C.c_void_p, C.c_char_p, C.c_void_p, C.c_uint64, C.c_uint16, C.c_char_p, C.c_int]
    dll.ext4_write_overwrite.restype = C.c_int

    # int ext4_mkdirs(void* fs_handle, const char* abs_path, uint16_t mode, char* err, int errlen)
    dll.ext4_mkdirs.argtypes = [C.c_void_p, C.c_char_p, C.c_uint16, C.c_char_p, C.c_int]
    dll.ext4_mkdirs.restype = C.c_int

    # int ext4_remove(void* fs_handle, const char* abs_path, char* err, int errlen)
    dll.ext4_remove.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_int]
    dll.ext4_remove.restype = C.c_int

    # int ext4_rename(void* fs_handle, const char* old_abs_path, const char* new_basename, char* err, int errlen)
    dll.ext4_rename.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p, C.c_char_p, C.c_int]
    dll.ext4_rename.restype = C.c_int

    # int ext4_mkfs(const char* target_path, uint64_t image_bytes, uint32_t block_size, const char* label, const char* opt_uuid, char* err, int errlen)
    dll.ext4_mkfs.argtypes = [C.c_char_p, C.c_uint64, C.c_uint32, C.c_char_p, C.c_char_p, C.c_char_p, C.c_int]
    dll.ext4_mkfs.restype = C.c_int

    return dll


# ---------- Data structures ----------

@dataclass
class DirEntry:
    name: str
    inode: int
    is_dir: bool
    size: int
    mode: int


@dataclass
class Stat:
    inode: int
    is_dir: bool
    size: int
    mode: int
    uid: int
    gid: int
    atime: int
    mtime: int
    ctime: int


# ---------- Main class ----------

class Ext4FS:
    """
    Python wrapper for ext4shim.dll
    Usage:
        fs = Ext4FS(dll_path=None)
        fs.open("image.img", rw=True)
        entries = fs.listdir("/")
        ...
        fs.close()
    """
    _ERRLEN = 512

    def __init__(self, dll_path: Optional[str] = None):
        self._dll = _bind(_load_dll(dll_path))
        self._handle = C.c_void_p(0)

    # context manager
    def __enter__(self) -> "Ext4FS":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ----- internal helpers -----
    def _errbuf(self) -> C.c_char_p:
        return C.create_string_buffer(self._ERRLEN)  # type: ignore

    def _raise_if_err(self, rc: int, errbuf: C.c_char_p, default: str):
        if rc != 0:
            msg = (errbuf.value.decode("utf-8", "ignore") if getattr(errbuf, "value", b"") else "") or default
            raise Ext4Error(msg)

    # ----- API -----

    def open(self, image_path: str, rw: bool = True):
        err = self._errbuf()
        h = C.c_void_p()
        rc = self._dll.ext4_open(_b(image_path), 1 if rw else 0, C.byref(h), err, self._ERRLEN)
        self._raise_if_err(rc, err, "open failed")
        self._handle = h

    def close(self):
        if self._handle and self._handle.value:
            try:
                self._dll.ext4_close(self._handle)
            finally:
                self._handle = C.c_void_p(0)

    def listdir(self, abs_path: str = "/") -> List[DirEntry]:
        bufsize = 64 * 1024
        for attempt in range(5):
            json_buf = C.create_string_buffer(bufsize)
            err = self._errbuf()
            rc = self._dll.ext4_listdir(self._handle, _b(abs_path), json_buf, bufsize, err, self._ERRLEN)
            if rc == 0:
                data = json_buf.value.decode("utf-8", "strict")
                try:
                    arr = json.loads(data)
                    return [DirEntry(**x) for x in arr]
                except Exception as e:
                    raise Ext4Error(f"listdir JSON parse failed: {e}\nRaw: {data[:2000]}")
            # retry on buffer errors
            msg = err.value.decode("utf-8", "ignore")
            if "buffer too small" in msg.lower() and bufsize < 8 * 1024 * 1024:
                bufsize *= 2
                continue
            self._raise_if_err(rc, err, "listdir failed")
        raise Ext4Error("listdir failed: ran out of retries")

    def stat(self, abs_path: str = "/") -> Stat:
        bufsize = 2048
        json_buf = C.create_string_buffer(bufsize)
        err = self._errbuf()
        rc = self._dll.ext4_stat(self._handle, _b(abs_path), json_buf, bufsize, err, self._ERRLEN)
        self._raise_if_err(rc, err, "stat failed")
        data = json_buf.value.decode("utf-8", "strict")
        try:
            obj = json.loads(data)
            return Stat(**obj)
        except Exception as e:
            raise Ext4Error(f"stat JSON parse failed: {e}\nRaw: {data[:2000]}")

    def read(self, abs_path: str, size_hint: Optional[int] = None) -> bytes:
        # If no size_hint provided, fetch file size via stat.
        if size_hint is None:
            st = self.stat(abs_path)
            if st.is_dir:
                raise Ext4Error("Cannot read a directory")
            size_hint = max(int(st.size), 0)

        buf = (C.c_uint8 * int(size_hint))()
        out_read = C.c_uint64(0)
        err = self._errbuf()
        rc = self._dll.ext4_read(self._handle, _b(abs_path), C.cast(buf, C.c_void_p),
                                 C.c_uint64(size_hint), C.byref(out_read), err, self._ERRLEN)
        self._raise_if_err(rc, err, "read failed")
        return bytes(buf[: int(out_read.value)])

    def write_overwrite(self, abs_path: str, data: bytes, mode: int = 0o644):
        if isinstance(data, memoryview):
            data = data.tobytes()
        err = self._errbuf()
        # c_uint16 keeps only permission bits; type bits set by shim
        rc = self._dll.ext4_write_overwrite(self._handle, _b(abs_path),
                                            _b(data), C.c_uint64(len(data)),
                                            C.c_uint16(mode & 0o777),
                                            err, self._ERRLEN)
        self._raise_if_err(rc, err, "write_overwrite failed")

    def mkdirs(self, abs_path: str, mode: int = 0o755):
        err = self._errbuf()
        rc = self._dll.ext4_mkdirs(self._handle, _b(abs_path), C.c_uint16(mode & 0o777), err, self._ERRLEN)
        self._raise_if_err(rc, err, "mkdirs failed")

    def remove(self, abs_path: str):
        err = self._errbuf()
        rc = self._dll.ext4_remove(self._handle, _b(abs_path), err, self._ERRLEN)
        self._raise_if_err(rc, err, "remove failed")

    def rename(self, old_abs_path: str, new_basename: str):
        err = self._errbuf()
        rc = self._dll.ext4_rename(self._handle, _b(old_abs_path), _b(new_basename), err, self._ERRLEN)
        self._raise_if_err(rc, err, "rename failed")

    # ----- class/staticmethods -----

    @classmethod
    def mkfs(cls, target_path: str, size_bytes: int, block_size: int = 4096,
             label: str = "", uuid: Optional[str] = None, dll_path: Optional[str] = None):
        """
        Create a new ext4 image file.
        """
        dll = _bind(_load_dll(dll_path))
        errlen = 512
        err = C.create_string_buffer(errlen)
        rc = dll.ext4_mkfs(_b(target_path), C.c_uint64(size_bytes), C.c_uint32(block_size),
                           _b(label), _b(uuid or ""), err, errlen)
        if rc != 0:
            msg = err.value.decode("utf-8", "ignore") or "mkfs failed"
            raise Ext4Error(msg)


# ---------- Quick self-test (optional) ----------

if __name__ == "__main__":
    # Simple smoke test: mkfs -> open -> mkdir -> write -> read -> rename -> remove
    img = os.path.abspath("test_ext4.img")
    if os.path.exists(img):
        os.remove(img)
    print("[*] mkfs …")
    Ext4FS.mkfs(img, 64 * 1024 * 1024, block_size=4096, label="PYEXT4")

    with Ext4FS() as fs:
        print("[*] open rw …")
        fs.open(img, rw=True)
        print("[*] mkdirs /demo …")
        fs.mkdirs("/demo", 0o755)
        print("[*] write /demo/hello.txt …")
        fs.write_overwrite("/demo/hello.txt", b"Hello, ext4!", 0o644)
        print("[*] stat /demo/hello.txt …")
        st = fs.stat("/demo/hello.txt")
        print("    size:", st.size, "inode:", st.inode)
        print("[*] read …")
        data = fs.read("/demo/hello.txt")
        print("    data:", data)
        print("[*] rename → hello2.txt …")
        fs.rename("/demo/hello.txt", "hello2.txt")
        print("[*] listdir /demo …")
        for e in fs.listdir("/demo"):
            print("   ", e)
        print("[*] remove /demo/hello2.txt …")
        fs.remove("/demo/hello2.txt")
        print("[*] OK")
