#!/usr/sbin/dtrace -qCs

#define VNODE_NAME(vp)                                 \
    (vp) ? ((vp)->v_path)                              \
         ? stringof((vp)->v_path) : "???" : "[ anon ]"

#define IS_SEG_VN(s)  (((struct seg*) s)->s_ops == &`segvn_ops)

fbt::as_fault:entry {
    self->in_fault = 1;
}
fbt::as_fault:return {
    self->in_fault = 0;
}

fbt::as_segat:return
/self->in_fault && arg1 == 0/ {
    @faults["???"] = count();
}

fbt::as_segat:return
/self->in_fault && arg1 != 0 && IS_SEG_VN(arg1)/ {
	this->seg = (struct seg*) arg1;
	this->seg_vn = (segvn_data_t*) this->seg->s_data;
	
	@faults[VNODE_NAME(this->seg_vn->vp)] = count();
}

tick-1s {
	printf("%8s %s\n", "FAULTS", "VNODE");
	printa("%@8u %s\n", @faults);
	trunc(@faults);
}