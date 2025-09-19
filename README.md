# Fab - A Build System for Tomorrow

[![Build](https://github.com/MetOffice/fab/actions/workflows/build.yml/badge.svg)](https://github.com/MetOffice/fab/actions/workflows/build.yml)
[![Build Documentation](https://github.com/MetOffice/fab/actions/workflows/documentation.yml/badge.svg)](https://github.com/MetOffice/fab/actions/workflows/documentation.yml)

The "Fab" project aims to provide the means to quickly and easily compile
software in a way tailored for scientific software development. It aims to be
quick both in terms of use and operation. Meanwhile ease should mean the
simple things are simple and the complicated things are possible.

Fab is not intended to replace existing tools for compiling general
application software. It targets different problems to, for instance, CMake
derived build systems. This means that if your usage falls outside the focus
of development you shouldn't expect high priority on your feature requests.

## Licence

The software is made available under a 3-clause BSD licence.

## Installation

The tool is easily installed using `pip install sci-fab`.

## Usage

Fab offers two modes of operation. In "zero configuration" mode it is used
directly as a tool by running `fab`. This examines the currently selected
directory and tries to build whatever it finds there.

In "framework" mode it offers a library of building-blocks which a developer
can use to create a build system customised to the needs of their software.
