#!/usr/bin/dtrace
#pragma D option bufsize=8m
#pragma D option switchrate=100hz

pid$target::pthread_create:entry {
    self->thread_id_ptr = (uintptr_t) arg0;
    self->thread_func = arg2;
    self->thread_arg = arg3;
}
pid$target::pthread_create:return {
    this->thread_id = * (uint_t*) copyin(self->thread_id_ptr, sizeof(uint_t));
    printf("[%d] pthread_create %x ", tid, this->thread_id);
    usym(self->thread_func);
    printf("(%x)\n", self->thread_arg);
}
pid$target::pthread_join:entry {
    self->thread_id = (uint_t) arg0;
    printf("[%d] pthread_join %x\n", tid, self->thread_id);
}
pid$target::pthread_join:return {
    printf("[%d] pthread_join:return %x -> %d\n", tid, self->thread_id, arg1);
}

plockstat$target:::, 
pid$target::pthread_cond_*wait*:entry,
pid$target::pthread_cond_*wait*:return,
pid$target::pthread_cond_signal:entry,
pid$target::pthread_cond_broadcast:entry {
    printf("[%d] %s:%s ", tid, probefunc, probename);
    usym(arg0);
    printf("[%p]\n", arg0);
    ustack(6);
}