
Development
===========
Information for developers.

Version numbering
-----------------
We use a `PEP 440 compliant <https://peps.python.org/pep-0440/#examples-of-compliant-version-schemes>`_
semantic versioning, of the form ``{major}.{minor}.{patch}[{a|b|rc}N]``

* 0.9.5
* 1.0.0a1
* 1.0.0a2
* 1.0.0b1
* 1.0.0rc1
* 1.0.0
* 1.0.1
* 1.1.0a1

Version bumping
---------------
The version number needs to be updated in two places

* source/fab/__init_.py
* docs/source/conf.py

Consider adding a developers' tool like `BumpVer <https://pypi.org/project/bumpver>`_.
