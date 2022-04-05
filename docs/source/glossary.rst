********
Glossary
********

.. glossary::

    Step
        A build step which typically reads from, and adds to, an in-memory :term:`Artefact` repository called
        the :term:`Artefact Store`. All steps are derived from the :class:`~fab.steps.Step` base class.

    Artefact Store
        At the start of a build run, Fab creates an empty dict called ``artefact_store``. Each step can read and write
        to this dict. An entry in this dict is called a :term:`Named Collection`, which maps a name string
        to, usually, a list or dict of :term:`Artefact` - but can be anything.

        Fab passes the growing artefacts store to each step in turn,
        where they typically read a :term:`Named Collection` and create a new one for subsequent steps to read.

        See also :ref:`Artefacts Overview <artefacts_overview>`

    Named Collection
        *Named collection* is a term for a collection of :term:`Artefact` in the :term:`Artefact Store`.

        These entries are usually a list of file paths or objects, or a :term:`Source Tree` dict,
        but could be anything created by one step and consumed by another.

        As an example, a Fortran preprocessing step might create a list of output paths
        as ``artefact_store['preprocessed fortran'] = my_results``.
        A subsequent step could read this list.

    Artefact
        *Artefact* is a term for any file created by a build step and added to the :term:`Artefact Store`.

        Some examples of artefacts are:
         - a Fortran file
         - a compiled object file
         - an executable file

        Some steps may create additional files which are not currently represented or tracked by Fab,
        such as the *.mod* files created by the Fortran preprocessor - although this particular case is under review.

    Artefact Getter
        A helper class which tells a build step which files to read. Fab's built-in steps come with
        sensible defaults so the user doesn't have to write unnecessary config.

        As an example, the Fortran preprocessor has a default artefact getter which reads *".F90"* files
        from the :term:`Named Collection` called _"all_source"_.

        All artefact getters are derived from :class:`~fab.artefacts.ArtefactGetterBase`.

    Source Tree
        Some steps produce a source tree which is implemented as a flat dict mapping from Path to
        :class:`~fab.dep_tree.AnalysedFile`.
        The tree's structure is defined by the nodes (values) referring to other paths (keys) in the dict.

        When building an executable, a sub-tree is extracted containing only the files needed to build the target
        program. When building a library, all compiled source code is included in the output.
