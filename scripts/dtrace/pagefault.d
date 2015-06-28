#!/usr/sbin/dtrace -qCs

/**
 * pagefault.d
 * 
 * Traces page faults which are handled by as_fault()
 * 
 * Tested on Solaris 11
 */

string fault_type[4];
string seg_rw_type[6];
string prot[8];

#define DUMP_AS_FAULT()                                 \
    printf("as_fault pid: %d as: %p\n", pid, self->as); \
    printf("\taddr: %p size: %d flags: %s|%s \n",       \
        self->addr, self->size,                         \
        fault_type[self->pf_type],                      \
        seg_rw_type[self->pf_rw]                        \
    )

#define PROT(p) prot[(p) & 0x7],                        \
                   ((p) & 0x8) ? "u" : "-"
    
#define VNODE_NAME(vp)  (vp)                            \
                        ? ((vp)->v_path)                \
                            ? stringof((vp)->v_path)    \
                            : "???"                     \
                        : "[ anon ]"                     
    
#define DUMP_SEG_VN(seg, seg_vn)                        \
    printf("\t[%p:%p] %s%s\n\tvn: %s\n\tamp: %p:%d \n", \
        (seg)->s_base, (seg)->s_base + (seg)->s_size,   \
        PROT((seg_vn)->prot), VNODE_NAME((seg_vn)->vp), \
        (seg_vn)->amp, (seg_vn)->anon_index             \
    )

#define IS_SEG_VN(s)  (((struct seg*) s)->s_ops == &`segvn_ops)

BEGIN {
    /* See vm/seg_enum.h */
    fault_type[0] = "F_INVAL";          fault_type[1] = "F_PROT";
    fault_type[2] = "F_SOFTLOCK";       fault_type[3] = "F_SOFTUNLOCK";
    
    seg_rw_type[0] = "S_OTHER";         seg_rw_type[1] = "S_READ";
    seg_rw_type[2] = "S_WRITE";         seg_rw_type[3] = "S_EXEC";
    seg_rw_type[4] = "S_CREATE";        seg_rw_type[5] = "S_READ_NOCOW";
    
    prot[0] = "---";                    prot[1] = "r--";
    prot[2] = "-w-";                    prot[3] = "rw-";
    prot[4] = "--x";                    prot[5] = "r-x";
    prot[6] = "-wx";                    prot[7] = "rwx";    
}
    
fbt::as_fault:entry {
    self->in_fault = 1;
    
    self->as      = args[1];
    self->addr    = args[2];
    self->size    = args[3];    
    
    self->pf_type = args[4];
    self->pf_rw   = args[5];
}

fbt::as_fault:return
{
    self->in_fault = 0;
}

fbt::as_segat:return
/self->in_fault && arg1 == 0/
{
    DUMP_AS_FAULT();
}

fbt::as_segat:return
/self->in_fault && arg1 != 0 && IS_SEG_VN(arg1)/
{
    this->seg = (struct seg*) arg1;
    this->seg_vn = (segvn_data_t*) this->seg->s_data;
    
    DUMP_AS_FAULT();
    DUMP_SEG_VN(this->seg, this->seg_vn);
}
