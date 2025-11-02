// ext4shim.c
// Windows shim over libext2fs for Python (ctypes).
// Build example (MinGW64):
//   gcc -O2 -D_WIN32_WINNT=0x0601 ^
//     -I"C:\dev\e2fs-mingw64\include" -L"C:\dev\e2fs-mingw64\lib" ^
//     -shared -o ext4shim.dll ext4shim.c ^
//     -lext2fs -le2p -lcom_err -lz
//
// Exports are declared via __declspec(dllexport). You may also provide a .def file.

#define _CRT_SECURE_NO_WARNINGS
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#  include <io.h>
#  include <fcntl.h>
#  include <sys/types.h>
#  include <sys/stat.h>
#  define lseek64  _lseeki64
#  define ftruncate64 _chsize_s
#endif

#include <errno.h>

#include <ext2fs/ext2fs.h>
#include <ext2fs/ext2_io.h>

// ------------------------ Common ------------------------

#define SHIM_API __declspec(dllexport)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MINU64(a,b) ((uint64_t)((a)<(b)?(a):(b)))

typedef struct {
    ext2_filsys fs;
} shim_fs_t;

static void set_err(char* err, int errlen, const char* msg) {
    if (!err || errlen <= 0) return;
    if (!msg) { err[0] = 0; return; }
#ifdef _MSC_VER
    _snprintf(err, (size_t)errlen, "%s", msg);
#else
    snprintf(err, (size_t)errlen, "%s", msg);
#endif
}

static void set_err_rc(char* err, int errlen, const char* prefix, errcode_t rc) {
    if (!err || errlen <= 0) return;
    const char* em = error_message(rc);
    if (!prefix) prefix = "";
#ifdef _MSC_VER
    _snprintf(err, (size_t)errlen, "%s%s%s", prefix, (prefix[0]?": ":""), (em?em:""));
#else
    snprintf(err, (size_t)errlen, "%s%s%s", prefix, (prefix[0]?": ":""), (em?em:""));
#endif
}

static int json_escape_name(const char* s, char* out, int outcap) {
    int p = 0;
    if (outcap < 3) return -1;
    out[p++] = '"';
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        const char* esc = NULL;
        char buf[8];
        switch (c) {
            case '\\': esc = "\\\\"; break;
            case '"':  esc = "\\\""; break;
            case '\b': esc = "\\b";  break;
            case '\f': esc = "\\f";  break;
            case '\n': esc = "\\n";  break;
            case '\r': esc = "\\r";  break;
            case '\t': esc = "\\t";  break;
            default: esc = NULL; break;
        }
        if (esc) {
            int n = (int)strlen(esc);
            if (p + n >= outcap) return -1;
            memcpy(out + p, esc, (size_t)n);
            p += n;
        } else if (c < 0x20) {
            if (p + 6 >= outcap) return -1;
#ifdef _MSC_VER
            _snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
#else
            snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
#endif
            memcpy(out + p, buf, 6);
            p += 6;
        } else {
            if (p + 1 >= outcap) return -1;
            out[p++] = (char)c;
        }
    }
    if (p + 2 > outcap) return -1;
    out[p++] = '"';
    out[p] = 0;
    return 0;
}

static int path_to_ino(ext2_filsys fs, const char* abs_path, ext2_ino_t* out_ino, char* err, int errlen) {
    if (!abs_path || abs_path[0] == 0 || (abs_path[0] == '/' && abs_path[1] == 0)) {
        *out_ino = EXT2_ROOT_INO;
        return 0;
    }
    if (abs_path[0] != '/') {
        set_err(err, errlen, "Path must be absolute (e.g. /dir/file)");
        return -1;
    }
    ext2_ino_t ino = 0;
    errcode_t rc = ext2fs_namei(fs, EXT2_ROOT_INO, EXT2_ROOT_INO, abs_path, &ino);
    if (rc) { set_err_rc(err, errlen, "namei failed", rc); return -1; }
    *out_ino = ino;
    return 0;
}

