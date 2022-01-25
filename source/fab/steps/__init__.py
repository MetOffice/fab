import multiprocessing


class Step(object):
    """


    """
    # We sometimes need to turn multiprocessing off when debugging a build.
    use_multiprocessing = True
    n_procs = 1

    def __init__(self, name):
        self.name = name

    def run(self, artefacts):
        raise NotImplementedError

    def run_mp(self, artefacts, func):
        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(func, artefacts)
        else:
            results = [func(f) for f in artefacts]

        return results



# def exrun(artefacts):
#     input = artefacts["all_source"][".c"]
#     results = run_mp()
#     artefacts["i made this"] = results





# class MPMapStep(Step):
#     """
#     Base class for Steps which use multiprocessing.map.
#
#     i.e A process to be run on a single file from a list of files.
#
#     """
#
#     def __init__(self, name, n_procs):
#         super().__init__(name)
#         self.n_procs = n_procs
#
#     def input_artefacts(self, artefacts):
#         raise NotImplementedError
#
#     def process_artefact(self, artefact):
#         raise NotImplementedError
#
#     def output_artefacts(self, results, artefacts):
#         raise NotImplementedError
#
#     def run(self, artefacts):
#         if self.use_multiprocessing:
#             with multiprocessing.Pool(self.n_procs) as p:
#                 results = p.map(self.process_artefact, self.input_artefacts(artefacts))
#         else:
#             results = [self.process_artefact(f) for f in self.input_artefacts(artefacts)]
#
#         self.output_artefacts(results, artefacts)


#
# EXAMPLE OF A STEP SUBCLASS
#
# class ExampleStep(Step):
#
#     def __init__(self, name):
#         super().__init__(name)
#
#     def input_artefacts(self, artefacts):
#         return artefacts["stuff i want"]
#
#     def process_artefact(self, artefact):
#         return "foo/output.f90"
#
#     def output_artefacts(self, results, artefacts):
#         artefacts["stuff i made"] = [NewThing(r) for r in results]
