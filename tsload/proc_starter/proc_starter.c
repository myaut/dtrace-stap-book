#define LOG_SOURCE "proc_starter"
#include <tsload/log.h>

#include <tsload/defs.h>

#include <tsload/mempool.h>
#include <tsload/modapi.h>
#include <tsload/autostring.h>

#include <tsload/plat/posixdecl.h>

#include <tsload/load/workload.h>
#include <tsload/load/wltype.h>

#include <proc_starter.h>
#include <shell.h>

#include <stdlib.h>

DECLARE_MODAPI_VERSION(MOD_API_VERSION);
DECLARE_MOD_NAME("proc_starter");
DECLARE_MOD_TYPE(MOD_TSLOAD);

#if defined(PLAT_LINUX) || defined(PLAT_SOLARIS)
#define SHELL_PATH "/usr/bin/sh"
#else
#define SHELL_PATH ""
#error "Cannot build proc_starter for your platfrom"
#endif

#define PROMPT "[shell-a277c062-9bff-11e4-9b0b-c4850831c67b] "

MODEXPORT wlp_descr_t proc_starter_params[] = {
	{ WLP_INTEGER, WLPF_NO_FLAGS, 
	  WLP_INT_RANGE(1, 1000),
	  WLP_NO_DEFAULT(),
	  "num_shells",
	  "Number of pre-forked shells. It is recommended to set this value to number of threads in threadpool.",
	  offsetof(struct proc_starter_workload, num_shells) },
	{ WLP_RAW_STRING, WLPF_OPTIONAL, 
	  WLP_STRING_LENGTH(1024),
	  WLP_STRING_DEFAULT( SHELL_PATH ),
	  "shell",
	  "Path to pre-forked shell",
	  offsetof(struct proc_starter_workload, shell) },
	{ WLP_RAW_STRING, WLPF_REQUEST, 
	  WLP_STRING_LENGTH(512),
	  WLP_NO_DEFAULT(),
	  "command",
	  "Command to be executed in request",
	  offsetof(struct proc_starter_request, command) },

	{ WLP_NULL }
};

module_t* self = NULL;

MODEXPORT int proc_starter_wl_config(workload_t* wl) {
	struct proc_starter_workload* pswl =
		(struct proc_starter_workload*) wl->wl_params;
	struct proc_starter_data* psdata = NULL;
	int shid;

	ps_shell_t* sh;
	
	char* argv[] = { pswl->shell, NULL };
	char* envp[] = {
		"PS1=" PROMPT,
		"PS2=" PROMPT,
		NULL
	};

	psdata = (struct proc_starter_data*) mp_malloc(sizeof(struct proc_starter_data));
	
	if(psdata == NULL) {
		wl_notify(wl, WLS_CFG_FAIL, 0, "Cannot allocate data structure");
		return -1;
	}

	squeue_init(&psdata->sq, "procstart-%s", wl->wl_name);

	wl->wl_private = psdata;

	for(shid = 0; shid < pswl->num_shells; ++shid) {
		sh = sh_create(pswl->shell, argv, envp);

		if(sh == NULL) {
			wl_notify(wl, WLS_CFG_FAIL, 0, "Cannot spawn shell #%d", shid);
			return -1;
		}

		if((shid % 10) == 0) {
			wl_notify(wl, WLS_CONFIGURING, (shid * 100) / pswl->num_shells,
					  "Spawned %d shells so far", shid);
		}

		/* Wait for first prompt */
		sh_expect(sh, PROMPT);

		squeue_push(&psdata->sq, sh);
	}

	wl_notify(wl, WLS_CONFIGURING, 100, "Spawned all %d shells", pswl->num_shells);

	return 0;
}

static void sh_free(void* obj) {
	sh_destroy((ps_shell_t*) obj);
}

MODEXPORT int proc_starter_wl_unconfig(workload_t* wl) {
	struct proc_starter_data* psdata =
		(struct proc_starter_data*) wl->wl_private;
	int shid;

	if(psdata) {
		squeue_destroy(&psdata->sq, sh_free);
		mp_free(psdata);
	}

	return 0;
}

MODEXPORT int proc_starter_run_request(request_t* rq) {
	workload_t* wl = rq->rq_workload;
	struct proc_starter_data* psdata =
		(struct proc_starter_data*) wl->wl_private;
	struct proc_starter_request* psrq =
		(struct proc_starter_request*) rq->rq_params;
	
	ps_shell_t* shell = squeue_pop(&psdata->sq);

	write(shell->sh_pty, psrq->command, strlen(psrq->command));
	write(shell->sh_pty, "\n", 1);

	sh_expect(shell, PROMPT);

	squeue_push(&psdata->sq, shell);

	return 0;
}

wl_type_t proc_starter_wlt = {
	/* wlt_name */			AAS_CONST_STR("proc_starter"),
	/* wlt_class */			WLC_OS_BENCHMARK,
	
	"Runs shell and sends commands to it with expect-like submodule.",
	
	/* wlt_params */		proc_starter_params,
						
	/* wlt_params_size*/	sizeof(struct proc_starter_workload),
	/* wlt_rqparams_size*/	sizeof(struct proc_starter_request),

	/* wlt_wl_config */		proc_starter_wl_config,
	/* wlt_wl_unconfig */	proc_starter_wl_unconfig,
	/* wlt_wl_step */		NULL,
	/* wlt_run_request */	proc_starter_run_request
};

MODEXPORT int mod_config(module_t* mod) {
	self = mod;
	wl_type_register(mod, &proc_starter_wlt);

	return MOD_OK;
}

MODEXPORT int mod_unconfig(module_t* mod) {
	wl_type_unregister(mod, &proc_starter_wlt);

	return MOD_OK;
}
