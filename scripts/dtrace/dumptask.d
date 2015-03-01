#!/usr/sbin/dtrace -qCs

/**
 * dumptask.d
 * 
 * Один раз в секунду печатает информацию по текущему процессу
 * Включает макросы извлечения из kthread_t и сопутствующих структур
 * Использует стандартные трансляторы psinfo_t* и lwpsinfo_t*s
 * 
 * Оттестировано на Solaris 11.2
 */

int argnum;
void* argvec;
string pargs[int];

int fdnum;
uf_entry_t* fdlist;

#define PSINFO(thread) xlate<psinfo_t *>(thread->t_procp)
#define LWPSINFO(thread) xlate<lwpsinfo_t *>(thread)

#define PUSER(thread) thread->t_procp->p_user

/**
 * Вытаскиваем указатель из массива указателей в зависимости
 * от модели процесса (32- или 64-бита)
 */
#define DATAMODEL_ILP32 0x00100000
#define GETPTR(proc, array, idx)                                \
    ((uintptr_t) ((proc->p_model == DATAMODEL_ILP32)            \
    ?  ((uint32_t*) array)[idx] : ((uint64_t*) array)[idx]))
#define GETPTRSIZE(proc)                                        \
    ((proc->p_model == DATAMODEL_ILP32)? 4 : 8)

#define FILE(list, num)     list[num].uf_file
#define CLOCK_TO_MS(clk)    (clk) * (`nsec_per_tick / 1000000)

/* Вытаскиваем путь до vnode */
#define VPATH(vn)                                \
    ((vn) == NULL || (vn)->v_path == NULL)       \
        ? "unknown" : stringof((vn)->v_path)

/* Корневая директория процесса - для зон может не совпадать с / */
#define DUMP_TASK_ROOT(thread)                   \
    printf("\troot: %s\n",                       \
        PUSER(thread).u_rdir == NULL             \
        ? "/"                                    \
        : VPATH(PUSER(thread).u_rdir));

/* Текущая рабочая директория процесса */
#define DUMP_TASK_CWD(thread)                    \
    printf("\tcwd: %s\n",                        \
        VPATH(PUSER(thread).u_cdir));        

/* Исполнимый файл процесса */
#define DUMP_TASK_EXEFILE(thread)                \
    printf("\texe: %s\n",                        \
        VPATH(thread->t_procp->p_exec));    

/* Копируем до 9 аргументов процесса. Само количество получаем
   через транслятор psinfo_t, сами же аргументы и указатели (необходимой
   в процессе длины) размещаются в стеке процесса. Копируем указатели 
   в argvec и сами аргументы в массив pargs. 
   См. также функцию ядра exec_args() */
#define COPYARG(t, n)                                           \
    pargs[n] = (n < argnum && argvec != 0)                      \
        ? copyinstr(GETPTR(t->t_procp, argvec, n)) : "???"
#define DUMP_TASK_ARGS_START(thread)                            \
    printf("\tpsargs: %s\n", PSINFO(thread)->pr_psargs);        \
    argnum = PSINFO(thread)->pr_argc;                           \
    argvec = (PSINFO(thread)->pr_argv != 0) ?                   \
               copyin(PSINFO(thread)->pr_argv,                  \
                      argnum * GETPTRSIZE(thread->t_procp)) : 0;\
    COPYARG(thread, 0); COPYARG(thread, 1); COPYARG(thread, 2); \
    COPYARG(thread, 3); COPYARG(thread, 4); COPYARG(thread, 5); \
    COPYARG(thread, 6); COPYARG(thread, 7); COPYARG(thread, 8); 

/* Время запуска процесса */
#define DUMP_TASK_START_TIME(thread)                         \
    printf("\tstart time: %ums\n",                           \
        (unsigned long) thread->t_procp->p_mstart / 1000000);

/* Процессорное время, затраченное процессом. Вообще говоря,
   оно измеряется через LWP microstate, а поля p_utime и p_stime
   устанавливаются при выходе из процесса  */
#define DUMP_TASK_TIME_STATS(thread)                         \
    printf("\tuser: %ldms\t kernel: %ldms\n",                \
        CLOCK_TO_MS(thread->t_procp->p_utime),               \
        CLOCK_TO_MS(thread->t_procp->p_stime));            
    
#define DUMP_TASK_FDS_START(thread)                          \
    fdlist = PUSER(thread).u_finfo.fi_list;                  \
    fdcnt = 0;                                               \
    fdnum = PUSER(thread).u_finfo.fi_nfiles;                 
    
#define DUMP_TASK(thread)                                    \
    printf("Task %p is %d/%d@%d %s\n", thread,               \
            PSINFO(thread)->pr_pid,                          \
            LWPSINFO(thread)->pr_lwpid,                      \
            LWPSINFO(thread)->pr_onpro,                      \
            PUSER(thread).u_comm);                           \
    DUMP_TASK_EXEFILE(thread)                                \
    DUMP_TASK_ROOT(thread)                                   \
    DUMP_TASK_CWD(thread)                                    \
    DUMP_TASK_ARGS_START(thread)                             \
    DUMP_TASK_FDS_START(thread)                              \
    DUMP_TASK_START_TIME(thread)                             \
    DUMP_TASK_TIME_STATS(thread)    

#define _DUMP_ARG_PROBE(probe, argi)                         \
probe /argi < argnum/ {                                      \
    printf("\targ%d: %s\n", argi, pargs[argi]); }    
#define DUMP_ARG_PROBE(probe)                                \
    _DUMP_ARG_PROBE(probe, 0)   _DUMP_ARG_PROBE(probe, 1)    \
    _DUMP_ARG_PROBE(probe, 2)   _DUMP_ARG_PROBE(probe, 3)    \
    _DUMP_ARG_PROBE(probe, 4)   _DUMP_ARG_PROBE(probe, 5)    \
    _DUMP_ARG_PROBE(probe, 6)   _DUMP_ARG_PROBE(probe, 7)    \
    _DUMP_ARG_PROBE(probe, 8)

#define _DUMP_FILE_PROBE(probe, fd)                          \
probe /fd < fdnum && FILE(fdlist, fd)/ {                     \
    printf("\tfile%d: %s\n", fd,                             \
                VPATH(FILE(fdlist, fd)->f_vnode)); }
#define DUMP_FILE_PROBE(probe)                               \
    _DUMP_FILE_PROBE(probe, 0)  _DUMP_FILE_PROBE(probe, 1)   \
    _DUMP_FILE_PROBE(probe, 2)  _DUMP_FILE_PROBE(probe, 3)   \
    _DUMP_FILE_PROBE(probe, 4)  _DUMP_FILE_PROBE(probe, 5)   \
    _DUMP_FILE_PROBE(probe, 6)  _DUMP_FILE_PROBE(probe, 7)

BEGIN {
    proc = 0;
    argnum = 0;
    fdnum = 0;
}

tick-1s {
    DUMP_TASK(curthread);
}

DUMP_ARG_PROBE(tick-1s)
DUMP_FILE_PROBE(tick-1s)
