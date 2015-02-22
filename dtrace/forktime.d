uint64_t tm_fork_start[int];
uint64_t tm_fork_end[int];
uint64_t tm_exec_start[int];
uint64_t tm_exec_end[int];

syscall::*fork*:entry {
    self->tm_fork_start = timestamp;    
}
syscall::*fork*:return 
/arg1 > 0/ 
{
    tm_fork_start[arg1] = self->tm_fork_start;
}

proc:::start {
    tm_fork_end[pid] = timestamp;
}
proc:::exec {
    tm_exec_start[pid] = timestamp;
}
proc:::exec-* {
    tm_exec_end[pid] = timestamp;
}

proc:::exit 
/ tm_fork_start[pid] > 0 && tm_fork_end[pid] > 0 &&
  tm_exec_start[pid] > 0 && tm_exec_end[pid] > 0 /
{   
    @fork[curpsinfo->pr_fname, curpsinfo->pr_psargs] = 
            avg(tm_fork_end[pid] - tm_fork_start[pid]);
    @postfork[curpsinfo->pr_fname, curpsinfo->pr_psargs] = 
            avg(tm_exec_start[pid] - tm_fork_end[pid]);
    @exec[curpsinfo->pr_fname, curpsinfo->pr_psargs] = 
            avg(tm_exec_end[pid] - tm_exec_start[pid]);
    @proc[curpsinfo->pr_fname, curpsinfo->pr_psargs] = 
            avg(timestamp - tm_exec_end[pid]);

    tm_fork_start[pid] = 0; tm_fork_end[pid] = 0;
    tm_exec_start[pid] = 0; tm_exec_end[pid] = 0;
}

tick-1s {
    normalize(@fork, 1000);     normalize(@postfork, 1000);
    normalize(@exec, 1000);     normalize(@proc, 1000);

    printf("%32s %8s %8s %8s %8s\n",
                "COMMAND", "FORK", "POSTFORK", "EXEC", "PROC");
    printa("%10s %22s %@6dus %@6dus %@6dus %@6dus\n", 
                 @fork, @exec, @postfork, @proc);

    clear(@fork); clear(@postfork); clear(@exec); clear(@proc);
}



