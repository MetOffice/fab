
#pragma FAB SysIncludeStart
//#include <stdio.h>
extern int printf (const char *__restrict __format, ...);
int sys_var;                    // external linkage, not a definition
int sys_func(void);             // external linkage, not a definition
#pragma FAB SysIncludeEnd


#pragma FAB UsrIncludeStart
int usr_var;                    // external linkage, not a definition
int usr_func(void);             // external linkage, not a definition
#pragma FAB UsrIncludeEnd


int var_decl;                   // external linkage, not a definition
static int var_static_decl;     // internal linkage, not a definition
extern int var_extern_decl;     // external linkage, not a definition

int var_def = 1;                // external linkage, is a definition
static int var_static_def = 1;  // internal linkage, is a definition
extern int var_extern_def = 1;  // external linkage, is a definition


int func_decl();                // external linkage, not a definition
static int func_static_decl();  // internal linkage, not a definition
extern int func_extern_decl();  // external linkage, not a definition

int func_def() {                // external linkage, is a definition
    return 1;
}

static int func_static_def() {  // internal linkage, is a definition
    return 1;
}


void main(void) {               // external linkage, is a definition

   // must
    var_static_decl = 1;        // invalid linkage, not a definition

    // explore
    usr_var = 1;
    var_decl = 1;
    var_extern_decl = 1;
    var_def = 1;
    var_extern_def = 1;


    printf("%i\n",
        sys_var + sys_func() +
        usr_var + usr_func() +
        var_decl + var_static_decl + var_extern_decl +
        var_def + var_static_def +
        func_decl() + func_static_decl() + func_extern_decl() +
        func_def() + func_static_def()
    );
}

int func_decl() {               // external linkage, is a definition
    return 1;
}

static int func_static_decl() { // internal linkage, is a definition
    return 1;
}
