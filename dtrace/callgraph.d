#!/usr/sbin/dtrace -s

#pragma D option flowindent

syscall::open*:entry
/pid == $target && copyinstr(arg0) == "not_exists"/
{
        self->traceme = 1;
}

syscall::open*:return
/self->traceme/
{
        self->traceme = 0;
}

fbt:::entry
/self->traceme && probefunc != "bcmp"/
{
        
}

fbt:::return
/self->traceme && probefunc != "bcmp"/
{
        trace(arg1);
}
