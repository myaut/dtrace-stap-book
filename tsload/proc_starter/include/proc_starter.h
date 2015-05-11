#ifndef PROC_STARTER_H_
#define PROC_STARTER_H_

#include <tsload/defs.h>

#include <tsload/syncqueue.h>

#include <tsload/load/wlparam.h>

struct proc_starter_workload {
	wlp_integer_t num_shells;
	char shell[1024];
};

struct proc_starter_data {
	squeue_t sq;
};

struct proc_starter_request {
	char command[512];

};
#endif /* BUSY_WAIT_H_ */

