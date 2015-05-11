#ifndef FILE_OPENER_H_
#define FILE_OPENER_H_

#include <tsload/defs.h>

#include <tsload/load/wlparam.h>

struct file_opener_workload {
	char root_dir[1024];
	wlp_integer_t created_files;
	wlp_integer_t max_files;

};

struct file_opener_request {
	wlp_integer_t file;
	wlp_bool_t create;

};
#endif /* BUSY_WAIT_H_ */

