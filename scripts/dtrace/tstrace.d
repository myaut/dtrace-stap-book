#!/usr/sbin/dtrace -qCs
/**
    tstrace.d -  traces Solaris dispatcher (and prints some TS information)
    Usage: tstrace.d <cpu#> 
    Note: Use -DSOLARIS10 on Solaris 10

    Tested on Solaris 11.2
*/

string classnames[struct thread_ops*];
int disp_spec;
int disp_commit;

/* Converts time from t_disp_time/cpu_last_swtch to nanoseconds
    - Solaris 10 uses system ticks (lbolts)
    - Solaris 11 uses unscaled hrtime_t 
   HRT_CONVERT converts unscaled time to nanoseconds
   HRT_DELTA substracts system time from its argument */
#ifdef SOLARIS10
#   define HRT_DELTA(ns)      (`nsec_per_tick * (`lbolt64 - (ns)))
#else
#   define __HRT_CONVERT(ts)                                         \
        (((ts >> (32 - NSEC_SHIFT)) * NSEC_SCALE)        +           \
         ((((ts << NSEC_SHIFT) & 0xFFFFFFFF) * NSEC_SCALE) >> 32))
#   if defined(__i386) || defined(__amd64)
#       define NSEC_SHIFT    5
#       define NSEC_SCALE    `hrt->nsec_scale
#       define HRT_CONVERT(ts) \
            ((`tsc_gethrtime_enable) ? __HRT_CONVERT(ts) : ts )
#   elif defined(__sparc)
#       define NANOSEC       1000000000
#       define NSEC_SHIFT    4
#       define NSEC_SCALE    				\
	((uint64_t)((NANOSEC << (32 - NSEC_SHIFT)) / `sys_tick_freq) & ~1)
#       define HRT_CONVERT       __HRT_CONVERT       
#   endif
#   define HRT_DELTA(ns)       ((timestamp > HRT_CONVERT(ns)) ? timestamp - HRT_CONVERT(ns) : 0)
#endif

#define TSINFO(t)           ((tsproc_t*) (t->t_cldata))
#define KTHREAD(t)          ((kthread_t*) (t))
#define KTHREADCPU(t)       ((kthread_t*) (t))->t_cpu->cpu_id
#define PSINFO(thread)      xlate<psinfo_t *>(thread->t_procp)   

#define TSKPRI      0x01    
#define TSBACKQ     0x02    
#define TSIA        0x04    
/* We ignore TSIA* flags here */
#define TSRESTORE   0x20    

/* TSFLAGSSTR creates string represenation for TS flags */
#define TSFLAGS(t)              (TSINFO(t)->ts_flags)
#define TSFLAGSSTR(t)                                              \
        strjoin(                                                   \
            strjoin(                                               \
                (TSFLAGS(t) & TSKPRI)    ?   "TSKPRI|" : "",       \
                (TSFLAGS(t) & TSBACKQ)   ?   "TSBACKQ|" : ""),     \
            strjoin(                                               \
                (TSFLAGS(t) & TSIA)      ?   "TSIA|" : "",         \
                (TSFLAGS(t) & TSRESTORE) ?   "TSRESTORE" : ""))

/* Returns true value if thread belongs to TS or IA class */
#define ISTSTHREAD(t)                                               \
    ((t->t_clfuncs == &`ts_classfuncs.thread) ||                    \
     (t->t_clfuncs == &`ia_classfuncs.thread))

#define TCLNAME(t_clfuncs)      classnames[t_clfuncs] 

#define DUMP_KTHREAD_INFO(hdr, thread)                                   \
    printf("\t%s t: %p %s[%d]/%d %s pri: %d\n", hdr, thread,             \
       PSINFO(thread)->pr_fname, PSINFO(thread)->pr_pid, thread->t_tid,  \
       TCLNAME(thread->t_clfuncs), thread->t_pri)

#define DUMP_DISP_INFO(disp)                                      \
    printf("\tDISP: nrun: %d npri: %d max: %d(%d)\n",             \
            (disp)->disp_nrunnable, (disp)->disp_npri,            \
            (disp)->disp_maxrunpri, (disp)->disp_max_unbound_pri) \

#define DUMP_CPU_INFO(cpup)                                              \
    this->delta = HRT_DELTA((cpup)->cpu_last_swtch);                     \
    printf("\tCPU : last switch: T-%dus rr: %d kprr: %d\n",                \
            this->delta / 1000, (cpup)->cpu_runrun, (cpup)->cpu_kprunrun); \
    DUMP_KTHREAD_INFO("\tcurrent", (cpup)->cpu_thread);                  \
    DUMP_KTHREAD_INFO("\tdisp   ", (cpup)->cpu_dispthread);              \
    DUMP_DISP_INFO(cpup->cpu_disp) 

