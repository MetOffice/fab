from collections.abc import Iterable
from pathlib import Path

from fabengine.actions import Action, Prerequisite, SubprocessAction
from fabengine.actions.fortran import AnalyseFortran
from fabengine.artefact_store import ArtefactPath
from fabengine.database import Database
from fabengine.prerequisite import RealFilePrerequisite


class Templaterator(SubprocessAction):
    """
    Processes Fortran template files.
    """

    def __init__(
        self,
        filename: Path,
        leafname: ArtefactPath,
        inserts: dict[str, str],
        database: Database,
    ):
        """
        :param filename: Template file.
        :param leafname: Name of generated file.
        :param inserts: Keyed values imposed on template.
        :param database: Build system state and configuration.
        """
        self._filename = filename
        self._leafname = leafname
        self._database = database

        destination = database.artefact_store.get_artefact(leafname).real_filename
        # Todo: Just have the source here?
        # Todo: Put generated files in the correct place.
        arguments = ["-o", destination]
        for key, value in inserts.items():
            arguments.extend(["-s", key + "=" + value])
        arguments.append(self._filename)
        super().__init__(
            self._database.configuration["paths"]["templaterator"], arguments
        )

    def __str__(self) -> str:
        return f"Templating: {self._filename}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: Depends on template file.
        """
        return [RealFilePrerequisite(self._filename)]

    def perform(self) -> list[Action]:
        """
        Performs templating.

        .. Todo:: Just include the templaterator source here? Removes need to
                  know about core.
        .. Todo:: Put generated files in the correct place, not top level.

        :return: Analyse resulting Fortran source.
        """
        self.run_subprocess()
        return [AnalyseFortran(self._leafname, self._database)]
