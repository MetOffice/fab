Features
********

Dynamic Source Tree Detection
=============================
coming soon

Incremental Build
=================
coming soon

Prebuilds
=========
coming soon


Limitations
===========

Dependency detection
--------------------
Whilst fab can automatically determine dependencies from module use statements,
and from standalone call statements, it doesn't currently detect a dependency from a call statement
on a single-line if statement. We can pass the analyser any dependencies which Fab can't detect,
and they'll make their way through to the link stage.