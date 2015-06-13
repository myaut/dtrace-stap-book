pid$target::mutex_lock_impl:entry
{ 
	self->mtxtime = timestamp; 
}

plockstat$target:::mutex-acquire
/ self->mtxtime != 0 /
{ 
	@[ustack()] = quantize(timestamp - self->mtxtime);
	self->mtxtime = 0;
}

pid$target::experiment_unconfigure:entry
{
	printa(@);
}