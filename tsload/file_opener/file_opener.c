#define LOG_SOURCE "file_opener"
#include <tsload/log.h>

#include <tsload/defs.h>

#include <tsload/pathutil.h>
#include <tsload/mempool.h>
#include <tsload/modapi.h>
#include <tsload/autostring.h>
#include <tsload/plat/posixdecl.h>

#include <tsload/load/workload.h>
#include <tsload/load/wltype.h>
#include <tsload/load/randgen.h>

#include <file_opener.h>

#include <stdlib.h>

#include <sys/stat.h>

DECLARE_MODAPI_VERSION(MOD_API_VERSION);
DECLARE_MOD_NAME("file_opener");
DECLARE_MOD_TYPE(MOD_TSLOAD);

MODEXPORT wlp_descr_t file_opener_params[] = {
	{ WLP_RAW_STRING, WLPF_NO_FLAGS,
	  WLP_STRING_LENGTH(1024),
	  WLP_NO_DEFAULT(),
	  "root_dir",
	  "Directory where files would be created / deleted",
	  offsetof(struct file_opener_workload, root_dir) },
	{ WLP_INTEGER, WLPF_NO_FLAGS, 
	  WLP_NO_RANGE(),
	  WLP_NO_DEFAULT(),
	  "created_files",
	  "Number of files that would be preliminary created",
	  offsetof(struct file_opener_workload, created_files) },
	{ WLP_INTEGER, WLPF_NO_FLAGS, 
	  WLP_NO_RANGE(),
	  WLP_NO_DEFAULT(),
	  "max_files",
	  "Maximum number of files",
	  offsetof(struct file_opener_workload, max_files) },
	{ WLP_INTEGER, WLPF_REQUEST, 
	  WLP_NO_RANGE(),
	  WLP_NO_DEFAULT(),
	  "file",
	  "ID of file",
	  offsetof(struct file_opener_request, file) },
	{ WLP_BOOL, WLPF_REQUEST,
	  WLP_NO_RANGE(),
	  WLP_NO_DEFAULT(),
	  "create",
	  "Set O_CREAT flag",
	  offsetof(struct file_opener_request, create) },

	{ WLP_NULL }
};

module_t* self = NULL;

static char* file_opener_path(char* path, size_t MAXLEN, const char* root_dir, int fid) {
	char fname[PATHPARTMAXLEN];

	snprintf(fname, PATHPARTMAXLEN, "file%d", abs(fid));

	return path_join(path, PATHMAXLEN, root_dir, fname, NULL);
}

static int file_opener_create_files(workload_t* wl,
								    struct file_opener_workload* fowl) {
	/* Create mask of preliminary created files and create files */
	int i;
	int fp;

	char path[PATHMAXLEN];

	/* Create some files */
	for(i = 0; i < fowl->created_files; ++i) {
		fp = creat(file_opener_path(path, PATHMAXLEN, fowl->root_dir, i), 0777);
		if(fp >= 0) {
			close(fp);
		}

		if((i % 50) == 0) {
			wl_notify(wl, WLS_CONFIGURING, (i * 100) / fowl->created_files,
					  "Created %d files so far", i);
		}
	}

	wl_notify(wl, WLS_CONFIGURING, 100, "Created all %d files", fowl->created_files);

	return 0;
}

static void file_opener_delete_files(struct file_opener_workload* fowl, int from, int to) {
	char path[PATHMAXLEN];

	while(from < to) {
		remove(file_opener_path(path, PATHMAXLEN, fowl->root_dir, from));
		++from;
	}
}

MODEXPORT int file_opener_wl_config(workload_t* wl) {
	struct file_opener_workload* fowl =
		(struct file_opener_workload*) wl->wl_params;
	int ret = 0;
	
	struct stat st;

	if(fowl->created_files > fowl->max_files) {
		wl_notify(wl, WLS_CFG_FAIL, 0, "Number of preliminary created files %lld is "
				"larger than maximum %lld", fowl->created_files, fowl->max_files);
		return -1;
	}

	if(stat(fowl->root_dir, &st) == -1) {
		wl_notify(wl, WLS_CFG_FAIL, 0, "Directory '%s' does not exists", fowl->root_dir);
		return -1;
	}

	if(!S_ISDIR(st.st_mode)) {
		wl_notify(wl, WLS_CFG_FAIL, 0, "'%s' is not a directory", fowl->root_dir);
		return -1;
	}

	return file_opener_create_files(wl, fowl);
}

MODEXPORT int file_opener_wl_unconfig(workload_t* wl) {
	struct file_opener_workload* fowl =
			(struct file_opener_workload*) wl->wl_params;

	/* Delete all files */
	file_opener_delete_files(fowl, 0, fowl->max_files);

	return 0;
}

MODEXPORT int file_opener_run_request(request_t* rq) {
	workload_t* wl = rq->rq_workload;
 	struct file_opener_workload* fowl =
		(struct file_opener_workload*) wl->wl_params;
	struct file_opener_request* forq =
		(struct file_opener_request*) rq->rq_params;
	int fp = -1;

	char path[PATHMAXLEN];
	file_opener_path(path, PATHMAXLEN, fowl->root_dir, forq->file % fowl->max_files);

	if(forq->create) {
		fp = creat(path, 0777);
	}
	else {
		fp = open(path, O_RDWR);
	}

	close(fp);

	return 0;
}

MODEXPORT int file_opener_step(workload_step_t* wls) {
	workload_t* wl = wls->wls_workload;
	struct file_opener_workload* fowl =
		(struct file_opener_workload*) wl->wl_params;
	
	/* Delete all files that are not pre-liminary created */
	file_opener_delete_files(fowl, fowl->created_files, fowl->max_files);

	return 0;
}
wl_type_t file_opener_wlt = {
	/* wlt_name */			AAS_CONST_STR("file_opener"),
	/* wlt_class */			WLC_FILESYSTEM_OP,
	
	"Benchmarks open() call for various cases: file not exists, "
	"existing file opened with O_CREAT, etc.",
	
	/* wlt_params */		file_opener_params,
						
	/* wlt_params_size*/	sizeof(struct file_opener_workload),
	/* wlt_rqparams_size*/	sizeof(struct file_opener_request),

	/* wlt_wl_config */		file_opener_wl_config,
	/* wlt_wl_unconfig */	file_opener_wl_unconfig,
	/* wlt_wl_step */		file_opener_step,
	/* wlt_run_request */	file_opener_run_request
};

MODEXPORT int mod_config(module_t* mod) {
	self = mod;

	wl_type_register(mod, &file_opener_wlt);

	return MOD_OK;
}

MODEXPORT int mod_unconfig(module_t* mod) {
	wl_type_unregister(mod, &file_opener_wlt);

	return MOD_OK;
}
