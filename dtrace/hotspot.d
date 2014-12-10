#!/usr/sbin/dtrace -qs

#pragma D option switchrate=10hz

hotspot$target:::class-loaded
{
        printf("%12s [???] %s\n", probename, stringof(copyin(arg0, arg1)));
}

hotspot$target:::method-entry,
hotspot$target:::method-return
{
        printf("%12s [%3d] %s.%s\n", probename, arg0, 
			stringof(copyin(arg1, arg2)), 
			stringof(copyin(arg3, arg4)));
}

hotspot$target:::thread-start,
hotspot$target:::thread-stop 
{
        printf("%12s [%3d] %s\n", probename, arg3, 
			stringof(copyin(arg0, arg1)));
}

hotspot$target:::monitor-contended-enter,
hotspot$target:::monitor-contended-exit
{
        printf("%12s [%3d] %s\n", probename, arg0, 
			stringof(copyin(arg2, arg3)));
}

