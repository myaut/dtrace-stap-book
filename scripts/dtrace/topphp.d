ap*:::process-request-entry {
	self->uri = copyinstr(arg1);
}

php*:::function-entry {
	self->starttime = timestamp;
}

php*:::function-return 
/ self->starttime != 0 / {
	this->func = strjoin(copyinstr(arg3), 
						 strjoin(copyinstr(arg4), copyinstr(arg0)));
	@[this->func, self->uri] = avg(timestamp - self->starttime);
}

END {
	printa(@);
}