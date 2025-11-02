#ifndef EXT4SHIM_H
#define EXT4SHIM_H

#ifdef __cplusplus
extern "C" {
#endif

// Function declarations
int ext4_open(const char* image_path, int read_write);
int ext4_close();
char* ext4_listdir(const char* path);
char* ext4_stat(const char* path);
int ext4_read(const char* path, char* buffer, unsigned int size);
int ext4_write_overwrite(const char* path, const char* data, unsigned int size, int mode);
int ext4_mkdirs(const char* path, int mode);
int ext4_remove(const char* path);
int ext4_rename(const char* old_path, const char* new_name);
int ext4_mkfs(const char* target, unsigned long long size_bytes, int block_size, 
              const char* label, const char* uuid);

#ifdef __cplusplus
}
#endif

#endif // EXT4SHIM_H