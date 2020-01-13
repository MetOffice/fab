import setuptools

with open('README.md', 'r') as handle:
    long_description = handle.read()

setuptools.setup(
    name='fabricate',
    version='0.1.dev0',
    author='',
    author_email='',
    description='Build system for scientific software',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Metomi/fab',
    packages=setuptools.find_packages(),
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'ProgrammingLanguage :: Python :: 3',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Build Tools'
        ],
    python_requires='>=3.6'
)
