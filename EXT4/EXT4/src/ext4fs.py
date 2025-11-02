
self._dll.ext4_open.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_int]
self._dll.ext4_open.restype = ctypes.c_int

self._dll.ext4_close.argtypes = [ctypes.c_void_p]
self._dll.ext4_close.restype = ctypes.c_int

self._dll.ext4_listdir.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
self._dll.ext4_listdir.restype = ctypes.c_int

# ... other function signatures ...