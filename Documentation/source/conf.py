# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

from fab import __version__ as fab_version

sys.path.insert(0, os.path.abspath('../../source'))


# -- Project information -----------------------------------------------------

project = 'Fab'
copyright = '2024 Met Office. All rights reserved.'
author = 'Fab Team'

# The full version, including alpha/beta/rc tags
release = fab_version

# The version up to the minor patch, for distinguishing multi-version docs
version = '.'.join(release.split('.')[:2])

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.graphviz',
    'sphinx.ext.intersphinx',
    'sphinx.ext.autosectionlabel',
    'sphinxcontrib.rsvgconverter',
    'sphinx_autodoc_typehints',
    'sphinx_copybutton',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Autodoc -----------------------------------------------------------------

autodoc_default_options = {
    'members': True,
    'show-inheritane': True
}

autoclass_content = 'both'


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'pydata_sphinx_theme'

html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/MetOffice/fab",
            "icon": "fa-brands fa-github"
        }
    ],
    "footer_start": ["crown-copyright"],
    "footer_center": ["sphinx-version"],
    "footer_end": ["theme-version"],
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


# Don't sort module contents alphabetically, we want to order them in a helpful way for the user to read.
autodoc_member_order = 'bysource'


# Join the class and constructor docstrings.
autoclass_content = 'both'

#
intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}

# create linkable targets from section headings
autosectionlabel_prefix_document = True


# include default values in argument descriptions
typehints_defaults = 'braces-after'

# linkcheck builder
linkcheck_allow_redirects = True  # Allow redirects to pass
linkcheck_ignore = [
    "https://metoffice.sharepoint.com",  # Ignore SharePoint links
    r'.*\.py$',  # Ignores URLs ending with .py
]
linkcheck_timeout = 2
linkcheck_allow_unauthorized = True  # Allow unauthorized links to pass
