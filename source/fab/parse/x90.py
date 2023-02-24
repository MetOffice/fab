# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Iterable, Set, Union, Optional, Dict, Any

from fparser.two.Fortran2003 import Use_Stmt, Call_Stmt, Name, Only_List, Actual_Arg_Spec_List, Part_Ref  # type: ignore

from fab.parse import AnalysedFile
from fab.parse.fortran_common import FortranAnalyserBase, iter_content, logger, _typed_child
from fab.util import by_type


class AnalysedX90(AnalysedFile):
    """
    Analysis results for an x90 file.

    """
    def __init__(self, fpath: Union[str, Path], file_hash: int,
                 # todo: the fortran version doesn't include the remaining args - update this too, for simplicity.
                 kernel_deps: Optional[Iterable[str]] = None):
        """
        :param fpath:
            The path of the x90 file.
        :param file_hash:
            The checksum of the x90 file.
        :param kernel_deps:
            Kernel symbols used by the x90 file.

        """
        super().__init__(fpath=fpath, file_hash=file_hash)

        # Maps used kernel metadata (type def names) to the modules they're found in
        self.kernel_deps: Set[str] = set(kernel_deps or {})

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "kernel_deps": sorted(self.kernel_deps),
        })
        return result

    @classmethod
    def from_dict(cls, d):
        result = cls(
            fpath=Path(d["fpath"]),
            file_hash=d["file_hash"],
            kernel_deps=set(d["kernel_deps"]),
        )
        assert result.file_hash is not None
        return result

    @classmethod
    def field_names(cls):
        return super().field_names() + [
            'kernel_deps',
        ]


class X90Analyser(FortranAnalyserBase):

    # Makes a parsable fortran version of x90.
    # todo: Use hashing to reuse previous analysis results.

    def __init__(self):
        super().__init__(result_class=AnalysedX90)

    def walk_nodes(self, fpath, file_hash, node_tree) -> AnalysedX90:  # type: ignore

        analysed_file = AnalysedX90(fpath=fpath, file_hash=file_hash)
        symbol_deps: Dict[str, str] = {}

        for obj in iter_content(node_tree):
            obj_type = type(obj)
            try:
                if obj_type == Use_Stmt:
                    self._process_use_statement(symbol_deps, obj)  # raises

                elif obj_type == Call_Stmt:
                    self._process_call_statement(symbol_deps, analysed_file, obj)

            except Exception:
                logger.exception(f'error processing node {obj.item or obj_type} in {fpath}')

        # save results for reuse
        # analysis_fpath = self._get_analysis_fpath(fpath, file_hash)
        # analysed_file.save(analysis_fpath)

        return analysed_file

    def _process_use_statement(self, symbol_deps: Dict[str, str], obj):
        # Record the modules in which potential kernels live.
        # We'll find out if they're kernels later.
        module_dep = _typed_child(obj, Name, must_exist=True)
        only_list = _typed_child(obj, Only_List)
        if not only_list:
            return

        name_nodes = by_type(only_list.children, Name)
        for name in name_nodes:
            symbol_deps[name.string] = module_dep.string

    def _process_call_statement(self, symbol_deps: Dict[str, str], analysed_file, obj):
        # if we're calling invoke, record the names of the args.
        # sanity check they end with "_type".
        called_name = _typed_child(obj, Name)
        if not called_name:
            # we see this for member calls, like "thing%func()", which we're not interested in
            return
        if called_name.string == "invoke":
            arg_list = _typed_child(obj, Actual_Arg_Spec_List)
            if not arg_list:
                logger.debug(f'No arg list passed to invoke: {obj.string}')
                return
            args = by_type(arg_list.children, Part_Ref)
            for arg in args:
                arg_name = _typed_child(arg, Name)
                arg_name = arg_name.string
                if arg_name in symbol_deps:
                    analysed_file.kernel_deps.add(arg_name)
                else:
                    logger.debug(f"arg '{arg_name}' to invoke() was not used, presumed built-in kernel")
