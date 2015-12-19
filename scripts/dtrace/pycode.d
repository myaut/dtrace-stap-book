#!/usr/sbin/dtrace -Cs

#include "pycode.h"

#define GET_Py3_STRING(obj) (((PyUnicodeObject*) copyin((uintptr_t) obj,                     \
                                           sizeof(PyUnicodeObject)))->flags[0] & 0xE0)       \
            ? copyinstr(((uintptr_t) obj) + sizeof(PyUnicodeObject)) : "<???>"   

foo$target::: {}

pid$target::PyEval_EvalCodeEx:entry {
    self->co = (PyCodeObject*) copyin(arg0, sizeof(PyCodeObject));

    trace(GET_Py3_STRING(self->co->co_filename));
    trace(GET_Py3_STRING(self->co->co_name));
    trace(self->co->co_firstlineno);
}