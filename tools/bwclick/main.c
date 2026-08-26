/* Send a real pointer click through zwlr_virtual_pointer_v1.
 *
 * Hyprland exposes no click dispatcher and this machine has no uinput module,
 * so there is otherwise no way to test whether a widget's onclick fires. It
 * does advertise the wlroots virtual-pointer protocol, which is exactly this.
 *
 * Kept in the repo rather than /tmp: it was rebuilt twice after scratch space
 * was cleared, and a test tool you cannot rely on being there is not a test
 * tool.
 */
#include <linux/input-event-codes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "vp.h"

static struct zwlr_virtual_pointer_manager_v1 *mgr;
static struct wl_seat *seat;

static void reg(void *d, struct wl_registry *r, uint32_t name,
                const char *iface, uint32_t ver) {
    (void)d; (void)ver;
    if (!strcmp(iface, "zwlr_virtual_pointer_manager_v1"))
        mgr = wl_registry_bind(r, name, &zwlr_virtual_pointer_manager_v1_interface, 1);
    else if (!strcmp(iface, "wl_seat"))
        seat = wl_registry_bind(r, name, &wl_seat_interface, 1);
}
static void reg_rm(void *d, struct wl_registry *r, uint32_t n) { (void)d;(void)r;(void)n; }
static const struct wl_registry_listener rl = { reg, reg_rm };

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: bwclick X Y [W H]\n"); return 2; }
    uint32_t x = atoi(argv[1]), y = atoi(argv[2]);
    uint32_t w = argc > 4 ? atoi(argv[3]) : 1920;
    uint32_t h = argc > 4 ? atoi(argv[4]) : 1080;

    struct wl_display *dpy = wl_display_connect(NULL);
    if (!dpy) { fprintf(stderr, "no display\n"); return 1; }
    struct wl_registry *r = wl_display_get_registry(dpy);
    wl_registry_add_listener(r, &rl, NULL);
    wl_display_roundtrip(dpy);
    if (!mgr) { fprintf(stderr, "no virtual pointer manager\n"); return 1; }

    struct zwlr_virtual_pointer_v1 *p =
        zwlr_virtual_pointer_manager_v1_create_virtual_pointer(mgr, seat);

    zwlr_virtual_pointer_v1_motion_absolute(p, 0, x, y, w, h);
    zwlr_virtual_pointer_v1_frame(p);
    wl_display_roundtrip(dpy);

    zwlr_virtual_pointer_v1_button(p, 10, BTN_LEFT, WL_POINTER_BUTTON_STATE_PRESSED);
    zwlr_virtual_pointer_v1_frame(p);
    wl_display_roundtrip(dpy);

    zwlr_virtual_pointer_v1_button(p, 60, BTN_LEFT, WL_POINTER_BUTTON_STATE_RELEASED);
    zwlr_virtual_pointer_v1_frame(p);
    wl_display_roundtrip(dpy);

    wl_display_flush(dpy);
    return 0;
}
