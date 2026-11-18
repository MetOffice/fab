Requirements doc for Transmute in FAB3
######################################

(A separate requirements document will be created for further Transmute Developments, QA and working practices)

Overview
^^^^^^^^

An extension of FAB3 to accommodate the PSyclone Transmute method by some means.
In LFRic Apps, long-term, eventually all optimisations (Such as OpenMP or compiler clauses) in source must be done through PSyclone.
Transmute currently describes using PSyclone without an API in LFRic Apps.
* Transmute uses base Psyclone functionality (No PSyclone API currently).
* It operates on Fortran files; science source and kernel files.

Technical Requirements:
^^^^^^^^^^^^^^^^^^^^^^^^

Transmute in Fab3 must maintain model runtime performance:
----------------------------------------------------------

* Executables built by FAB3 must be of comparable runtime performance to those built by make.
* Developers must have appropriately similar methods as the make system of controlling how source is optimised by FAB3 Transmute.

Transmute should operate in the build system like PSyclone PSyKAl where possible:
---------------------------------------------------------------------------------

* Fundamentally we are applying PSyclone over source
* Though it is not the same as PSyKAl, we are using PSyclone differently

Developers must be able to control whether to Transmute a Fortran Source file:
------------------------------------------------------------------------------

* In LFRic Apps, long-term, eventually all hand coded optimisations (Such as OpenMP or compiler clauses) in Fortran source must be done through PSyclone.

	* However, there will be edge cases, and so not every file will want to go through PSyclone. 
	* We will describe this as the Opt-Out method as still.

* In the immediate term, the MetOffice will want to more explicit control over which files have Transmute applied.

	* MO has reasonable LFRic runtime performance from OpenMP coverage by Transmute currently with make with a specific list of files.
	* These scripts are currently fragile with better QA required (and actioned in its own requirements)
	* We will describe this as Opt-In method.

* Opt-In will be the default at the MetOffice for the immediate term.
* External partners want Opt-Out, especially for GPU porting.

	* Therefore, partners must be able to choose for their site.

* When our working-practices, QA, and script coverage improve sufficiently, MO will move to Opt-Out.

Developers must be able to control how they use Transmute on Fortran Source:
--------------------------------------------------------------------------------

* PSyclone uses passed in python Transformation scripts to alter the input Fortran file
* These Transformation scripts are written in a specific way
* Transformation scripts may be written bespoke for a specific Fortran file.
* Transformation scripts may be written generically for multiple Fortran files.
* The selection of an transformation script to apply to Fortran Source must be configurable for the Transmute build Step.
* It must be possible to define the transformation script to use for each Fortran file
* This can be done in python, or with YAML files or another appropriate method.
* A entry in the configuration must resolve to a Transformation Script for a Fortran File.

For the usage of Transmute scripts, FAB3 must interface with the existing separations of concerns LFRic Apps such as:
----------------------------------------------------------------------------------------------------------------------------------

* <application>
* <PSyclone-method>
* <architecture> 
* These define the initial storage locations in the repository.
* This must be an extensible list of corresponding folder stores as all above options may be extended.
* Transmute script usage must be configurable by different partner sites. This informs which <architecture> folder to use.
* Current <architecture> options include:

	* Minimum
	* CPU
	* Extensible for GPU option
	* Extensible for further subsets of CPU/GPU options.

* The folder structure under <application>/optimisation/<PSyclone-method>/<architecture>/ may be extended by LFRic developers to further organise scripts.

Configuration properties of the Transmute build step must be able to be externally overwritten from cylc.
--------------------------------------------------------------------------------------------------------------

The Psyclone step must be able to run in Parallel
--------------------------------------------------

* For Spice, we need to avoid importing the Python libraries too many times as it adversely affects the file system. 
* The make build system uses a python tool to handle this step with farmer and worker threads.

Transmute uses the PSyclone command, which has a number of command line options:
----------------------------------------------------------------------------------

* These are -l all, -s $(OPTIMISATION_PATH_PSY)/$(DSL)/$*.py, -o $(SOURCE_DIR)/$*.f90, INPUTFILE
* Some the flags in the command should be extensible
* Existing flags such as -l all must be configurable per Fortran input file.

It must have PYTHONPATHs setup for the PSyclone command so that it can use the appropriate Transformation script and it's imports, including:
--------------------------------------------------------------------------------------------------------------------------------------------

