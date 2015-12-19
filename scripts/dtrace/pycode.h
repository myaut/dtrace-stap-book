#ifndef PY_CODE_H
#define PY_CODE_H

/**
 * This is forward definitions taken from Include/object.h and Include/code.h 
 * to support extraction of Python 3.4 interpreter state
 */

typedef long        ssize_t;

typedef struct _object {
    /* _PyObject_HEAD_EXTRA */
    ssize_t ob_refcnt;
    struct PyObject *ob_type;
} PyObject;

/* Bytecode object */
typedef struct _code {
    PyObject base;
    int co_argcount;        /* #arguments, except *args */
    int co_kwonlyargcount;  /* #keyword only arguments */
    int co_nlocals;         /* #local variables */
    int co_stacksize;       /* #entries needed for evaluation stack */
    int co_flags;           /* CO_..., see below */
    PyObject *co_code;      /* instruction opcodes */
    PyObject *co_consts;    /* list (constants used) */
    PyObject *co_names;     /* list of strings (names used) */
    PyObject *co_varnames;  /* tuple of strings (local variable names) */
    PyObject *co_freevars;  /* tuple of strings (free variable names) */
    PyObject *co_cellvars;      /* tuple of strings (cell variable names) */
    /* The rest doesn't count for hash or comparisons */
    unsigned char *co_cell2arg; /* Maps cell vars which are arguments. */
    PyObject *co_filename;  /* unicode (where it was loaded from) */
    PyObject *co_name;      /* unicode (name, for reference) */
    int co_firstlineno;     /* first source line number */
    PyObject *co_lnotab;    /* string (encoding addr<->lineno mapping) See
                   Objects/lnotab_notes.txt for details. */
    void *co_zombieframe;     /* for optimization only (see frameobject.c) */
    PyObject *co_weakreflist;   /* to support weakrefs to code objects */
} PyCodeObject;

/**
 * Compact ASCII object from Python3 -- data starts after PyUnicodeObject -- only if compact, ascii
 * and ready flags are set
 */
typedef struct _unicode {
    PyObject  base;
    ssize_t   length;
    ssize_t   hash;
    char      flags[4];
    void*     wstr;
} PyUnicodeObject;

#endif 