static int lookup_parent_and_base(const char* abs_path, char* parent, int parent_cap, char* base, int base_cap, char* err, int errlen) {
    if (!abs_path || abs_path[0] != '/') { set_err(err, errlen, "Path must be absolute"); return -1; }
    const char* last = strrchr(abs_path, '/');
    if (!last) { set_err(err, errlen, "Invalid absolute path"); return -1; }
    if (last == abs_path) {
        // parent = "/", base = tail
#ifdef _MSC_VER
        _snprintf(parent, parent_cap, "/");
        _snprintf(base,   base_cap,   "%s", abs_path+1);
#else
        snprintf(parent, parent_cap, "/");
        snprintf(base,   base_cap,   "%s", abs_path+1);
#endif
        if (base[0] == 0) { set_err(err, errlen, "Empty basename"); return -1; }
        return 0;
    }
    int plen = (int)(last - abs_path);
    if (plen <= 0 || plen >= parent_cap) { set_err(err, errlen, "Parent path too long"); return -1; }
    memcpy(parent, abs_path, (size_t)plen); parent[plen] = 0;
#ifdef _MSC_VER
    _snprintf(base, base_cap, "%s", last+1);
#else
    snprintf(base, base_cap, "%s", last+1);
#endif
    if (base[0] == 0) { set_err(err, errlen, "Empty basename"); return -1; }
    return 0;
}

static int ensure_dir(ext2_filsys fs, ext2_ino_t parent, const char* name, uint16_t mode, ext2_ino_t* out_dir, char* err, int errlen) {
    // Does entry exist?
    ext2_ino_t child = 0;
    errcode_t rc = ext2fs_lookup(fs, parent, name, (int)strlen(name), NULL, &child);
    if (rc == 0 && child != 0) {
        struct ext2_inode in; memset(&in, 0, sizeof(in));
        rc = ext2fs_read_inode(fs, child, &in);
        if (rc) { set_err_rc(err, errlen, "read_inode failed", rc); return -1; }
        if (!LINUX_S_ISDIR(in.i_mode)) { set_err(err, errlen, "Path segment exists and is not a directory"); return -1; }
        *out_dir = child;
        return 0;
    }
    // Create dir using ext2fs_mkdir
    rc = ext2fs_mkdir(fs, parent, 0, name);
    if (rc) { set_err_rc(err, errlen, "mkdir failed", rc); return -1; }
    // Lookup again
    child = 0;
    rc = ext2fs_lookup(fs, parent, name, (int)strlen(name), NULL, &child);
    if (rc || child == 0) { set_err(err, errlen, "mkdir succeeded but lookup failed"); return -1; }
    // Set mode (keep type bits)
    struct ext2_inode in2; memset(&in2, 0, sizeof(in2));
    rc = ext2fs_read_inode(fs, child, &in2);
    if (rc) { set_err_rc(err, errlen, "read_inode failed", rc); return -1; }
    in2.i_mode = (in2.i_mode & ~07777) | (mode & 07777);
    rc = ext2fs_write_inode(fs, child, &in2);
    if (rc) { set_err_rc(err, errlen, "write_inode failed", rc); return -1; }
    *out_dir = child;
    return 0;
}

static int mkdirs_abs(ext2_filsys fs, const char* abs_path, uint16_t mode, char* err, int errlen) {
    if (!abs_path || abs_path[0] != '/') { set_err(err, errlen, "Path must be absolute"); return -1; }
    if (strcmp(abs_path, "/") == 0) return 0;
    ext2_ino_t cur = EXT2_ROOT_INO;
    const char* p = abs_path + 1;
    char seg[256];
    while (*p) {
        int i = 0;
        while (*p && *p != '/' && i < (int)sizeof(seg)-1) seg[i++] = *p++;
        seg[i] = 0;
        if (i == 0) { if (*p == '/') { ++p; continue; } else break; }
        ext2_ino_t next = 0;
        if (ensure_dir(fs, cur, seg, mode, &next, err, errlen)) return -1;
        cur = next;
        if (*p == '/') ++p;
    }
    return 0;
}

