"""Module with Zarr backend for NWB for integration with PyNWB"""

from pathlib import Path
from .backend import ZarrIO, SUPPORTED_ZARR_STORES

from hdmf.utils import docval, popargs, get_docval
from hdmf.backends.io import HDMFIO
from hdmf.build import BuildManager, TypeMap
from pynwb import get_manager, get_type_map


def _build_nwb_manager(io_cls, path, mode, manager, extensions, load_namespaces, storage_options):
    """Resolve a BuildManager for NWB given the IO subclass and constructor args.

    Centralises the namespace-loading + manager-selection logic that both
    :class:`NWBZarrIO` and :class:`NWBZarrV2IO` share.
    """
    io_modes_that_create_file = ["w", "w-", "x"]
    if mode in io_modes_that_create_file or manager is not None or extensions is not None:
        load_namespaces = False

    if load_namespaces:
        tm = get_type_map()
        io_cls.load_namespaces(namespace_catalog=tm, path=path, storage_options=storage_options)
        return BuildManager(tm)

    if manager is not None and extensions is not None:
        raise ValueError("'manager' and 'extensions' cannot be specified together")
    if extensions is not None:
        return get_manager(extensions=extensions)
    if manager is None:
        return get_manager()
    return manager


class NWBZarrIO(ZarrIO):
    """
    IO backend for PyNWB for writing NWB files

    This class is similar to the :py:class:`~pynwb.NWBHDF5IO` class in PyNWB. The main purpose of this class
    is to perform default setup for BuildManager, loading or namespaces etc., in the context
    of the NWB format.
    """

    @docval(
        *get_docval(ZarrIO.__init__),
        {
            "name": "load_namespaces",
            "type": bool,
            "doc": "whether or not to load cached namespaces from given path - not applicable in write mode",
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

    @docval(
        {"name": "src_io", "type": HDMFIO, "doc": "the HDMFIO object for reading the data to export"},
        {
            "name": "nwbfile",
            "type": "NWBFile",
            "doc": "the NWBFile object to export. If None, then the entire contents of src_io will be exported",
            "default": None,
        },
        {"name": "write_args", "type": dict, "doc": "arguments to pass to :py:meth:`write_builder`", "default": dict()},
    )
    def export(self, **kwargs):
        nwbfile = popargs("nwbfile", kwargs)
        kwargs["container"] = nwbfile
        super().export(**kwargs)

    @staticmethod
    @docval(
        {
            "name": "path",
            "type": (str, Path, *SUPPORTED_ZARR_STORES),
            "doc": "the path to the Zarr file or a supported Zarr store",
        },
        is_method=False,
    )
    def read_nwb(**kwargs):
        """
        Helper factory method for reading an NWB file and return the NWBFile object.
        """
        # Retrieve the filepath
        path = popargs("path", kwargs)
        if isinstance(path, Path):
            path = str(path)
        # determine default storage options to use when opening a file from S3
        storage_options = None
        if isinstance(path, str) and path.startswith(("s3://")):
            storage_options = dict(anon=True)

        # open the file with NWBZarrIO and rad the file
        io = NWBZarrIO(path=path, mode="r", load_namespaces=True, storage_options=storage_options)
        nwbfile = io.read()

        # return the NWBFile object
        return nwbfile
