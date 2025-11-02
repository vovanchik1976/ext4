
#define SHIM_API __declspec(dllexport)


SHIM_API int ext4_open(const char* image_path, int rw, void** fs_handle, char* err, int errlen) {
    // ... implementation ...
}

// ... other functions with SHIM_API ...