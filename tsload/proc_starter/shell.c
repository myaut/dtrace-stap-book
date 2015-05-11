#define LOG_SOURCE "proc_starter"
#include <tsload/log.h>

#include <tsload/defs.h>

#include <tsload/mempool.h>

#include <shell.h>

#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <termios.h>
#include <errno.h>

#ifdef PLAT_SOLARIS
#include <stropts.h>
#endif

#ifdef PLAT_SOLARIS
char* ptsname_r(int pt_master, char* buf, size_t len) {
	/* Solaris doesn't have ptsname_r, but its ptsname is thread
	 * safe, so just call it and copy data from it to buf */
	return strncpy(buf, ptsname(pt_master), len);
}
#endif

#ifndef NSIG
#ifdef _NSIG
#define NSIG _NSIG
#else
#define NSIG 32
#endif
#endif

int shell_trace = 0;

static int sh_open_pty(ps_shell_t* sh) {
	int ret;

	/* Open/allocate pty master/slave devices */
	sh->sh_pty = open(DEV_PTY_MASTER, O_RDWR | O_NOCTTY);
	if(sh->sh_pty < 0) {
		logmsg(LOG_WARN, "Cannot open PTY master device '%s'. Errno = %d", DEV_PTY_MASTER, errno);
		return -1;
	}

	ret = grantpt(sh->sh_pty);
	if(ret < 0) {
		logmsg(LOG_WARN, "Cannot grant PTY master device %d. Errno = %d", sh->sh_pty, errno);
		goto error;
	}

	ret = unlockpt(sh->sh_pty);
	if(ret < 0) {
		logmsg(LOG_WARN, "Cannot grant PTY master device %d. Errno = %d", sh->sh_pty, errno);
		goto error;
	}

	ptsname_r(sh->sh_pty, sh->sh_pt_name, DEV_PTS_NAMELEN);
	sh->sh_pt_slave = open(sh->sh_pt_name, O_RDWR | O_NOCTTY);
	if(sh->sh_pt_slave < 0) {
		logmsg(LOG_WARN, "Cannot open PTY master device '%s'. Errno = %d", DEV_PTY_MASTER, errno);
		goto error;
	}

	/* FIXME: need something to do with pt_slave here */

	return 0;

error:
	close(sh->sh_pty);
	return -1;
}

void sh_child_error(ps_shell_t* sh, int errcode) {
	/* Error in child process */
	int err = errno;

	write(sh->sh_status_pipes[1], &errcode, sizeof(int));
	write(sh->sh_status_pipes[1], &err, sizeof(int));

	/* We do not need to call ts_finish() here, so use _exit */
	_exit(EXIT_FAILURE);
}

int sh_reset_signals(void) {
	int sig;
	sigset_t ss;

	if (sigemptyset(&ss) < 0)
		return -1;
	if (sigprocmask(SIG_SETMASK, &ss, NULL) < 0)
		return -1;
	for (sig = 1; sig < NSIG; sig++) {
		struct sigaction sa;
		memset(&sa, 0, sizeof(struct sigaction));
		sa.sa_handler = SIG_DFL;
		sa.sa_flags = SA_RESTART;
		if(sig == SIGKILL || sig == SIGSTOP)
			continue;
		if(sigaction(sig, &sa, NULL) < 0) {
			if(errno == EINVAL)
				continue;
			return -1;
		}
	}

	return 0;
}

int sh_make_term(ps_shell_t* sh) {
	struct termios term;

#ifdef PLAT_SOLARIS
	/* See man pts */
	if(ioctl(sh->sh_pt_slave, I_PUSH, "ptem") < 0)
		return 0;
	if(ioctl(sh->sh_pt_slave, I_PUSH, "ldterm") < 0)
		return 0;
#endif

	if(tcgetattr(sh->sh_pt_slave, &term) != 0)
		return -1;

	return 0;
}

