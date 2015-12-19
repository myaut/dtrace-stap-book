#!/usr/sbin/dtrace -qCZs

BEGIN {
    self->depth = 0;
}

foo$target::: {
    /* This probe is just a workaround for -xlazyload */
}

python$target:::function-entry {
    func_stack[self->depth] = arg1;
    file_stack[self->depth] = arg0;
    
    self->depth++;
}
python$target:::function-return {
    self->depth--;
}

pid$target::malloc:entry 
/ func_stack[self->depth] != 0 / {
    @mallocs[copyinstr(func_stack[self->depth]),
             copyinstr(file_stack[self->depth])] = sum(arg0);
}