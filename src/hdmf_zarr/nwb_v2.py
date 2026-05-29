"""Read-only NWB IO backend for NWB Zarr files written with hdmf-zarr<1.0 + zarr<3.

:class:`NWBZarrV2IO` is the V2 counterpart of :class:`~hdmf_zarr.NWBZarrIO`.
It uses :class:`~hdmf_zarr.v2_backend.ZarrV2IO` under the hood, which knows
how to navigate zarr v2 stores with zarr-python v3.
"""

from pathlib import Path

from hdmf.build import TypeMap
from hdmf.utils import docval, popargs, get_docval

from .nwb import _build_nwb_manager
from .v2_backend import ZarrV2IO


class NWBZarrV2IO(ZarrV2IO):
    """Read-only NWB IO for zarr-v2 files, opened via :class:`ZarrV2IO`.

    Use this class — or rely on :meth:`NWBZarrIO.read_nwb` auto-dispatching to
    it — when reading NWB files written by older hdmf-zarr versions.
    """

    @docval(
        *get_docval(ZarrV2IO.__init__),
        {
            "name": "load_namespaces",
            "type": bool,
            "doc": "whether or not to load cached namespaces from given path",
            "default": True,
        },
        {
            "name": "extensions",
            "type": (str, TypeMap, list),
            "doc": "a path to a namespace, a TypeMap, or a list consisting paths  to namespaces and TypeMaps",
            "default": None,
        },
    )
    def __init__(self, **kwargs):
        path, mode, manager, extensions, load_namespaces, storage_options = popargs(
            "path", "mode", "manager", "extensions", "load_namespaces", "storage_options", kwargs
        )
        manager = _build_nwb_manager(
            type(self), path, mode, manager, extensions, load_namespaces, storage_options
        )
        super().__init__(path, manager=manager, mode=mode, storage_options=storage_options)

    @staticmethod
    @docval(
        {
            "name": "path",
            "type": (str, Path),
            "doc": "the path to the zarr v2 NWB file",
        },
        is_method=False,
    )
    def read_nwb(**kwargs):
        """Open a zarr-v2 NWB file and return its :class:`NWBFile`."""
        path = popargs("path", kwargs)
        if isinstance(path, Path):
            path = str(path)
        storage_options = None
        if isinstance(path, str) and path.startswith(("s3://")):
            storage_options = dict(anon=True)
        io = NWBZarrV2IO(path=path, mode="r", load_namespaces=True, storage_options=storage_options)
        return io.read()
