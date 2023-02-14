# Usage:
# docker build -t fab .
# docker run --env PYTHONPATH=/fab/source -v /home/byron/git/fab:/fab -v /home/byron:/home/byron -it fab bash

FROM ubuntu:20.04

RUN apt update && apt install -y gcc gfortran libclang-dev python-clang python3-pip rsync git

RUN mkdir -p ~/.local/lib/python3.8/site-packages
RUN cp -vr /usr/lib/python3/dist-packages/clang ~/.local/lib/python3.8/site-packages/

RUN pip install pytest pytest-cov pytest-mock flake8 mypy
RUN pip install sphinx sphinx_rtd_theme sphinx-autodoc-typehints
RUN pip install svn GitPython matplotlib
RUN pip install fparser

CMD [ "python3", "--version" ]