// ------------------------ Open / Close ------------------------

SHIM_API int ext4_open(const char* image_path, int rw, void** fs_handle, char* err, int errlen) {
    if (!image_path || !fs_handle) { set_err(err, errlen, "bad args"); return -1; }
    *fs_handle = NULL;

    io_manager io = windows_io_manager;

    ext2_filsys fs = NULL;
    errcode_t rc = ext2fs_open(
        image_path,
        (rw ? (EXT2_FLAG_RW | EXT2_FLAG_64BITS) : EXT2_FLAG_64BITS),
        0, 0, io, &fs
    );
    if (rc) { set_err_rc(err, errlen, "ext2fs_open failed", rc); return -1; }

    rc = ext2fs_read_inode_bitmap(fs);
    if (rc) { set_err_rc(err, errlen, "read_inode_bitmap failed", rc); ext2fs_close(fs); return -1; }
    rc = ext2fs_read_block_bitmap(fs);
    if (rc) { set_err_rc(err, errlen, "read_block_bitmap failed", rc); ext2fs_close(fs); return -1; }

    shim_fs_t* h = (shim_fs_t*)calloc(1, sizeof(shim_fs_t));
    if (!h) { ext2fs_close(fs); set_err(err, errlen, "oom"); return -1; }
    h->fs = fs;
    *fs_handle = h;
    set_err(err, errlen, NULL);
    return 0;
}

SHIM_API int ext4_close(void* fs_handle) {
    if (!fs_handle) return 0;
    shim_fs_t* h = (shim_fs_t*)fs_handle;
    if (h->fs) {
        ext2fs_mark_super_dirty(h->fs);
        ext2fs_flush(h->fs);
        ext2fs_close(h->fs);
    }
    free(h);
    return 0;
}

// ------------------------ listdir / stat ------------------------

typedef struct {
    ext2_filsys fs;
    char* out;
    int cap;
    int pos;
    int first;
} list_ctx_t;

static int append_json(char* out, int cap, int* pos, const char* s) {
    int n = (int)strlen(s);
    if (*pos + n + 1 > cap) return -1;
    memcpy(out + *pos, s, (size_t)n);
    *pos += n;
    out[*pos] = 0;
    return 0;
}

static int dir_cb(ext2_ino_t dir, int entry, struct ext2_dir_entry *de, int offset, int blocksize, char *buf, void *priv) {
    (void)dir; (void)entry; (void)offset; (void)blocksize; (void)buf;
    list_ctx_t* ctx = (list_ctx_t*)priv;
    if (!de || de->inode == 0 || de->name_len == 0) return 0;

    // get inode for size/mode/dir type
    struct ext2_inode in; memset(&in, 0, sizeof(in));
    if (ext2fs_read_inode(ctx->fs, de->inode, &in)) return 0;

    char name[260]; memset(name, 0, sizeof(name));
    memcpy(name, de->name, de->name_len);

    char esc[600];
    if (json_escape_name(name, esc, sizeof(esc))) return -1;

    char one[1024];
    snprintf(one, sizeof(one),
        "%s{\"name\":%s,\"inode\":%u,\"is_dir\":%s,\"size\":%llu,\"mode\":%u}",
        (ctx->first ? "" : ","),
        esc,
        (unsigned)de->inode,
        (LINUX_S_ISDIR(in.i_mode) ? "true" : "false"),
        (unsigned long long)in.i_size,
        (unsigned)in.i_mode
    );
    if (append_json(ctx->out, ctx->cap, &ctx->pos, one)) return -1;
    ctx->first = 0;
    return 0;
}

