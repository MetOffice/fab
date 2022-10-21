Glossary
********

.. glossary::

    Step
        A build step which typically reads from, and adds to, an in-memory :term:`Artefact` repository called
        the :term:`Artefact Store`. Steps are derived from the :class:`~fab.steps.Step` base class.

    Artefact Store
        At the start of a build run, Fab creates an empty ``artefact_store``.
        An entry in this store is called an :term:`Artefact Collection`, which is a mapping from a name string
        to, usually, a collection of :term:`Artefact` - but can be anything.

        Fab passes the growing artefact store to each step in turn,
        where they typically read a :term:`Artefact Collection` and create a new one for subsequent steps to read.

        See also :ref:`Artefacts Overview <artefacts_overview>`

    Artefact Collection
        A collection of :term:`Artefact` in the :term:`Artefact Store`.

        These entries are usually a list of file paths or objects, or a :term:`Source Tree`,
        but could be anything created by one step and consumed by another.

        As an example, a Fortran preprocessing step might create a list of output paths
        as ``artefact_store['preprocessed fortran'] = my_results``.
        A subsequent step could read this list.

    Artefact
        *Artefact* is a term for an item, usually a file,
        created by a build step and added to the :term:`Artefact Store`.

        Some examples of artefacts are:
         - a Fortran file
         - a compiled object file
         - an executable file

        These exist as files in the file system and paths in the artefact store.

    Artefacts Getter
        A helper class which a :term:`Step` uses to get artefacts from the :term:`Artefact Store`.
        Fab's built-in steps come with sensible defaults so the user doesn't have to write unnecessary config.

        As an example, the Fortran preprocessor has a default artefact getter which reads *".F90"* files
        from the :term:`Artefact Collection` called _"all_source"_.

        Artefact getters are derived from :class:`~fab.artefacts.ArtefactsGetter`.

    Source Tree
        The :class:`~fab.steps.analyse.Analyse` step produces a dependency tree of the entire project source.
        This is represented as a mapping from Path to :class:`~fab.dep_tree.AnalysedFile`.
        The tree structure is defined as the AnalysedFiles' file dependencies are Paths, i.e other entries in the tree.

        When building executables, a sub-tree is extracted from the :term:`Source Tree`, for each executable
        we want to build. Each build tree contains only the files needed to build that target.
        When building a library, all source code is included in a single build tree.

        Fab's source code uses the term *source tree* for everything that's been analysed,
        and *build trees* for sub-trees extracted for each target exe.

    Fab Workspace
        The folder in which all Fab output is created. Defaults to *~/fab-workspace*, and can be overridden
        by the *FAB_WORKSPACE* environment variable or the `fab_workspace` argument to the
        :class:`~fab.build_config.BuildConfig` constructor.

    Project Workspace
        A folder inside the fab workspace, containing all output from (typically) a single build config.

    Incremental Build
        This term refers to Fab's ability to avoid reprocessing an artefact if the output is already available.
        For example, if the user has previously built the project, there will likely be object files Fab can use
        to avoid recompilation.

    Prebuild
        This term has much overlap with the term :term:`Incremental Build`. It refers to artefacts that were built by
        another user, which can be copied to avoid reprocessing artefacts.
        Technical details on how this works can be found in :ref:`development:Incremental & Prebuilds`.
