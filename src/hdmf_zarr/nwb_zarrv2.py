"""Read-only NWB IO backend for NWB Zarr files written with hdmf-zarr<1.0 + zarr<3.

:class:`NWBZarrV2IO` is the V2 counterpart of :class:`~hdmf_zarr.NWBZarrIO`.
It uses :class:`~hdmf_zarr.backend_v2.ZarrV2IO` under the hood, which knows
how to navigate zarr v2 stores with zarr-python v3.
"""

from pathlib import Path

from hdmf.build import TypeMap
from hdmf.utils import docval, popargs, get_docval

from .backend import SUPPORTED_ZARR_STORES
from .nwb import NWBZarrIO, _build_nwb_manager
from .backend_zarrv2 import ZarrV2IO


class NWBZarrV2IO(ZarrV2IO):
    """Read-only NWB IO for zarr-v2 files, opened via :class:`ZarrV2IO`.

    Use this class when reading NWB files written by older hdmf-zarr versions.
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

    @docval(
        {
            "name": "path",
            "type": (str, Path, *SUPPORTED_ZARR_STORES),
            "doc": "the destination path (or Zarr store) for the exported zarr v3 NWB file",
        },
        {
            "name": "nwbfile",
            "type": "NWBFile",
            "doc": (
                "the NWBFile object to export. If None, the file is read from this IO and exported in full."
            ),
            "default": None,
        },
        {
            "name": "write_args",
            "type": dict,
            "doc": "arguments to pass to :py:meth:`write_builder`",
            "default": None,
        },
        {
            "name": "storage_options",
            "type": dict,
            "doc": "Zarr storage options for the destination store",
            "default": None,
        },
    )
    def export_to_v3(self, **kwargs):
        """Export this zarr-v2 NWB file to a new zarr-v3 NWB file.

        Reads the contents of this read-only zarr-v2 file and writes them out as a
        zarr-v3 file via :class:`~hdmf_zarr.NWBZarrIO`. Because a v2 → v3 conversion
        rewrites the storage layout, data chunks are always copied (``link_data`` is
        forced to ``False``) rather than linked back to the source file.
        """
        path, nwbfile, write_args, storage_options = popargs(
            "path", "nwbfile", "write_args", "storage_options", kwargs
        )
        if isinstance(path, Path):
            path = str(path)
        write_args = dict(write_args) if write_args is not None else {}
        # v2 -> v3 is a format conversion: chunks must be re-written, not linked
        write_args["link_data"] = False

        if nwbfile is None:
            nwbfile = self.read()
        nwbfile.set_modified()

        with NWBZarrIO(path=path, mode="w", storage_options=storage_options) as export_io:
            export_io.export(nwbfile=nwbfile, src_io=self, write_args=write_args)

    @staticmethod
    @docval(
        {
            "name": "source_path",
            "type": (str, Path),
            "doc": "the path to the source zarr v2 NWB file to convert",
        },
        {
            "name": "dest_path",
            "type": (str, Path, *SUPPORTED_ZARR_STORES),
            "doc": "the destination path (or Zarr store) for the exported zarr v3 NWB file",
        },
        {
            "name": "write_args",
            "type": dict,
            "doc": "arguments to pass to :py:meth:`write_builder`",
            "default": None,
        },
        {
            "name": "storage_options",
            "type": dict,
            "doc": "Zarr storage options for the destination store",
            "default": None,
        },
        is_method=False,
    )
    def convert_to_v3(**kwargs):
        """Convert a zarr-v2 NWB file to a new zarr-v3 NWB file in one call.

        Convenience one-shot wrapper that opens *source_path* with
        :class:`NWBZarrV2IO` and exports it to *dest_path* as a zarr-v3 file. For
        more control (e.g. inspecting or modifying the :class:`NWBFile` before
        writing), open the file yourself and use :meth:`export_to_v3` instead.

        Example::

            NWBZarrV2IO.convert_to_v3("old_v2.nwb.zarr", "new_v3.nwb.zarr")
        """
        source_path, dest_path, write_args, storage_options = popargs(
            "source_path", "dest_path", "write_args", "storage_options", kwargs
        )
        if isinstance(source_path, Path):
            source_path = str(source_path)
        source_storage_options = None
        if isinstance(source_path, str) and source_path.startswith(("s3://")):
            source_storage_options = dict(anon=True)
        with NWBZarrV2IO(
            path=source_path, mode="r", load_namespaces=True, storage_options=source_storage_options
        ) as v2_io:
            v2_io.export_to_v3(path=dest_path, write_args=write_args, storage_options=storage_options)

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
