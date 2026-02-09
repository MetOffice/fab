from __future__ import annotations

from pathlib import Path
from typing import Optional


class Project:
    def __init__(self, project_dir: Path,
                 identifier: Optional[str] = None,
                 source_dir: Path = Path('source'),
                 configuration_meta_data: Path = Path('rose-meta')):
        self._project_dir = project_dir
        self._identifier = identifier or self._project_dir.name
        self._source_dir = source_dir
        self._configuration_meta_data = configuration_meta_data

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def project_dir(self) -> Path:
        return self._project_dir

    @property
    def source_dir(self) -> Path:
        return self._project_dir / self._source_dir

    @property
    def configuration_meta_data(self) -> Path:
        return self._project_dir / self._configuration_meta_data