void sh_execve(ps_shell_t* sh,
			   const char* filename, char* const argv[],
		  	   char* const envp[]) {
	int fd;
	int max_fd = sysconf(_SC_OPEN_MAX);

	if(close(sh->sh_pt_slave) == -1)
		sh_child_error(sh, SHELL_CLOSE_SLAVE_ERROR);
	if(close(sh->sh_pty) == -1)
		sh_child_error(sh, SHELL_CLOSE_MASTER_ERROR);
	if(setsid() == -1)
		sh_child_error(sh, SHELL_SETSID_ERROR);
	sh->sh_pt_slave = open(sh->sh_pt_name, O_RDWR | O_NOCTTY);
	if(sh_reset_signals() < 0)
		sh_child_error(sh, SHELL_SIGRESET_ERROR);
	if(sh_make_term(sh) < 0)
		sh_child_error(sh, SHELL_MKTERM_ERROR);
	if(sh->sh_pt_slave < 0)
		sh_child_error(sh, SHELL_SLAVE_OPEN_ERROR);
	if(dup2(sh->sh_pt_slave, STDIN_FILENO) == -1 ||
			dup2(sh->sh_pt_slave, STDOUT_FILENO) == -1 ||
			dup2(sh->sh_pt_slave, STDERR_FILENO) == -1)
		sh_child_error(sh, SHELL_DUP2_ERROR);

	close(sh->sh_pt_slave);
	sh->sh_pt_slave = -1;

	/* Close all files except 0, 1, and 2 */
	for(fd = 3; fd < max_fd; ++fd)
		close(fd);

	fcntl(sh->sh_status_pipes[0], F_SETFD, FD_CLOEXEC);
	fcntl(sh->sh_status_pipes[1], F_SETFD, FD_CLOEXEC);

	if(execve(filename, argv, envp) == -1)
		sh_child_error(sh, SHELL_EXECVE_ERROR);
}

#define SH_ERROR_HANDLE(errcode, msg, err)				\
		case errcode:									\
			logmsg(LOG_WARN, msg " Errno = %d", err);	\
			goto error;

ps_shell_t* sh_create(const char* filename, char* const argv[],
					  char* const envp[]) {
	int pt_master, pt_slave;
	char pt_name[DEV_PTS_NAMELEN];

	ps_shell_t* sh = mp_malloc(sizeof(ps_shell_t));

	int ret, err;
	ssize_t rcount;

	if(sh == NULL) {
		logmsg(LOG_WARN, "Cannot allocate ps_shell_t");
		return NULL;
	}

	sh->sh_pty = -1;
	sh->sh_pt_slave = -1;
	sh->sh_buffer = NULL;

	ret = pipe(sh->sh_status_pipes);
	if(ret < 0) {
		logmsg(LOG_WARN, "Cannot create status pipe pair. Errno = %d", errno);
		mp_free(sh);
		return NULL;
	}

	ret = sh_open_pty(sh);

	sh->sh_pid = fork();
	if(sh->sh_pid < 0) {
		logmsg(LOG_WARN, "fork() is failed. Errno = %d", errno);
		goto error;
	}

	if(sh->sh_pid != 0) {
		/* Master */

		/* Close remote side of a PIPE, it is owned by child now  */
		close(sh->sh_status_pipes[1]);
		close(sh->sh_pt_slave);

		rcount = (int) read(sh->sh_status_pipes[0], &ret, sizeof(int));

		if(rcount == 0) {
			close(sh->sh_status_pipes[0]);

			/* Child closed pipe - allocate buffers and return */
			sh->sh_buf_size = SHELL_BUF_SIZE;
			sh->sh_buffer = mp_malloc(SHELL_BUF_SIZE);

			sh->sh_start = sh->sh_buffer;
			sh->sh_end = sh->sh_start;

			*sh->sh_end = '\0';

			return sh;
		}

		/* Oops - an error, read errno and report error */
		read(sh->sh_status_pipes[0], &err, sizeof(int));
		switch(ret) {
		SH_ERROR_HANDLE(SHELL_SETSID_ERROR, "Failed to create new session.", err);
		SH_ERROR_HANDLE(SHELL_SLAVE_OPEN_ERROR, "Failed to re-open slave.", err);
		SH_ERROR_HANDLE(SHELL_CLOSE_MASTER_ERROR, "Failed to close master", err);
		SH_ERROR_HANDLE(SHELL_CLOSE_SLAVE_ERROR, "Failed to close slave", err);
		SH_ERROR_HANDLE(SHELL_DUP2_ERROR, "Failed to dup2().", err);
		SH_ERROR_HANDLE(SHELL_EXECVE_ERROR, "Failed to execve().", err);
		SH_ERROR_HANDLE(SHELL_SIGRESET_ERROR, "Failed to reset signals", err);
		SH_ERROR_HANDLE(SHELL_MKTERM_ERROR, "Failed to setup terminal", err);
		}
	}
	else {
		/* Child */
		sh_execve(sh, filename, argv, envp);
	}


error:
	close(sh->sh_status_pipes[0]);
	close(sh->sh_status_pipes[1]);

	close(sh->sh_pty);
	close(sh->sh_pt_slave);
	mp_free(sh);

	return NULL;
}

