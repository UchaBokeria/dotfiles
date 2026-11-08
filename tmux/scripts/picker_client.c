/* Small local transport: pass the popup tty to the preloaded picker worker. */
#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>

static volatile sig_atomic_t worker_fd = -1, transport_fd = -1;
static void forward(int sig) {
    if (worker_fd >= 0) syscall(SYS_pidfd_send_signal, worker_fd, sig, NULL, 0);
    else if (sig != SIGWINCH && transport_fd >= 0) { close(transport_fd); transport_fd = -1; }
}
static int exact(int fd, void *buf, size_t size) {
    size_t n = 0;
    while (n < size) {
        ssize_t r = read(fd, (char *)buf + n, size - n);
        if (r < 0 && errno == EINTR) continue;
        if (r <= 0) return -1;
        n += (size_t)r;
    }
    return 0;
}
static void fallback(char **argv) {
    char service[PATH_MAX];
    snprintf(service, sizeof(service), "%s", argv[2]);
    char *slash = strrchr(service, '/');
    if (slash && (size_t)(slash - service) + 20 < sizeof(service)) {
        strcpy(slash + 1, "picker_service.py");
        pid_t pid = fork();
        if (pid == 0) {
            setsid();
            pid_t detached = fork();
            if (detached < 0) _exit(1);
            if (detached > 0) _exit(0);
            int fd = open("/dev/null", O_RDWR);
            if (fd >= 0) { dup2(fd, 0); dup2(fd, 1); dup2(fd, 2); if (fd > 2) close(fd); }
            execlp("python3", "python3", service, "serve", (char *)NULL);
            _exit(127);
        }
        if (pid > 0) { while (waitpid(pid, NULL, 0) < 0 && errno == EINTR) {} }
    }
    execl(argv[2], argv[2], "open-ui", "--client", argv[3], "--pane", argv[4], "--workspace", argv[5], (char *)NULL);
    perror("picker fallback");
    exit(1);
}
int main(int argc, char **argv) {
    if (argc != 6 || !isatty(0) || !isatty(1)) return 2;
    int probe = (int)syscall(SYS_pidfd_open, getpid(), 0);
    if (probe < 0) fallback(argv);
    close(probe);
    int fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    if (fd < 0) fallback(argv);
    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    if (strlen(argv[1]) >= sizeof(addr.sun_path)) { close(fd); fallback(argv); }
    strcpy(addr.sun_path, argv[1]);
    struct timeval timeout = { .tv_sec = 1 };
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) { close(fd); fallback(argv); }
    struct ucred peer; socklen_t length = sizeof(peer);
    if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &peer, &length) || peer.uid != getuid()) { close(fd); fallback(argv); }
    char data[4096] = "open";
    size_t used = 5;
    for (int i = 3; i < 6; i++) {
        size_t n = strlen(argv[i]) + 1;
        if (n > sizeof(data) - used) { close(fd); fallback(argv); }
        memcpy(data + used, argv[i], n); used += n;
    }
    const char *names[] = { "TERM", "LANG", "LC_ALL", "LC_CTYPE", "COLORTERM", "TMUX" };
    for (size_t i = 0; i < sizeof(names)/sizeof(names[0]); i++) {
        const char *value = getenv(names[i]); if (!value) value = "";
        size_t n = strlen(value) + 1;
        if (n > sizeof(data) - used) { close(fd); fallback(argv); }
        memcpy(data + used, value, n); used += n;
    }
    struct iovec io = { .iov_base = data, .iov_len = used };
    char ancillary[CMSG_SPACE(sizeof(int))] = {0};
    struct msghdr msg = { .msg_iov = &io, .msg_iovlen = 1, .msg_control = ancillary, .msg_controllen = sizeof(ancillary) };
    struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET; cmsg->cmsg_type = SCM_RIGHTS; cmsg->cmsg_len = CMSG_LEN(sizeof(int));
    int tty = 0; memcpy(CMSG_DATA(cmsg), &tty, sizeof(tty));
    int32_t pid = 0;
    if (sendmsg(fd, &msg, MSG_NOSIGNAL) != (ssize_t)used) { close(fd); fallback(argv); }
    char reply_control[CMSG_SPACE(4*sizeof(int))] = {0};
    struct iovec reply_io = { .iov_base = &pid, .iov_len = sizeof(pid) };
    struct msghdr reply = { .msg_iov = &reply_io, .msg_iovlen = 1,
                           .msg_control = reply_control, .msg_controllen = sizeof(reply_control) };
    ssize_t count;
    do { count = recvmsg(fd, &reply, MSG_CMSG_CLOEXEC); } while (count < 0 && errno == EINTR);
    int descriptor = -1, descriptors = 0;
    if (count >= 0) {
        for (struct cmsghdr *item = CMSG_FIRSTHDR(&reply); item; item = CMSG_NXTHDR(&reply, item)) {
            if (item->cmsg_level != SOL_SOCKET || item->cmsg_type != SCM_RIGHTS) continue;
            size_t total = (item->cmsg_len - CMSG_LEN(0)) / sizeof(int);
            int *values = (int *)CMSG_DATA(item);
            for (size_t i = 0; i < total; i++) {
                if (descriptors++ == 0) descriptor = values[i]; else close(values[i]);
            }
        }
    }
    if (count != sizeof(pid) || pid <= 0 || descriptors != 1 || (reply.msg_flags & (MSG_TRUNC|MSG_CTRUNC))) {
        if (descriptor >= 0) close(descriptor);
        close(fd); fallback(argv);
    }
    /* The server passes a pidfd opened while this child is still unreaped;
       signals can never reach an unrelated process after numeric PID reuse. */
    worker_fd = descriptor;
    transport_fd = fd;
    struct sigaction action = { .sa_handler = forward };
    sigemptyset(&action.sa_mask);
    sigaction(SIGWINCH, &action, NULL); sigaction(SIGHUP, &action, NULL);
    sigaction(SIGTERM, &action, NULL); sigaction(SIGINT, &action, NULL);
    timeout.tv_sec = timeout.tv_usec = 0;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    int32_t status = 1;
    if (exact(fd, &status, sizeof(status))) status = 1;
    if (worker_fd >= 0) close(worker_fd);
    worker_fd = -1;
    if (transport_fd >= 0) close(fd);
    transport_fd = -1;
    return status >= 0 && status <= 255 ? status : 1;
}
