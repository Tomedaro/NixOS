#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>
#include <sys/mman.h>

/* Intercept shm_open and immediately ftruncate to the requested size.
   The size isn't known here, so we intercept wl_shm_create_pool instead. */

/* wayland-client struct forward — just need the first call arg */
struct wl_shm;

typedef void* (*wl_shm_create_pool_t)(struct wl_shm*, int fd, int32_t size);

void* wl_shm_create_pool(struct wl_shm* shm, int fd, int32_t size) {
    /* Ensure fd is sized before Hyprland validates it */
    ftruncate(fd, (off_t)size);

    wl_shm_create_pool_t real = dlsym(RTLD_NEXT, "wl_shm_create_pool");
    return real(shm, fd, size);
}
