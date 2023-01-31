FROM ubuntu:20.04

RUN apt update && apt install -y gcc gfortran libclang-dev python-clang python3-pip rsync

RUN mkdir -p ~/.local/lib/python3.8/site-packages
RUN cp -vr /usr/lib/python3/dist-packages/clang ~/.local/lib/python3.8/site-packages/

RUN pip install flake8 fparser matplotlib mypy pytest sphinx sphinx_rtd_theme

CMD [ "python3", "--version" ]