* The PSyclone build from the loaded environment
* The python library is stored at: interfaces/build/transmute_psytrans
* The transformation scripts and their imports are stored at: <application>/optimisation/<PSyclone-method>/<architecture>


Functional Requirements:
^^^^^^^^^^^^^^^^^^^^^^^^

The Transmute Psyclone build step in FAB3:
===================================================

It must be possible to generate a PSyclone Transmute action for little .f90 source files.
----------------------------------------------------------------------------------------------------

It must be possible to generate a PSyclone Transmute action for big .F90 files after they are pre-processed to become "little .f90" files.
------------------------------------------------------------------------------------------------------------------------------------------------------

* This takes the .f90 file and applies PSyclone to it without the PSyKAl API.

It must have the Fortran file dependencies also pre-processed.
-------------------------------------------------------------

* Psyclone needs this to confirm some external variables are safe to Transform.
* Compiler defined macros for these files must be adhered too.

The FAB configuration must allow the user to configure whether a Fortran file generates it's respective Transmute build step action:
-------------------------------------------------------------------------------------------------------------------------------------

* By source tree, specified by root directory.
* Also, by simple glob.
* Not every file needs a Transmute Action, governed by Opt-In/Out list(s).
* Opt-In/Out list(s) must be configurable by <application>, <PSyclone-method> and <architecture>.
* Sites must have configurable control over <architecture> defined lists.

The FAB configuration must be able to inform the transmute build step of:
---------------------------------------------------------------------------

* <architecture>
* Opt-In/Out
* These must be overridable by appropriate settings in cylc.

Variables set in cylc must be available to inform the Transmute step.
--------------------------------------------------------------------

* <architecture> must be controllable by sites in cylc, this will override the configuration.
* Opt-In/Out must be controllable by sites in cylc, this will override the configuration.

It must be configurable as to which transformation script will be applied to the Fortran file (see the transformation script configuration in FAB3).
-------------------------------------------------------------------------------------------------------------------------------------------------

The Psyclone command must have sensible default flags configured, denoted earlier.
----------------------------------------------------------------------------------

* These flags need to be configurable per Fortran file.

	* From a specific list, Opt-In.
	* From a wildcard glob of the source code, Opt-Out.

It must resolve appropriate PYTHONPATHs for PSyclone.
------------------------------------------------------

* These must point to the root directory of the scripts, as defined by the FAB configuration: <application>/optimisation/<PSyclone-method>/<architecture>.
* It must also point to the appropriate Transmute python function library root.

	Currently in LFRic Apps this is: ``interfaces/build/transmute_psytrans``

It must preserve current ordering of Transmute and PSyKAl steps from the make system:
-------------------------------------------------------------------------------------

* Currently Transmute occurs after PSyKAl to preserve kernel metadata comments for the PSyKAl PSyclone step.
* In the working practices we currently do not allow a developer to Transmute in-lined source.

	* It's not unsafe to do so, just redundant.
	* PSyKAl PSyclone developers in-lining source which has a Transmute script should be aware and resolve this.


Future Considerations for the FAB3 Transmute build Step:
========================================================

Currently there is no interaction between Transmute and PSyKAl steps for kernels.
---------------------------------------------------------------------------------

* Currently a Fortran source file should only be passed to Transmute if it is not in-lined by the algorithm.

We could allow reversal of build steps, PSyKAl after Transmute step for Kernels
-----------------------------------------------------------------------------

* Would require preservation of comments in Transmute step.
* Would allow inlining of Transmuted kernels.
* Would require preservation of clauses generated by Transmute in PSyKAl step.
* Would introduce additional calls to PSyclone, when Transmute behaviour could be done to the in-lined source in the PSYKAL step.

Transmute and PSyKAl are distinct build actions, could re-combine if optimal.
-----------------------------------------------------------------------------

* For the parallel PSyclone step, the build may be more performant if we combined these.
* However, these were only separated for:

	* Ease of initial build system integration:

		* Given differing file extensions and source (x90 or f90).
		* Given differing PSyclone APIs.
		* Given differing Transformation requirements.

	* Ease of Developer usage:

		* They are fundamentally different approaches to transforming source using PSyclone, this consideration needs preserving.

Architecture set to Minimum for Transmute needs further exploring as a potential build optimisation
-----------------------------------------------------------------------

