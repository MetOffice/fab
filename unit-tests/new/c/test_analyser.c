
#pragma FAB SysIncludeStart
//#include <stdio.h>
void func printf(char* f, int a);
int sys_var;
int sys_func(void);
#pragma FAB SysIncludeEnd


#pragma FAB UsrIncludeStart
int usr_var;
int usr_func(void);
#pragma FAB UsrIncludeEnd


int var_decl;
static int var_static_decl;
extern int var_extern_decl; //

int var_def = 1;
static int var_static_def = 1;


int func_decl(); //
static int func_static_decl(); //
extern int func_extern_decl();

int func_def() {
    return 1;
}

static int func_static_def() {
    return 1;
}


void main(void) {

    var_static_decl = 1;


    printf("%i\n",
        sys_var + sys_func() +
        usr_var + usr_func() +
        var_decl + var_static_decl + var_extern_decl +
        var_def + var_static_def +
        func_decl() + func_static_decl() + func_extern_decl() +
        func_def() + func_static_def()
    );
}

int func_decl() {
    return 1;
}

static int func_static_decl() {
    return 1;
}