SHIM_API int ext4_listdir(void* fs_handle, const char* abs_path, char* json_utf8, int buflen, char* err, int errlen) {
    if (!fs_handle || !json_utf8 || buflen <= 2) { set_err(err, errlen, "bad args"); return -1; }
    json_utf8[0] = 0;

    shim_fs_t* h = (shim_fs_t*)fs_handle;
    ext2_ino_t ino = 0;
    if (path_to_ino(h->fs, (abs_path && abs_path[0]) ? abs_path : "/", &ino, err, errlen)) return -1;

    struct ext2_inode in; memset(&in, 0, sizeof(in));
    if (ext2fs_read_inode(h->fs, ino, &in)) { set_err(err, errlen, "read_inode failed"); return -1; }
    if (!LINUX_S_ISDIR(in.i_mode)) { set_err(err, errlen, "Not a directory"); return -1; }

    list_ctx_t ctx; memset(&ctx, 0, sizeof(ctx));
    ctx.fs = h->fs; ctx.out = json_utf8; ctx.cap = buflen; ctx.pos = 0; ctx.first = 1;

    if (append_json(json_utf8, buflen, &ctx.pos, "[")) { set_err(err, errlen, "buffer too small"); return -1; }
    errcode_t rc = ext2fs_dir_iterate2(h->fs, ino, 0, NULL, dir_cb, &ctx);
    if (rc) { set_err_rc(err, errlen, "dir_iterate failed", rc); return -1; }
    if (append_json(json_utf8, buflen, &ctx.pos, "]")) { set_err(err, errlen, "buffer too small"); return -1; }

    set_err(err, errlen, NULL);
    return 0;
}

