# Site-specific setup

This directory contains a simple template for a site-specific setup
of compilers. The Fab base class will look in this directory for
a configuration class, which the Fab baselclass will instantiate
and issue callbacks. See documentation for more details.

At the moment there is just one 'site': ``default``, which is the name
used when no site or platform is specified on the command line.

## TODO

TODO: it's not yet clear if this directory should stay here or go
elsewhere, e.g. documentation, or ...