STATIC_INLINE size_t sh_avail(ps_shell_t* sh) {
	/* Save one byte for NULL-terminator */
	return sh->sh_buf_size - (sh->sh_end - sh->sh_buffer) - 1;
}

static size_t sh_buf_move(ps_shell_t* sh) {
	/* Deletes data from [buf; start) */
	size_t len = sh->sh_end - sh->sh_start;
	size_t begin = sh->sh_start - sh->sh_buffer;

	if(begin < SHELL_WATERMARK) {
		/* It's futile - we do not free too much bytes from our operation */
		return sh_avail(sh);
	}

	memmove(sh->sh_buffer, sh->sh_start, len);
	sh->sh_start = sh->sh_buffer;
	sh->sh_end = sh->sh_buffer + len;

	*sh->sh_end = '\0';

	return sh_avail(sh);
}

static size_t sh_buf_realloc(ps_shell_t* sh) {
	size_t end = sh->sh_end - sh->sh_buffer;
	size_t begin = sh->sh_start - sh->sh_buffer;

	sh->sh_buf_size += SHELL_BUF_SIZE;
	sh->sh_buffer = mp_realloc(sh->sh_buffer, sh->sh_buf_size);

	/* If realloc will relocate memory, advance pointers too */
	sh->sh_start = sh->sh_buffer + begin;
	sh->sh_end = sh->sh_buffer + end;

	return sh_avail(sh);
}

char* sh_expect(ps_shell_t* sh, const char* line) {
	size_t avail;
	ssize_t rbytes;

	char* p = strstr(sh->sh_start, line);

	if(p == NULL) {
		/* Feed more data from shell
		 * Destroy previously read data */
		sh->sh_start = sh->sh_end;

		while(p == NULL) {
			avail = sh_avail(sh);

			if(avail < SHELL_WATERMARK) {
				/* Try to compress buffer  */
				avail = sh_buf_move(sh);

				if(avail < SHELL_WATERMARK) {
					avail = sh_buf_realloc(sh);
				}
			}

			rbytes = read(sh->sh_pty, sh->sh_end, avail);

			if(shell_trace & SHELL_TRACE_PTRS) {
				printf("READ %5d %5d %5d -> %5d\n", (int) (sh->sh_start - sh->sh_buffer),
						(int) (sh->sh_end - sh->sh_buffer), (int) avail, (int) rbytes);
			}

			if(rbytes == -1)
				return NULL;

			sh->sh_end += rbytes;
			*sh->sh_end = '\0';

			p = strstr(sh->sh_start, line);
		}
	}

	if(shell_trace & SHELL_TRACE_BUFS) {
		fputs(sh->sh_start, stderr);
	}

	sh->sh_start = p + sizeof(line);
	return sh->sh_start;
}

void sh_destroy(ps_shell_t* sh) {
	close(sh->sh_pty);

	/* waitpid/kill here? */

	mp_free(sh->sh_buffer);
	mp_free(sh);
}
