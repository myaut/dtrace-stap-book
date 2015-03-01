cv_wait*:entry  {
    self->timeout = 0;
}

cv_timedwait_hires:entry,
cv_timedwait_sig_hires:entry {
    self->timeout = (arg2 / arg3) * arg3;
}

cv_wait:entry,
cv_wait_sig:entry,
cv_timedwait_hires:entry,
cv_timedwait_sig_hires:entry  {
    printf("[%d] %s %s cv: %p mutex: %p timeout: %d\n", 
            pid, execname, probefunc, arg0, arg1, self->timeout);
    stack(4);
}

cv_signal:entry,
cv_broadcast:entry {
    printf("[%d] %s %s cv: %p\n", 
            pid, execname, probefunc, arg0);
    stack(4);
}