#define TS_QUANTUM_LEFT(tspp)                  \
    ((tspp)->ts_flags & TSKPRI)                \
        ?   (tspp)->ts_timeleft                \
        :   (tspp)->ts_timer - (tspp)->ts_lwp->lwp_ac.ac_clock       

#define DUMP_TSPROC_INFO(thread)                                    \
    printf("\tTS: timeleft: %d flags: %s cpupri: %d upri: %d boost: %d => %d\n",  \
            TS_QUANTUM_LEFT(TSINFO(thread)), TSFLAGSSTR(thread),    \
            TSINFO(thread)->ts_cpupri, TSINFO(thread)->ts_upri,     \
            TSINFO(thread)->ts_boost, TSINFO(thread)->ts_scpri )      

BEGIN {
    printf("Tracing CPU%d...\n", $1);

    classnames[&`ts_classfuncs.thread]  =  "TS";   
    classnames[&`ia_classfuncs.thread]  =  "IA";   
    classnames[&`sys_classfuncs.thread] =  "SYS";  
    classnames[&`fx_classfuncs.thread]  =  "FX";   
    /* classnames[&`rt_classfuncs.thread] = "RT"; */
    classnames[&`sysdc_classfuncs.thread] = "SDC";
}

/* Helper functions tracer
    cpu_surrender - called when thread leaves CPU
    setbackdq  - called when thread is put onto queue tail
    setfrontdq  - called when thread is put onto disp queue head */
fbt::cpu_surrender:entry 
/cpu == $1/ {
    DUMP_KTHREAD_INFO("cpu_surrender", KTHREAD(arg0));
}

fbt::set*dq:entry 
/KTHREADCPU(arg0) == $1 && ISTSTHREAD(KTHREAD(arg0))/ {
    printf("=> %s \n", probefunc);
    DUMP_KTHREAD_INFO(probefunc, KTHREAD(arg0));
    DUMP_TSPROC_INFO(KTHREAD(arg0));    
}

/* Man dispatcher function disp(). Uses speculations so only when 
   TS thread moves onto CPU or/and leaves it, data will be printed. */
fbt::disp:entry 
/cpu == $1/ {
    disp_spec = speculation();
    disp_commit = 0;
    
    speculate(disp_spec);
    printf("=> disp \n");
    DUMP_CPU_INFO(`cpu[$1]);
}
    
fbt::disp:entry 
/cpu == $1/ {
    speculate(disp_spec);   DUMP_KTHREAD_INFO("curthread: ", curthread);
}

fbt::disp:entry 
/cpu == $1 && ISTSTHREAD(curthread)/ {
    speculate(disp_spec);   DUMP_TSPROC_INFO(curthread);
    disp_commit = 1;
}

fbt::disp:return
/cpu == $1/ {
    speculate(disp_spec);   DUMP_KTHREAD_INFO("disp", KTHREAD(arg1));
}

fbt::disp:return
/cpu == $1 && ISTSTHREAD(KTHREAD(arg1))/ {
    speculate(disp_spec);   DUMP_TSPROC_INFO(KTHREAD(arg1));
    disp_commit = 1;
}

fbt::disp:return
/cpu == $1 && disp_commit/ {
    commit(disp_spec);    
}

fbt::disp:return
/cpu == $1 && !disp_commit/ {
    discard(disp_spec);
}

/* System tick function clock_tick -- reflects changes in 
   thread and CPU parameters after tick */
sched:::tick
/cpu == $1 && ISTSTHREAD(KTHREAD(arg0))/ {
    printf("=> clock_tick \n");
    DUMP_CPU_INFO(`cpu[$1]);
    DUMP_KTHREAD_INFO("clock_tick", KTHREAD(arg0));
    DUMP_TSPROC_INFO(KTHREAD(arg0));    
}

/* Trace for wakeups -- traces awoken thread */
sched:::wakeup
/KTHREADCPU(arg0) == $1 && ISTSTHREAD(KTHREAD(arg0))/ {
    printf("=> %s [wakeup] \n", probefunc);
    DUMP_CPU_INFO(`cpu[$1]);
    DUMP_KTHREAD_INFO("wakeup", KTHREAD(arg0));
    DUMP_TSPROC_INFO(KTHREAD(arg0));
}
