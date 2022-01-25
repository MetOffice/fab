import multiprocessing


class Step(object):

    def __init__(self, name):
        self.name = name

    def run(self, artefacts):
        raise NotImplementedError


class MPStep(Step):

    # We sometimes need to turn multiprocessing off when debugging a build.
    use_multiprocessing = True

    def __init__(self, name, n_procs):
        super().__init__(name)
        self.n_procs = n_procs

    def input_artefacts(self, artefacts):
        raise NotImplementedError

    def process_artefact(self, artefact):
        raise NotImplementedError

    def output_artefacts(self, results, artefacts):
        raise NotImplementedError

    def run(self, artefacts):
        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(self.process_artefact, self.input_artefacts(artefacts))
        else:
            results = [self.process_artefact(f) for f in self.input_artefacts(artefacts)]

        self.output_artefacts(results, artefacts)


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
