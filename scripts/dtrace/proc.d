#!/usr/sbin/dtrace -qCs

#define PARENT_EXECNAME(thread) \
    (thread->t_procp->p_parent != NULL) \
        ? stringof(thread->t_procp->p_parent->p_user.u_comm)    \
        : "???" 
        
proc:::, syscall::fork*:entry, syscall::exec*:entry, 
    syscall::wait*:entry  {
    printf("%6d[%8s]/%6d[%8s] %s::%s:%s\n", 
        pid, execname, ppid, PARENT_EXECNAME(curthread), 
           probeprov, probefunc, probename);
}

proc:::create {
    printf("\tPID: %d -> %d\n", curpsinfo->pr_pid, args[0]->pr_pid);
}


proc:::exec {
    printf("\tfilename: %s\n", args[0]);
}

proc:::exit {
    printf("\treturn code: %d\n", args[0]);
}
