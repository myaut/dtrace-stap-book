#pragma D option strsize=2048
#pragma D option bufsize=128M
#pragma D option switchrate=20hz

ap*:::internal-redirect  {
    printf("[httpd] redirect\t'%s' -> '%s'\n", copyinstr(arg0), copyinstr(arg1));
}

ap*:::read-request-entry {
    printf("[httpd] read-request\n");
}

ap*:::read-request-success {
    this->servername = (arg3) ? copyinstr(arg3) : "???";
    
    printf("[httpd] read-request\t%s %s %s  [status: %d]\n", 
        copyinstr(arg1), this->servername, copyinstr(arg2), arg4);
}

ap*:::process-request-entry {
    printf("[httpd] process-request\t'%s'\n", copyinstr(arg1));
}

ap*:::process-request-return {
    printf("[httpd] process-request\t'%s' access-status: %d\n", 
        copyinstr(arg1), arg2);
}

php*:::request-startup,
php*:::request-shutdown {
    printf("[ PHP ] %s\t%s '%s' file: %s \n", probename, 
        copyinstr(arg2), copyinstr(arg1), copyinstr(arg0));
}

php*:::function-entry,
php*:::function-return {
    printf("[ PHP ] %s\t%s%s%s file: %s:%d \n", probename, 
        copyinstr(arg3), copyinstr(arg4), copyinstr(arg0),
        basename(copyinstr(arg1)), arg2);
}

mysql*:::query-parse-start {
   self->parsequery = copyinstr(arg0, 1024);
}

mysql*:::query-parse-done {
   printf("[MySQL] query-parse\t'%s' status: %d\n", self->parsequery, arg0);
}

mysql*:::query-exec-start {
   self->execquery = copyinstr(arg0, 1024);
}

mysql*:::query-exec-done {
   printf("[MySQL] query-exec\t'%s' status: %d\n", self->execquery, arg0);
}

