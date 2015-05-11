#ifndef SHELL_H_
#define SHELL_H_

#define DEV_PTS_NAMELEN			32
#define	DEV_PTY_MASTER			"/dev/ptmx"

#define SHELL_BUF_SIZE			2048
#define SHELL_WATERMARK			128

#define SHELL_SETSID_ERROR			1
#define SHELL_SLAVE_OPEN_ERROR		2
#define SHELL_CLOSE_MASTER_ERROR	3
#define SHELL_CLOSE_SLAVE_ERROR		4
#define SHELL_DUP2_ERROR			5
#define SHELL_EXECVE_ERROR			6
#define SHELL_SIGRESET_ERROR		7
#define SHELL_MKTERM_ERROR			8

#define SHELL_TRACE_PTRS			0x01
#define SHELL_TRACE_BUFS			0x02

typedef struct pt_shell {
	int   sh_pty;
	int   sh_pid;

	char  sh_pt_name[DEV_PTS_NAMELEN];

	char* sh_buffer;
	size_t sh_buf_size;

	char* sh_start;
	char* sh_end;

	/* Variables used only in sh_create() */
	int   sh_pt_slave;
	/* Status PIPE. We couldn't track errors on child directly because
	 * logging uses mutexes, and using they from forked processes is dangerous */
	int   sh_status_pipes[2];
} ps_shell_t;

ps_shell_t* sh_create(const char* filename, char* const argv[],
					  char* const envp[]);
void sh_destroy(ps_shell_t* sh);

char* sh_expect(ps_shell_t* sh, const char* line);

#endif /* SHELL_H_ */
