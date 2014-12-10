#!/usr/sbin/dtrace -qCs

/**
 * taskdump.d
 * 
 * Один раз в секунду печатает информацию по текущему процессу
 * Включает макросы извлечения из kthread_t и сопутствующих структур
 * Использует стандартные трансляторы psinfo_t* и lwpsinfo_t*s
 * 
 * Оттестировано на Solaris 11 snv_151a
 */

int argnum;
int argcnt;
uintptr_t argvec;
this uintptr_t argptr;

int fdnum;
int fdcnt;
uf_entry_t* fdlist;

#define PSINFO(thread) xlate<psinfo_t *>(thread->t_procp)
#define LWPSINFO(thread) xlate<lwpsinfo_t *>(thread)

#define PUSER(thread) thread->t_procp->p_user

#define FILE(list, num) list[num].uf_file
#define CLOCK_TO_MS(clk)	(clk) * (`nsec_per_tick / 1000000)

#define DUMP_TASK_ROOT(thread)							\
	printf("\troot: %s\n", 							\
		PUSER(thread).u_rdir == NULL 					\
		? "/" 									\
		: PUSER(thread).u_rdir->v_path == NULL 				\
			? "<unknown>" 							\
			: stringof(PUSER(thread).u_rdir->v_path));

#define DUMP_TASK_EXEFILE(thread)							\
	printf("\texe: %s\n",								\
		thread->t_procp->p_exec == NULL 					\
		? "<unknown>" 								\
		: stringof(thread->t_procp->p_exec->v_path) );	
							
#define DUMP_TASK_CWD(thread)							\
	printf("\tcwd: %s\n", 								\
		PUSER(thread).u_cdir->v_path == NULL 				\
		? "<unknown>" 								\
		: stringof(PUSER(thread).u_cdir->v_path));		

#define DUMP_TASK_ARGS_START(thread)						\
	printf("\tpsargs: %s\n", PSINFO(thread)->pr_psargs);		\
	argnum = PSINFO(thread)->pr_argc;						\
	argvec = (uintptr_t) PSINFO(thread)->pr_argv;				\
	argcnt = 0;
	
#define DUMP_TASK_START_TIME(thread)						\
	printf("\tstart time: %ums\n", 						\
		(unsigned long) thread->t_procp->p_mstart / 1000000);
	
#define DUMP_TASK_TIME_STATS(thread)						\
	printf("\tuser: %ldms\t kernel: %ldms\n", 				\
		CLOCK_TO_MS(thread->t_procp->p_utime), 				\
		CLOCK_TO_MS(thread->t_procp->p_stime));			
	
#define DUMP_TASK_FDS_START(thread)						\
	fdnum = PUSER(thread).u_finfo.fi_nfiles; 				\
	fdlist = PUSER(thread).u_finfo.fi_list; 				\
	fdcnt = 0;
	
#define DUMP_TASK(thread) 								\
	printf("Task %p is %d/%d@%d %s\n", thread, 				\
			PSINFO(thread)->pr_pid, 					\
			LWPSINFO(thread)->pr_lwpid, 					\
			LWPSINFO(thread)->pr_onpro, 					\
			PUSER(thread).u_comm);						\
	DUMP_TASK_EXEFILE(thread)							\
	DUMP_TASK_ROOT(thread)								\
	DUMP_TASK_CWD(thread)								\
	DUMP_TASK_ARGS_START(thread)							\
	DUMP_TASK_FDS_START(thread)							\
	DUMP_TASK_START_TIME(thread)							\
	DUMP_TASK_TIME_STATS(thread)	

BEGIN {
	argnum = 0;
	fdnum = 0;
}

/**
 * Цикл, печатающий аргументы
 */
profile:::tick-1ms 
/argnum > 0/
{
	/**
	 * Массив аргументов argvec - массив 32-битных указателей 
	 * (для 32-битного приложения), поэтому Копируем 4 байта указателя со 	 * смещением argvec + argcnt * sizeof(uint32_t) в argptr
	 * 
	 * ЗАМЕЧАНИЕ: copyin и copyinstr копируют из текущего пространства 	 	 * процесса, для посторонних процессов *следует использовать pr_psargs 	 * из psinfo_t*
	 */
	this->argptr = *((uint32_t*) copyin(argvec + argcnt * sizeof(uint32_t), sizeof(char*)));
	printf("\targ%d: %s\n", argcnt, copyinstr(this->argptr));
	argcnt++;
	argnum--;
}

/**
 * Цикл, печатающий открытые файлы
 */
profile:::tick-1ms
/argnum == 0 && fdnum > 0 && FILE(fdlist, fdcnt)/
{
	printf("\tfile%d: %s\n", fdcnt, 
			FILE(fdlist, fdcnt)->f_vnode->v_path == NULL
			? "<unknown>" 
			: stringof(FILE(fdlist, fdcnt)->f_vnode->v_path));
	fdcnt++;
	fdnum--;
}

tick-1s {
	 DUMP_TASK(curthread);
}
