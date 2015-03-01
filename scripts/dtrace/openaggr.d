syscall::openat*:entry
/(arg2 & O_CREAT) == O_CREAT/ {
    @create[execname, pid] = count();
}

syscall::openat*:entry
/(arg2 & O_CREAT) == 0/ {
    @open[execname, pid] = count();
}

syscall::openat*:return
/ arg1 > 0 / {
    @success[execname, pid] = count();
}

tick-$1s {
    printf("%Y\n", walltimestamp);
    printf("%12s %6s %6s %6s %s\n", 
              "EXECNAME", "PID", "CREATE", "OPEN", "SUCCESS");
    printa("%12s %6d %@6d %@6d %@d\n", @create, @open, @success);
    trunc(@create); trunc(@open); trunc(@success);
}