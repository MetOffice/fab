# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

import os.path
import setuptools  # type: ignore

_here = os.path.dirname(__file__)

with open(os.path.join(_here, 'README.md'), 'r', encoding='utf-8') as handle:
    _long_description = handle.read()

with open(os.path.join(_here, 'source', 'fab', '__init__.py'),
          encoding='utf-8') as handle:
    for line in handle:
        bits = line.split('=', 1)
        if bits[0].strip().lower() == '__version__':
            _version = bits[1].strip().strip('"\'')
            break
    else:
        raise RuntimeError('Cannot determine package version.')

tests = ['pytest', 'pytest-cov', 'pytest-mock', 'flake8', 'mypy']
docs = ['sphinx', 'sphinx-material', 'sphinx-autodoc-typehints', 'sphinx-copybutton']
features = ['matplotlib', 'jinja2', 'psyclone']

setuptools.setup(
    name='sci-fab',
    version=_version,
    author='SciFab Developers',
    author_email='metomi@metoffice.gov.uk',
    description='Build system for scientific software',
    long_description=_long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Metomi/fab',
    project_urls={
        'Bug reports': 'https://github.com/metomi/fab/issues',
        'Source': 'https://github.com/metomi/fab/'
    },
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Build Tools'
        ],
    package_dir={'': 'source'},
    packages=setuptools.find_packages(where='source'),
    python_requires='>=3.7, <4',
    install_requires=['fparser'],  # you'll also need python-clang if your project includes c code
    extras_require={
        'tests': tests,
        'docs': docs,
        'features': features,
        'dev': [*tests, *docs, *features],
    },
    entry_points={
        'console_scripts': [
            'fab=fab.cli:cli_fab'
        ]
    },
)
