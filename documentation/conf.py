# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
#
from pathlib import Path
from sys import path as sys_path

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'TBS'
copyright = 'Met Office'
author = 'Team TBS'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'pydata_sphinx_theme',
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinxcontrib.mermaid',
    'matplotlib.sphinxext.plot_directive'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# As of Feb 2026 there seems to be a bug in Sphinx where it can't recognise
# certain standard Python libraries such as pathlib and abc. As a crude
# solution to this problem we ignore these warnings.
#
nitpick_ignore = {
    ('py:class', 'abc.ABC'),
    ('py:class', 'collections.abc.Generator'),
    ('py:class', 'collections.abc.Iterable'),
    ('py:class', 'enum.Enum'),
    ('py:class', 'multiprocessing.Process'),
    ('py:class', 'multiprocessing.managers.SyncManager'),
    ('py:class', 'pathlib.Path'),
    ('py:class', 'Path'),
    ('py:class', 'Queue')
}

# -- Automatic API documentation generator -----------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/apidoc.html

sys_path.insert(0, str(Path('..', 'source').resolve()))

apidoc_modules = [
    {
        'path': '../source',
        'destination': '_api',
        'separate_modules': True,
        'module_first': True,
    }
]

autoclass_content = 'both'

autodoc_default_options = {
    'members': True,
    'show-inheritance': True,
}
autodoc_inherit_docstrings = True
autodoc_member_order = 'groupwise'
autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'

todo_include_todos = True


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_theme_options = {
    'collapse_navigation': True,
    'footer_start': ['crown-copyright', 'sphinx-version'],
    'navigation_depth': 2,
    'show_nav_level': 2
}
# html_static_path = ['_static']
