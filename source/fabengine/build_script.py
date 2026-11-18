from abc import ABC
from collections.abc import Iterable
from pathlib import Path

from fabengine.repository import Repository


class BuildScript(ABC):
    def repositories(
        self, dependencies_file: Path | str | None
    ) -> Iterable[Repository]:
        return []

    def packages(self) -> list[str]:
        return []

    def fpp_definitions(self) -> dict:
        return {}

    def force_prerequisites(self) -> dict[str, str]:
        return {}

    def openmp(self) -> bool:
        return False

    def fortran_pp(self) -> Path:
        return Path("cpp")

    def fortran_pp_flags(self) -> list[str]:
        return []

    def fortran_compile_flags_common(self) -> list[str]:
        return []

    def fortran_overrides(self) -> dict:
        """
        Path specific overrides to fortran compilation settings.

        :return: A dictionary of Paths. Values should be dictionaries with keys and item
                 types as described in validate_overrides
        """
        return {}

    def c_pp(self) -> Path:
        return Path("cpp")

    def c_pp_flags(self) -> list[str]:
        return []

    def c_compile_flags_common(self) -> list[str]:
        return []

    def c_overrides(self) -> dict:
        """
        Path specific overrides to c compilation settings.

        :return: A dictionary of Paths. Values should be dictionaries with keys and item
                 types as described in validate_overrides
        """
        return {}

    @property
    def build_name(self) -> str:
        """Determine the build name based on a property of the class name."""

        if hasattr(self, "__build_name"):
            return self.__build_name
        return self.__class__.__name__