SHIM_API int ext4_stat(void* fs_handle, const char* abs_path, char* json_utf8, int buflen, char* err, int errlen) {
    if (!fs_handle || !json_utf8 || buflen < 16) { set_err(err, errlen, "bad args"); return -1; }
    json_utf8[0] = 0;

    shim_fs_t* h = (shim_fs_t*)fs_handle;
    ext2_ino_t ino = 0;
    if (path_to_ino(h->fs, (abs_path && abs_path[0]) ? abs_path : "/", &ino, err, errlen)) return -1;

    struct ext2_inode in; memset(&in, 0, sizeof(in));
    if (ext2fs_read_inode(h->fs, ino, &in)) { set_err(err, errlen, "read_inode failed"); return -1; }

#ifdef _MSC_VER
    _snprintf(json_utf8, buflen,
#else
    snprintf(json_utf8, buflen,
#endif
        "{\"inode\":%u,\"is_dir\":%s,\"size\":%llu,\"mode\":%u,"
        "\"uid\":%u,\"gid\":%u,\"atime\":%u,\"mtime\":%u,\"ctime\":%u}",
        (unsigned)ino,
        (LINUX_S_ISDIR(in.i_mode) ? "true" : "false"),
        (unsigned long long)in.i_size,
        (unsigned)in.i_mode,
        (unsigned)(in.i_uid | (in.osd2.linux2.l_i_uid_high << 16)),
        (unsigned)(in.i_gid | (in.osd2.linux2.l_i_gid_high << 16)),
        (unsigned)in.i_atime, (unsigned)in.i_mtime, (unsigned)in.i_ctime
    );
    set_err(err, errlen, NULL);
    return 0;
}

// ------------------------ read / write_overwrite ------------------------

SHIM_API int ext4_read(void* fs_handle, const char* abs_path, uint8_t* out_buf, uint64_t bufsize, uint64_t* out_read, char* err, int errlen) {
    if (!fs_handle || !abs_path || !out_buf || !out_read) { set_err(err, errlen, "bad args"); return -1; }
    *out_read = 0;

    shim_fs_t* h = (shim_fs_t*)fs_handle;
    ext2_ino_t ino = 0;
    if (path_to_ino(h->fs, abs_path, &ino, err, errlen)) return -1;

    struct ext2_inode in; memset(&in, 0, sizeof(in));
    if (ext2fs_read_inode(h->fs, ino, &in)) { set_err(err, errlen, "read_inode failed"); return -1; }
    if (LINUX_S_ISDIR(in.i_mode)) { set_err(err, errlen, "Is a directory"); return -1; }

    ext2_file_t f = NULL;
    errcode_t rc = ext2fs_file_open2(h->fs, ino, &in, 0, &f);
    if (rc) { set_err_rc(err, errlen, "file_open failed", rc); return -1; }

    uint64_t size = in.i_size;
    uint64_t toread = (bufsize < size) ? bufsize : size;
    uint64_t done = 0;

    while (done < toread) {
        unsigned int chunk = (unsigned int)MIN(64*1024ULL, toread - done);
        unsigned int got = 0;
        rc = ext2fs_file_read(f, out_buf + done, chunk, &got);
        if (rc) { ext2fs_file_close(f); set_err_rc(err, errlen, "file_read failed", rc); return -1; }
        if (got == 0) break;
        done += got;
    }
    ext2fs_file_close(f);
    *out_read = done;
    set_err(err, errlen, NULL);
    return 0;
}

static int create_or_truncate_file(ext2_filsys fs, const char* abs_path, uint16_t mode, ext2_ino_t* out_ino, char* err, int errlen) {
    char parent[512], base[256];
    if (lookup_parent_and_base(abs_path, parent, sizeof(parent), base, sizeof(base), err, errlen)) return -1;

    ext2_ino_t pino = 0;
    if (path_to_ino(fs, parent, &pino, err, errlen)) return -1;

    // existing?
    ext2_ino_t existing = 0;
    errcode_t rc = ext2fs_lookup(fs, pino, base, (int)strlen(base), NULL, &existing);
    if (rc == 0 && existing != 0) {
        struct ext2_inode in; memset(&in, 0, sizeof(in));
        if (ext2fs_read_inode(fs, existing, &in)) { set_err(err, errlen, "read_inode failed"); return -1; }
        if (LINUX_S_ISDIR(in.i_mode)) { set_err(err, errlen, "Target exists and is a directory"); return -1; }
        // truncate to zero by open+set_size
        ext2_file_t f = NULL;
        rc = ext2fs_file_open2(fs, existing, &in, 0, &f);
        if (rc) { set_err_rc(err, errlen, "file_open(write) failed", rc); return -1; }
        rc = ext2fs_file_set_size2(f, 0);
        ext2fs_file_close(f);
        if (rc) { set_err_rc(err, errlen, "set_size(0) failed", rc); return -1; }
        *out_ino = existing;
        return 0;
    }

    // new file
    ext2_ino_t ino = 0;
    rc = ext2fs_new_inode(fs, pino, LINUX_S_IFREG, 0, &ino);
    if (rc) { set_err_rc(err, errlen, "new_inode failed", rc); return -1; }

    struct ext2_inode in; memset(&in, 0, sizeof(in));
    in.i_mode = LINUX_S_IFREG | (mode & 0777);
    if (ext2fs_write_inode(fs, ino, &in)) { set_err(err, errlen, "write_inode failed"); return -1; }

    rc = ext2fs_link(fs, pino, base, ino, EXT2_FT_REG_FILE);
    if (rc) { set_err_rc(err, errlen, "link failed", rc); return -1; }

    *out_ino = ino;
    return 0;
}

SHIM_API int ext4_write_overwrite(void* fs_handle, const char* abs_path, const uint8_t* data, uint64_t size, uint16_t mode, char* err, int errlen) {
    if (!fs_handle || !abs_path || !data) { set_err(err, errlen, "bad args"); return -1; }
    shim_fs_t* h = (shim_fs_t*)fs_handle;

    // ensure parent dirs exist
    {
        char parent[512], base[256];
        if (lookup_parent_and_base(abs_path, parent, sizeof(parent), base, sizeof(base), err, errlen)) return -1;
        if (mkdirs_abs(h->fs, parent, 0755, err, errlen)) return -1;
    }

    ext2_ino_t ino = 0;
    if (create_or_truncate_file(h->fs, abs_path, mode, &ino, err, errlen)) return -1;

    struct ext2_inode in; memset(&in, 0, sizeof(in));
    if (ext2fs_read_inode(h->fs, ino, &in)) { set_err(err, errlen, "read_inode failed"); return -1; }

    ext2_file_t f = NULL;
    errcode_t rc = ext2fs_file_open2(h->fs, ino, &in, 0, &f);
    if (rc) { set_err_rc(err, errlen, "file_open(write) failed", rc); return -1; }

    uint64_t done = 0;
    while (done < size) {
        unsigned int chunk = (unsigned int)MIN(64*1024ULL, size - done);
        unsigned int wrote = 0;
        rc = ext2fs_file_write(f, (void*)(data + done), chunk, &wrote);
        if (rc) { ext2fs_file_close(f); set_err_rc(err, errlen, "file_write failed", rc); return -1; }
        if (wrote == 0) break;
        done += wrote;
    }
    rc = ext2fs_file_set_size2(f, size);
    ext2fs_file_close(f);
    if (rc) { set_err_rc(err, errlen, "set_size(final) failed", rc); return -1; }

    ext2fs_mark_super_dirty(h->fs);
    ext2fs_flush(h->fs);
    set_err(err, errlen, NULL);
    return 0;
}

// ------------------------ mkdirs / remove / rename ------------------------

SHIM_API int ext4_mkdirs(void* fs_handle, const char* abs_path, uint16_t mode, char* err, int errlen) {
    if (!fs_handle || !abs_path) { set_err(err, errlen, "bad args"); return -1; }
    shim_fs_t* h = (shim_fs_t*)fs_handle;
    if (mkdirs_abs(h->fs, abs_path, mode, err, errlen)) return -1;
    ext2fs_mark_super_dirty(h->fs);
    ext2fs_flush(h->fs);
    set_err(err, errlen, NULL);
    return 0;
}

SHIM_API int ext4_remove(void* fs_handle, const char* abs_path, char* err, int errlen) {
    if (!fs_handle || !abs_path) { set_err(err, errlen, "bad args"); return -1; }
    shim_fs_t* h = (shim_fs_t*)fs_handle;

    char parent[512], base[256];
    if (lookup_parent_and_base(abs_path, parent, sizeof(parent), base, sizeof(base), err, errlen)) return -1;

    ext2_ino_t pino = 0;
    if (path_to_ino(h->fs, parent, &pino, err, errlen)) return -1;

    ext2_ino_t child = 0;
    errcode_t rc = ext2fs_lookup(h->fs, pino, base, (int)strlen(base), NULL, &child);
    if (rc || child == 0) { set_err(err, errlen, "Not found"); return -1; }

    rc = ext2fs_unlink(h->fs, pino, base, child, 0);
    if (rc) { set_err_rc(err, errlen, "unlink failed", rc); return -1; }

    ext2fs_mark_super_dirty(h->fs);
    ext2fs_flush(h->fs);
    set_err(err, errlen, NULL);
    return 0;
}

SHIM_API int ext4_rename(void* fs_handle, const char* old_abs_path, const char* new_basename, char* err, int errlen) {
    if (!fs_handle || !old_abs_path || !new_basename || new_basename[0]==0) { set_err(err, errlen, "bad args"); return -1; }
    shim_fs_t* h = (shim_fs_t*)fs_handle;

    char parent[512], base[256];
    if (lookup_parent_and_base(old_abs_path, parent, sizeof(parent), base, sizeof(base), err, errlen)) return -1;

    ext2_ino_t pino = 0;
    if (path_to_ino(h->fs, parent, &pino, err, errlen)) return -1;

    ext2_ino_t child = 0;
    errcode_t rc = ext2fs_lookup(h->fs, pino, base, (int)strlen(base), NULL, &child);
    if (rc || child == 0) { set_err(err, errlen, "Not found"); return -1; }

    // new name must not exist
    ext2_ino_t exists = 0;
    rc = ext2fs_lookup(h->fs, pino, new_basename, (int)strlen(new_basename), NULL, &exists);
    if (rc == 0 && exists != 0) { set_err(err, errlen, "Target name already exists"); return -1; }

    rc = ext2fs_link(h->fs, pino, new_basename, child, 0);
    if (rc) { set_err_rc(err, errlen, "link(new) failed", rc); return -1; }

    rc = ext2fs_unlink(h->fs, pino, base, child, 0);
    if (rc) { set_err_rc(err, errlen, "unlink(old) failed", rc); return -1; }

    ext2fs_mark_super_dirty(h->fs);
    ext2fs_flush(h->fs);
    set_err(err, errlen, NULL);
    return 0;
}

// ------------------------ mkfs (with feature fallback) ------------------------

static int create_sparse_file(const char* path, uint64_t bytes, char* err, int errlen) {
#ifdef _WIN32
    FILE* f = fopen(path, "wb");
    if (!f) { set_err(err, errlen, "Cannot create image file"); return -1; }
    int fd = _fileno(f);
    if (ftruncate64(fd, (long long)bytes) != 0) {
        fclose(f);
        set_err(err, errlen, "Resize failed");
        return -1;
    }
    fclose(f);
#else
    FILE* f = fopen(path, "wb");
    if (!f) { set_err(err, errlen, "Cannot create image file"); return -1; }
    int fd = fileno(f);
    if (ftruncate(fd, (off_t)bytes) != 0) {
        fclose(f);
        set_err(err, errlen, "Resize failed");
        return -1;
    }
    fclose(f);
#endif
    return 0;
}

static void fill_sb_basic(struct ext2_super_block* s,
                          uint64_t image_bytes,
                          uint32_t block_size,
                          int enable_64bit,
                          int enable_csum,
                          const char* label)
{
    memset(s, 0, sizeof(*s));
    s->s_rev_level = EXT2_DYNAMIC_REV;
    s->s_feature_incompat = EXT2_FEATURE_INCOMPAT_FILETYPE |
                            (enable_64bit ? EXT4_FEATURE_INCOMPAT_64BIT : 0);
    s->s_feature_compat   = EXT2_FEATURE_COMPAT_DIR_PREALLOC;
    s->s_feature_ro_compat = EXT2_FEATURE_RO_COMPAT_SPARSE_SUPER |
                             (enable_csum ? EXT4_FEATURE_RO_COMPAT_METADATA_CSUM : 0);

    s->s_log_block_size = (block_size == 1024 ? 0 : (block_size == 2048 ? 1 : 2));

    // layout
    uint64_t blocks_total = image_bytes / block_size;
    uint32_t blocks_per_group = block_size * 8;                 // classic choice 
    if (blocks_per_group == 0) blocks_per_group = 32768;

    uint32_t group_count = (uint32_t)((blocks_total + blocks_per_group - 1) / blocks_per_group);
    uint32_t inodes_per_group = 8192;
    if (inodes_per_group * group_count * sizeof(struct ext2_inode) > blocks_per_group * block_size) {
        inodes_per_group = (uint32_t)((blocks_per_group * block_size) / sizeof(struct ext2_inode));
    }

    s->s_blocks_count = (uint32_t)(blocks_total & 0xFFFFFFFFu);
    s->s_inodes_count = inodes_per_group * group_count;
    s->s_r_blocks_count = 0;
    s->s_free_blocks_count = (uint32_t)(blocks_total & 0xFFFFFFFFu) - 1;
    s->s_free_inodes_count = s->s_inodes_count - 11;
    s->s_first_data_block = (block_size == 1024) ? 1 : 0;
    s->s_blocks_per_group = blocks_per_group;
    s->s_inodes_per_group = inodes_per_group;
    s->s_wtime = (uint32_t)time(NULL);
    s->s_mtime = s->s_wtime;
    s->s_magic = EXT2_SUPER_MAGIC;
    s->s_state = EXT2_VALID_FS;
    s->s_errors = EXT2_ERRORS_DEFAULT;
    s->s_minor_rev_level = 0;
    s->s_lastcheck = s->s_wtime;
    s->s_checkinterval = 0;
    s->s_creator_os = EXT2_OS_LINUX; // Reverted to EXT2_OS_LINUX
    s->s_def_resuid = EXT2_DEF_RESUID;
    s->s_def_resgid = EXT2_DEF_RESGID;
    s->s_first_ino = EXT2_GOOD_OLD_FIRST_INO;
    s->s_inode_size = EXT2_GOOD_OLD_INODE_SIZE;
    s->s_block_group_nr = 0;
    s->s_flags = 0;
    if (label && label[0]) {
        strncpy((char*)s->s_volume_name, label, sizeof(s->s_volume_name));
    }
}

static int do_initialize_fs(const char* target_path,
                            uint64_t image_bytes,
                            uint32_t block_size,
                            int enable_64bit,
                            int enable_csum,
                            io_manager io,
                            char* err, int errlen)
{
    struct ext2_super_block s;
    fill_sb_basic(&s, image_bytes, block_size, enable_64bit, enable_csum, NULL);

    ext2_filsys fs = NULL;
    errcode_t rc = ext2fs_initialize(target_path, EXT2_FLAG_RW | (enable_64bit ? EXT2_FLAG_64BITS : 0), &s, io, &fs);
    if (rc) { set_err_rc(err, errlen, "ext2fs_initialize failed", rc); return -1; }

    rc = ext2fs_allocate_tables(fs);
    if (rc) { ext2fs_close(fs); set_err_rc(err, errlen, "allocate_tables failed", rc); return -1; }

    // journal (best effort)
    rc = ext2fs_add_journal_inode(fs, 0, 0); (void)rc;

    ext2fs_mark_super_dirty(fs);
    rc = ext2fs_write_bitmaps(fs);
    if (rc) { ext2fs_close(fs); set_err_rc(err, errlen, "write_bitmaps failed", rc); return -1; }

    rc = ext2fs_close(fs);
    if (rc) { set_err_rc(err, errlen, "close after mkfs failed", rc); return -1; }
    return 0;
}

SHIM_API int ext4_mkfs(const char* target_path, uint64_t image_bytes, uint32_t block_size, const char* label, const char* opt_uuid, char* err, int errlen) {
    (void)opt_uuid; // optional; not parsed here
    if (!target_path || image_bytes < 16ull * 1024 * 1024) {
        set_err(err, errlen, "image too small (>=16MiB)"); return -1;
    }
    if (block_size != 1024 && block_size != 2048 && block_size != 4096) block_size = 4096;

    if (create_sparse_file(target_path, image_bytes, err, errlen)) return -1;

    io_manager io = windows_io_manager;

    // Try a cascade of feature sets to avoid ext2 71 on some builds
    // 1) 64bit + metadata_csum
    if (do_initialize_fs(target_path, image_bytes, block_size, 1, 1, io, err, errlen) == 0) goto label_set;
    // 2) metadata_csum only
    if (do_initialize_fs(target_path, image_bytes, block_size, 0, 1, io, err, errlen) == 0) goto label_set;
    // 3) 64bit only
    if (do_initialize_fs(target_path, image_bytes, block_size, 1, 0, io, err, errlen) == 0) goto label_set;
    // 4) basic (no advanced features)
    if (do_initialize_fs(target_path, image_bytes, block_size, 0, 0, io, err, errlen) == 0) goto label_set;
    // All failed
    return -1;

label_set:
    // Set label if provided
    if (label && label[0]) {
        ext2_filsys fs = NULL;
        errcode_t rc = ext2fs_open(target_path, EXT2_FLAG_RW, 0, 0, io, &fs);
        if (rc == 0) {
            strncpy((char*)fs->super->s_volume_name, label, sizeof(fs->super->s_volume_name));
            ext2fs_close(fs);
        }
    }
    set_err(err, errlen, NULL);
    return 0;
}