* Minimum for PSyKAl is to apply very basic PSyclone features to algorithms.
* Principle should extend to Transmutable source.
* Most source will not need to be Transmuted, if hand coded opts are cleaned from existing source.
* If minimum is selected, we need to identify if a Transmute Action is actually required:

	* The lack of an transformation script for an existing pair match from the configuration could be used as an indicator that we don't need an action.
	* Without a global script at all to fall back on, the Transmute step otherwise resolves without calling Psyclone.
	* Possibly Transmute is not required at all with Minimum.


The transformation script configuration in FAB3:
================================================

It must allow the user to choose which transformation script is applied to a specific Fortran File.
---------------------------------------------------------------------------------------------------

The interpretation of a configuration option must use glob (or a similar method) to resolve to an appropriate transformation script from the configuration file.
------------------------------------------------------------------------------------------------------------------------------------------------

If no script is defined in the configuration for a Fortran File to be transmuted, it must resolve to the appropriate default script.
---------------------------------------------------------------------------------------------------------------------------------

The default script must be a global.py.
---------------------------------------

In LFRic Apps, the global.py will be stored by application, by PSyclone method and by <architecture> method.
------------------------------------------------------------------------------------------------------

* FAB3 must resolve this default without the configuration.
* This will look like: <application>/optimisation/<PSyclone-method>/<architecture>.
* Sites must be able to control the <architecture> method in cylc. The FAB3 configuration must understand this.

It must allow multiple Fortran files to be matched to a single transformation script, wildcarding part of a file or directory name.
----------------------------------------------------------------------------------------------------------------------------------

* This replaces the existing make local.py method.

It must be able to select the right transformation script if multiple options are provided in a configuration, following a set hierarchy of priority.
---------------------------------------------------------------------------------------------------------------------------------------------------

* Only one script can be chosen
* Developers can add multiple similar entires to allow matching multiple files to a script based on shared naming conventions or directories.
* FAB must compare the relative resolved glob for the Fortran file against those generated per option of the configuration.

There is a hierarchy of priority for pair matching scripts to Fortran files, which will supersede the default.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

* An exact filename match.
* A filename wildcard match.
* A broader path or directory match.
* If no configured selector matches, use the default ``global.py`` script.

For example, for ``super_work/myfile.f90``:
* ``*/myfile`` - an exact filename match
* ``*/my*`` - A filename wildcard match.
* ``super_work*`` - A broader path or directory match.
Use ``global.py`` only if none of the configured selectors are present or match.

To reduce script duplication, transformation scripts must still be able to:
----------------------------------------------------------------------------

* Import other Python functions from a library like the PSyclone PSyKAl method does.

	* This import must point to the root of an extensible library of python functions.

* Must allow parameterised transformations for common functionality.

	* It must accept variables such as an ignore_dependencies_for.
	* These should be tuneable in the Transmute configuration method.
	* These should also be able to then be obscured away by an import as they may contain a long list of variables.
	* These variables must be usable in script to tune the Transformations.
	* It must be an extensible list, allowing developers to add additional properties, and resolve them in the transformation script.
	* It should not be used to control major forking pathways in scripts; users should be encouraged to write a bespoke script.

Developers must be able to choose flags for the PSyclone command per Fortran file:
----------------------------------------------------------------------------------

* We must have sensible defaults configured by the build step action.
* To define in the configuration which additional flags we want to use per file.

	* Such as --keep-comments / --keep-directives, key to early script concretisation.

* To define in the configuration alternative flag options from the default.
* This can be its own configuration or combined with the transformation script configuration.

Further developments/consideration to the script selection configuration:
=========================================================================

Which default global.py (stored by application, by PSyclone method and by architecture method), is selected by the configuration.
----------------------------------------------------------------------------------------------------------------------------------

* The default methodology could be expanded.

	* A configurable default for <architecture> could be available.
	* If no global or override exists for a file where selected in the resolved <application>/optimisation/<PSyclone-method>/<architecture> directory, it fall back to the provided <architecture> too.
	* This would further reduce duplication overhead, especially for architecture overrides.

We should still store PSyKAl and Transmute scripts separately in LFRic.
------------------------------------------------------------------------

* We are transforming the source differently, using different APIs.
* This provides cleaner separation of concerns for users and developers.
* There might be future overlap between function libraries.

	* No occurrence of cross Transmute PSyKAl usage yet, until we start actively in-lining source.
