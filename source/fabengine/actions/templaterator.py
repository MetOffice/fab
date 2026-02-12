from pathlib import Path
from typing import Iterable

from fabengine.actions import Action, Prerequisite, SubprocessAction
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class Templaterator(SubprocessAction):
    """
    Processes Fortran template files.
    """

    def __init__(
        self,
        filename: Path,
        leafname: str,
        inserts: dict[str, str],
        core_dir: Path,
        database: Database,
    ):
        """
        :param filename: Template file.
        :param leafname: Name of generated file.
        :param inserts: Keyed values imposed on template.
        :param core_dir: LFRic core source, used to find templaterator.
        :param database: Build system state and configuration.
        """
        self._filename = filename
        self._database = database

        self._destination = database.configuration.build_dir / leafname

        # Todo: Just have the source here?
        # Todo: Put generated files in the correct place.
        arguments = ["-o", self._destination]
        for key, value in inserts.items():
            arguments.extend(["-s", key + "=" + value])
        arguments.append(self._filename)
        super().__init__(
            core_dir / "infrastructure" / "build" / "tools" / "Templaterator", arguments
        )

    def __str__(self) -> str:
        return f"Templating: {self._filename}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: Depends on template file.
        """
        return [FilePrerequisite(self._filename)]

    def perform(self) -> list[Action]:
        """
        Performs templating.

        .. Todo:: Just include the templaterator source here? Removes need to
                  know about core.
        .. Todo:: Put generated files in the correct place, not top level.

        :return: Analyse resulting Fortran source.
        """
        self.run_subprocess()
        return [AnalyseFortran(self._destination, self._database)]
