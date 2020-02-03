import os
import re
import subprocess
from glob import glob

import luigi

# Let's define the relationships between the source files here. In practice
# this information would come from Fab, perhaps it would be stored in
# something like a sqlite database or similar
DEPENDENCIES = {
    "test_exec":
        ["ex_main.f90", ],
    "ex_main.f90":
        ["ex.f90", ],
    }

# Similarly another database that gives us information about how to compile
# each given source. This would likely be more complicated in a final version
# of Fab; the compiler may be represented as a class or something else
COMPILERS = {
    "test_exec": ["ifort", ],
    "ex_main.f90": ["ifort", "-c"],
    "ex.f90": ["ifort", "-c"],
    }


# This is a Luigi "task" which aims to produce Fortran build objects from
# source (in Fab terminology this would be a Transform that does a compilation)
class CompileFortran(luigi.Task):

    # These "parameters" acts as constructor arguments for the task (similar
    # to an __init__ method) but are also used to form the unique signature
    # of the task for Luigi's internals; as such we use the path to the source
    # file. It seems possible for this to be multiple source files to cover
    # other cases we identified in our requirements
    source = luigi.Parameter()

    # The requires method returns a list of other Tasks which this one
    # depends on, so we pull this information from one of our "databases"
    def requires(self):
        if self.source in DEPENDENCIES:
            return [CompileFortran(dependency)
                    for dependency in DEPENDENCIES[self.source]]

    # The output method returns a list of "targets" (artifacts/products in Fab)
    # and Luigi will check to make sure these have been created
    def output(self):
        # Being Fortran, we need to get the name of the contained module; as
        # the produced files will be based on it (not the source filename)
        module_names = None
        with open(self.source, "r") as source:
            lines = source.read()
            module_names = re.findall(r"\Wmodule\s+{w+}\W", lines)

        # Define the object file as the first target
        targets = [luigi.LocalTarget(re.sub(r".f90$", ".o",  self.source)), ]

        # And define the .mod file as the second one (if the file contains a
        # module!)
        if module_names is not None:
            for mod_name in module_names:
                targets.append(luigi.LocalTarget(
                    os.path.join(
                        os.path.dirname(self.source), mod_name + ".mod")))

        return targets

    # Finally this part defines what should be run to perform the compilation.
    # So we look up the command to use from the other "database"
    def run(self):
        compiler_command = COMPILERS[self.source]
        subprocess.check_call(compiler_command + [self.source, ])


# Next we define a second task which deals with the linking
class LinkFortran(luigi.Task):

    # The linking step doesn't really correspond to a singular file source
    # like the compilation step does, but it still has an entry in the
    # dictionaries/databases so the name needs to be given
    source = luigi.Parameter()
    # Also specify the name of the exec to build
    exec_name = luigi.Parameter()

    # The requires method is the same as the compile step (look up in database)
    def requires(self):
        if self.source in DEPENDENCIES:
            return [CompileFortran(dependency)
                    for dependency in DEPENDENCIES[self.source]]

    # The output/target is the executable
    def output(self):
        return luigi.LocalTarget(self.exec_name)

    # Making a few assumptions here - that all compilers support the "-o name"
    # syntax for specifying the exec... we're also blindly just grabbing
    # all object files for the linking, which will do for now but would need
    # a lot of further work
    def run(self):
        compiler_command = COMPILERS[self.source]
        subprocess.check_call(compiler_command
                              + glob("*.o")
                              + ["-o", self.exec_name])


if __name__ == "__main__":

    # Now we can put together the DAG itself - 2 compile steps and a link
    build_manifest = [
        LinkFortran("test_exec", "test_exec.exe"),
        CompileFortran("ex_main.f90"),
        CompileFortran("ex.f90"),
        ]

    # and execute it...
    luigi.build(
        build_manifest,
        local_scheduler=True)
