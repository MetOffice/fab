##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from abc import ABC, abstractmethod
from pathlib import Path
from typing import IO, Iterator, List, Text, Union
from zlib import adler32


class TextReader(ABC):
    # TODO: Consider whether returning Path or str will cause
    #       any weird behaviour anywhere
    @property
    @abstractmethod
    def filename(self) -> Union[Path, str]:
        raise NotImplementedError('Abstract method must be implemented')

    @abstractmethod
    def line_by_line(self) -> Iterator[str]:
        raise NotImplementedError('Abstract method must be implemented')


class FileTextReader(TextReader):
    def __init__(self, filename: Path):
        self._filename: Path = filename
        self._handle = None

    def __del__(self):
        if self._handle is not None:
            self._handle.close()

    def get_handle(self):
        if self._handle is None:
            self._handle: IO[Text] = \
                self._filename.open(encoding='utf-8')
        return self._handle

    @property
    def filename(self):
        return self._filename

    def line_by_line(self):
        handle = self.get_handle()
        for line in handle.readlines():
            yield line


class StringTextReader(TextReader):
    def __init__(self, string: str):
        self._hash = hash(string)
        self._content: List[str] = string.splitlines(keepends=True)

    @property
    def filename(self):
        return f'[string:{hash(self._hash)}]'

    def line_by_line(self):
        while len(self._content) > 0:
            yield self._content.pop(0)


class TextReaderDecorator(TextReader, ABC):
    def __init__(self, reader: TextReader):
        self._source = reader

    @property
    def filename(self):
        return self._source.filename


class TextReaderAdler32(TextReaderDecorator):
    def __init__(self, source: TextReader):
        super().__init__(source)
        self._hash = 1

    @property
    def hash(self):
        return self._hash

    def line_by_line(self):
        for line in self._source.line_by_line():
            self._hash = adler32(bytes(line, encoding='utf-8'), self._hash)
            yield line
