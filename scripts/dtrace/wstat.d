#pragma D option aggsortkey
#pragma D option aggsortkeypos=0 

syscall::write:entry 
{
        @wbytes[pid, execname, arg0] = sum(arg2);
        @wops[pid, execname, arg0] = count();
}

tick-1s 
{
        normalize(@wbytes, 1024);       

        printf("%5s %12s %3s %7s %7s\n", 
			"PID", "EXECNAME", "FD", "OPS", "KBYTES");
        printa("%5u %12s %3u %7@d %7@dK\n", @wops, @wbytes);
        clear(@wbytes);
}