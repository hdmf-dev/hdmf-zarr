"""Module with the Zarr-based I/O-backend for HDMF"""

# Python imports
import os
import shutil
import warnings
import numpy as np
import tempfile
import logging

# Zarr imports
import zarr
from zarr.hierarchy import Group
from zarr.core import Array
from zarr.storage import DirectoryStore, TempStore, NestedDirectoryStore, ConsolidatedMetadataStore
import numcodecs

# HDMF-ZARR imports
from .utils import ZarrDataIO, ZarrReference, ZarrSpecWriter, ZarrSpecReader, ZarrIODataChunkIteratorQueue
from .zarr_utils import BuilderZarrReferenceDataset, BuilderZarrTableDataset

# HDMF imports
from hdmf.backends.io import HDMFIO
from hdmf.backends.errors import UnsupportedOperation
from hdmf.backends.utils import NamespaceToBuilderHelper, WriteStatusTracker
from hdmf.utils import docval, getargs, popargs, get_docval, get_data_shape
from hdmf.build import Builder, GroupBuilder, DatasetBuilder, LinkBuilder, BuildManager, ReferenceBuilder, TypeMap
from hdmf.data_utils import AbstractDataChunkIterator
from hdmf.spec import RefSpec, DtypeSpec, NamespaceCatalog
from hdmf.query import HDMFDataset
from hdmf.container import Container

from pathlib import Path


# Module variables
ROOT_NAME = "root"
"""
Name of the root builder for read/write
"""

SPEC_LOC_ATTR = ".specloc"
"""
Reserved attribute storing the path to the Group where the schema for the file are cached
"""

DEFAULT_SPEC_LOC_DIR = "specifications"
"""
Default name of the group where specifications should be cached
"""

SUPPORTED_ZARR_STORES = (DirectoryStore, TempStore, NestedDirectoryStore)
"""
Tuple listing all Zarr storage backends supported by ZarrIO
"""


class ZarrIO(HDMFIO):

    @staticmethod
    def can_read(path):
        try:
            # TODO: how to use storage_options? Maybe easier to just check for ".zarr" suffix
            zarr.open(path, mode="r")
            return True
        except Exception:
            return False

    @docval(
        {
            "name": "path",
            "type": (str, Path, *SUPPORTED_ZARR_STORES),
            "doc": "the path to the Zarr file or a supported Zarr store",
        },
        {
            "name": "manager",
            "type": BuildManager,
            "doc": "the BuildManager to use for I/O",
            "default": None,
        },
        {
            "name": "mode",
            "type": str,
            "doc": (
                'the mode to open the Zarr file with, one of ("w", "r", "r+", "a", "r-"). '
                "the mode r- is used to force open without consolidated metadata in read only mode."
            ),
        },
        {
            "name": "synchronizer",
            "type": (zarr.ProcessSynchronizer, zarr.ThreadSynchronizer, bool),
            "doc": "Zarr synchronizer to use for parallel I/O. If set to True a ProcessSynchronizer is used.",
            "default": None,
        },
        {
            "name": "object_codec_class",
            "type": None,
            "doc": (
                "Set the numcodec object codec class to be used to encode objects."
                "Use numcodecs.pickles.Pickle by default."
            ),
            "default": None,
        },
        {
            "name": "storage_options",
            "type": dict,
            "doc": "Zarr storage options to read remote folders",
            "default": None,
        },
        {
            "name": "force_overwrite",
            "type": bool,
            "doc": (
                "force overwriting existing object when in 'w' mode. The existing file or directory"
                " will be deleted when before opening (even if the object is not Zarr, e.g,. an HDF5 file)"
            ),
            "default": False,
        },
    )
    def __init__(self, **kwargs):
        self.logger = logging.getLogger("%s.%s" % (self.__class__.__module__, self.__class__.__qualname__))
        path, manager, mode, synchronizer, object_codec_class, storage_options, force_overwrite = popargs(
            "path",
            "manager",
            "mode",
            "synchronizer",
            "object_codec_class",
            "storage_options",
            "force_overwrite",
            kwargs,
        )
        if manager is None:
            manager = BuildManager(TypeMap(NamespaceCatalog()))
        if isinstance(synchronizer, bool):
            if synchronizer:
                sync_path = tempfile.mkdtemp()
                self.__synchronizer = zarr.ProcessSynchronizer(sync_path)
            else:
                self.__synchronizer = None
        else:
            self.__synchronizer = synchronizer
        self.__mode = mode
        self.__force_overwrite = force_overwrite
        if isinstance(path, Path):
            path = str(path)
        self.__path = path
        self.__file = None
        self.__storage_options = storage_options
        self.__built = dict()
        self._written_builders = WriteStatusTracker()  # track which builders were written (or read) by this IO object
        self.__dci_queue = None  # Will be initialized on call to io.write
        # Codec class to be used. Alternates, e.g., =numcodecs.JSON
        self.__codec_cls = numcodecs.pickles.Pickle if object_codec_class is None else object_codec_class
        source_path = self.__path
        if isinstance(self.__path, SUPPORTED_ZARR_STORES):
            source_path = self.__path.path
        super().__init__(manager, source=source_path)

    @property
    def file(self):
        """
        The Zarr zarr.hierarchy.Group (or zarr.core.Array) opened by the backend.
        May be None in case open has not been called yet, e.g., if no data has been
        read or written yet via this instance.
        """
        return self.__file

    @property
    def path(self):
        """The path to the Zarr file as set by the user"""
        return self.__path

    @property
    def abspath(self):
        """The absolute path to the Zarr file"""
        return os.path.abspath(self.source)

    @property
    def synchronizer(self):
        return self.__synchronizer

    @property
    def object_codec_class(self):
        return self.__codec_cls

    @property
    def mode(self):
        """
        The mode specified by the user when creating the ZarrIO instance.

        NOTE: The Zarr library may not honor the mode. E.g., DirectoryStore in Zarr uses
        append mode and does not allow setting a file to read-only mode.
        """
        return self.__mode

    def open(self):
        """Open the Zarr file"""
        if self.__file is None:
            # Allow overwriting an existing file (e.g., an HDF5 file). Zarr will normally fail if the
            # existing object at the path is a file. So if we are in `w` mode we need to delete the file first
            if self.mode == "w" and self.__force_overwrite:
                if isinstance(self.path, (str, Path)) and os.path.exists(self.path):
                    if os.path.isdir(self.path):  # directory
                        shutil.rmtree(self.path)
                    else:  # File
                        os.remove(self.path)

            # Within zarr, open_consolidated only allows the mode to be 'r' or 'r+'.
            # As a result, when in other modes, the file will not use consolidated metadata.
            if self.mode != "r":
                # When we consolidate metadata, we use ConsolidatedMetadataStore.
                # This interface does not allow for setting items.
                # In the doc string, it says it is "read only". As a result, we cannot use r+ with consolidate_metadata.
                # r- is only an internal mode in ZarrIO to force the use of regular open. For Zarr we need to
                # use the regular mode r when r- is specified
                mode_to_use = self.mode if self.mode != "r-" else "r"
                self.__file = zarr.open(
                    store=self.path,
                    mode=mode_to_use,
                    synchronizer=self.__synchronizer,
                    storage_options=self.__storage_options,
                )
            else:
                self.__file = self.__open_file_consolidated(
                    store=self.path,
                    mode=self.mode,
                    synchronizer=self.__synchronizer,
                    storage_options=self.__storage_options,
                )

    def close(self):
        """Close the Zarr file"""
        self.__file = None
        return

    def is_remote(self):
        """Return True if the file is remote, False otherwise"""
        from zarr.storage import FSStore

        if isinstance(self.file.store, FSStore):
            return True
        else:
            return False

    @classmethod
    @docval(
        {
            "name": "namespace_catalog",
            "type": (NamespaceCatalog, TypeMap),
            "doc": "the NamespaceCatalog or TypeMap to load namespaces into",
        },
        {
            "name": "path",
            "type": (str, Path, *SUPPORTED_ZARR_STORES),
            "doc": "the path to the Zarr file or a supported Zarr store",
        },
        {
            "name": "storage_options",
            "type": dict,
            "doc": "Zarr storage options to read remote folders",
            "default": None,
        },
        {"name": "namespaces", "type": list, "doc": "the namespaces to load", "default": None},
    )
    def load_namespaces(cls, namespace_catalog, path, storage_options, namespaces=None):
        """
        Load cached namespaces from a file.
        """
        # TODO: how to use storage_options here?
        f = zarr.open(path, mode="r", storage_options=storage_options)
        if SPEC_LOC_ATTR not in f.attrs:
            msg = "No cached namespaces found in %s" % path
            warnings.warn(msg)
        else:
            spec_group = f[f.attrs[SPEC_LOC_ATTR]]
            if namespaces is None:
                namespaces = list(spec_group.keys())
            for ns in namespaces:
                ns_group = spec_group[ns]
                latest_version = list(ns_group.keys())[-1]
                ns_group = ns_group[latest_version]
                reader = ZarrSpecReader(ns_group)
                namespace_catalog.load_namespaces("namespace", reader=reader)

    @docval(
        {"name": "container", "type": Container, "doc": "the Container object to write"},
        {"name": "cache_spec", "type": bool, "doc": "cache specification to file", "default": True},
        {
            "name": "link_data",
            "type": bool,
            "doc": "If not specified otherwise link (True) or copy (False) Datasets",
            "default": True,
        },
        {
            "name": "exhaust_dci",
            "type": bool,
            "doc": (
                "exhaust DataChunkIterators one at a time. If False, add "
                "them to the internal queue self.__dci_queue and exhaust them concurrently at the end"
            ),
            "default": True,
        },
        {
            "name": "number_of_jobs",
            "type": int,
            "doc": (
                "Number of jobs to use in parallel during write "
                "(only works with GenericDataChunkIterator-wrapped datasets)."
            ),
            "default": 1,
        },
        {
            "name": "max_threads_per_process",
            "type": int,
            "doc": ("Limits the number of threads used by each process. The default is None (no limits)."),
            "default": None,
        },
        {
            "name": "multiprocessing_context",
            "type": str,
            "doc": (
                "Context for multiprocessing. It can be None (default), 'fork' or 'spawn'. "
                "Note that 'fork' is only available on UNIX systems (not Windows)."
            ),
            "default": None,
        },
        {
            "name": "consolidate_metadata",
            "type": bool,
            "doc": ("Consolidate metadata into a single .zmetadata file in the root group to accelerate read."),
            "default": True,
        },
    )
    def write(self, **kwargs):
        """Overwrite the write method to add support for caching the specification and parallelization."""
        cache_spec, number_of_jobs, max_threads_per_process, multiprocessing_context = popargs(
            "cache_spec", "number_of_jobs", "max_threads_per_process", "multiprocessing_context", kwargs
        )

        self.__dci_queue = ZarrIODataChunkIteratorQueue(
            number_of_jobs=number_of_jobs,
            max_threads_per_process=max_threads_per_process,
            multiprocessing_context=multiprocessing_context,
        )

        super(ZarrIO, self).write(**kwargs)
        if cache_spec:
            self.__cache_spec()

    def __cache_spec(self):
        """Internal function used to cache the spec in the current file"""
        ref = self.__file.attrs.get(SPEC_LOC_ATTR)
        spec_group = None
        if ref is not None:
            spec_group = self.__file[ref]
        else:
            path = DEFAULT_SPEC_LOC_DIR  # do something to figure out where the specifications should go
            spec_group = self.__file.require_group(path)
            self.__file.attrs[SPEC_LOC_ATTR] = path
        ns_catalog = self.manager.namespace_catalog
        for ns_name in ns_catalog.namespaces:
            ns_builder = NamespaceToBuilderHelper.convert_namespace(ns_catalog, ns_name)
            namespace = ns_catalog.get_namespace(ns_name)
            if namespace.version is None:
                group_name = "%s/unversioned" % ns_name
            else:
                group_name = "%s/%s" % (ns_name, namespace.version)
            ns_group = spec_group.require_group(group_name)
            writer = ZarrSpecWriter(ns_group)
            ns_builder.export("namespace", writer=writer)

    @docval(
        *get_docval(HDMFIO.export),
        {"name": "cache_spec", "type": bool, "doc": "whether to cache the specification to file", "default": True},
        {
            "name": "number_of_jobs",
            "type": int,
            "doc": (
                "Number of jobs to use in parallel during write "
                "(only works with GenericDataChunkIterator-wrapped datasets)."
            ),
            "default": 1,
        },
        {
            "name": "max_threads_per_process",
            "type": int,
            "doc": "Limits the number of threads used by each process. The default is None (no limits).",
            "default": None,
        },
        {
            "name": "multiprocessing_context",
            "type": str,
            "doc": (
                "Context for multiprocessing. It can be None (default), 'fork' or 'spawn'. "
                "Note that 'fork' is only available on UNIX systems (not Windows)."
            ),
            "default": None,
        },
    )
    def export(self, **kwargs):
        """Export data read from a file from any backend to Zarr.
        See :py:meth:`hdmf.backends.io.HDMFIO.export` for more details.
        """
        if self.mode != "w":
            raise UnsupportedOperation(
                "Cannot export to file %s in mode '%s'. Please use mode 'w'." % (self.source, self.mode)
            )

        src_io = getargs("src_io", kwargs)
        write_args, cache_spec = popargs("write_args", "cache_spec", kwargs)
        number_of_jobs, max_threads_per_process, multiprocessing_context = popargs(
            "number_of_jobs", "max_threads_per_process", "multiprocessing_context", kwargs
        )

        self.__dci_queue = ZarrIODataChunkIteratorQueue(
            number_of_jobs=number_of_jobs,
            max_threads_per_process=max_threads_per_process,
            multiprocessing_context=multiprocessing_context,
        )

        if not isinstance(src_io, ZarrIO) and write_args.get("link_data", True):
            raise UnsupportedOperation(
                f"Cannot export from non-Zarr backend { src_io.__class__.__name__} "
                "to Zarr with write argument link_data=True. "
                "Set write_args={'link_data': False}"
            )

        write_args["export_source"] = src_io.source  # pass export_source=src_io.source to write_builder
        ckwargs = kwargs.copy()
        ckwargs["write_args"] = write_args
        if not write_args.get("link_data", True):
            ckwargs["clear_cache"] = True
        super().export(**ckwargs)
        if cache_spec:
            # add any namespaces from the src_io that have not yet been loaded
            for namespace in src_io.manager.namespace_catalog.namespaces:
                if namespace not in self.manager.namespace_catalog.namespaces:
                    self.manager.namespace_catalog.add_namespace(
                        name=namespace, namespace=src_io.manager.namespace_catalog.get_namespace(namespace)
                    )
            self.__cache_spec()

    def get_written(self, builder, check_on_disk=False):
        """
        Return True if this builder has been written to (or read from) disk by this IO object, False otherwise.

        :param builder: Builder object to get the written flag for
        :type builder: Builder
        :param check_on_disk: Check that the builder has been physically written to disk not just flagged as written
                              by this I/O backend
        :type check_on_disk: bool
        :return: True if the builder is found in self._written_builders using the builder ID, False otherwise. If
                 check_on_disk is enabled then the function cals get_builder_exists_on_disk in addition to verify
                 that the builder has indeed been written to disk.
        """
        written = self._written_builders.get_written(builder)
        if written and check_on_disk:
            written = written and self.get_builder_exists_on_disk(builder=builder)
        return written

    @docval({"name": "builder", "type": Builder, "doc": "The builder of interest"})
    def get_builder_exists_on_disk(self, **kwargs):
        """
        Convenience function to check whether a given builder exists on disk in this Zarr file.
        """
        builder = getargs("builder", kwargs)
        builder_path = self.get_builder_disk_path(builder=builder, filepath=None)
        exists_on_disk = os.path.exists(builder_path)
        return exists_on_disk

    @docval(
        {"name": "builder", "type": Builder, "doc": "The builder of interest"},
        {"name": "filepath", "type": str, "doc": "The path to the Zarr file or None for this file", "default": None},
    )
    def get_builder_disk_path(self, **kwargs):
        builder, filepath = getargs("builder", "filepath", kwargs)
        basepath = filepath if filepath is not None else self.source
        builder_path = os.path.join(basepath, self.__get_path(builder).lstrip("/"))
        return builder_path

    @docval(
        {"name": "builder", "type": GroupBuilder, "doc": "the GroupBuilder object representing the NWBFile"},
        {
            "name": "link_data",
            "type": bool,
            "doc": "If not specified otherwise link (True) or copy (False) Zarr Datasets",
            "default": True,
        },
        {
            "name": "exhaust_dci",
            "type": bool,
            "doc": (
                "Exhaust DataChunkIterators one at a time. If False, add "
                "them to the internal queue self.__dci_queue and exhaust them concurrently at the end"
            ),
            "default": True,
        },
        {
            "name": "export_source",
            "type": str,
            "doc": "The source of the builders when exporting",
            "default": None,
        },
        {
            "name": "consolidate_metadata",
            "type": bool,
            "doc": "Consolidate metadata into a single .zmetadata file in the root group to accelerate read.",
            "default": True,
        },
    )
    def write_builder(self, **kwargs):
        """Write a builder to disk."""
        f_builder, link_data, exhaust_dci, export_source, consolidate_metadata = getargs(
            "builder", "link_data", "exhaust_dci", "export_source", "consolidate_metadata", kwargs
        )
        for name, gbldr in f_builder.groups.items():
            self.write_group(
                parent=self.__file,
                builder=gbldr,
                link_data=link_data,
                exhaust_dci=exhaust_dci,
                export_source=export_source,
            )
        for name, dbldr in f_builder.datasets.items():
            self.write_dataset(
                parent=self.__file,
                builder=dbldr,
                link_data=link_data,
                exhaust_dci=exhaust_dci,
                export_source=export_source,
            )
        self.write_attributes(self.__file, f_builder.attributes)  # the same as set_attributes in HDMF
        self.__dci_queue.exhaust_queue()  # Write any remaining DataChunkIterators that have been queued
        self._written_builders.set_written(f_builder)
        self.logger.debug(
            "Done writing %s '%s' to path '%s'" % (f_builder.__class__.__qualname__, f_builder.name, self.source)
        )

        # Consolidate metadata for the entire file after everything has been written
        if consolidate_metadata:
            zarr.consolidate_metadata(store=self.path)

    @staticmethod
    def __get_store_path(store):
        """
        Method to retrieve the path from the Zarr storage.
        ConsolidatedMetadataStore wraps around other Zarr Store objects, requiring a check to
        retrieve the path.
        """
        if isinstance(store, zarr.storage.ConsolidatedMetadataStore):
            fpath = store.store.path
        else:
            fpath = store.path

        return fpath

    def __open_file_consolidated(self, store, mode, synchronizer=None, storage_options=None):
        """
        This method will check to see if the metadata has been consolidated.
        If so, use open_consolidated.
        """
        # This check is just a safeguard for possible errors in the future. But this should never happen
        if mode == "r-":
            raise ValueError("Mode r- not allowed for reading with consolidated metadata")
        try:
            return zarr.open_consolidated(
                store=store,
                mode=mode,
                synchronizer=synchronizer,
                storage_options=storage_options,
            )
        except KeyError:  # A KeyError is raised when the '/.zmetadata' does not exist
            return zarr.open(
                store=store,
                mode=mode,
                synchronizer=synchronizer,
                storage_options=storage_options,
            )

    @docval(
        {"name": "parent", "type": Group, "doc": "the parent Zarr object"},
        {"name": "builder", "type": GroupBuilder, "doc": "the GroupBuilder to write"},
        {
            "name": "link_data",
            "type": bool,
            "doc": "If not specified otherwise link (True) or copy (False) Zarr Datasets",
            "default": True,
        },
        {
            "name": "exhaust_dci",
            "type": bool,
            "doc": (
                "exhaust DataChunkIterators one at a time. If False, add "
                "them to the internal queue self.__dci_queue and exhaust them concurrently at the end"
            ),
            "default": True,
        },
        {"name": "export_source", "type": str, "doc": "The source of the builders when exporting", "default": None},
        returns="the Group that was created",
        rtype="Group",
    )
    def write_group(self, **kwargs):
        """Write a GroupBuider to file"""
        parent, builder, link_data, exhaust_dci, export_source = getargs(
            "parent", "builder", "link_data", "exhaust_dci", "export_source", kwargs
        )

        if self.get_written(builder):
            group = parent[builder.name]
        else:
            group = parent.require_group(builder.name)

        subgroups = builder.groups
        if subgroups:
            for subgroup_name, sub_builder in subgroups.items():
                self.write_group(
                    parent=group,
                    builder=sub_builder,
                    link_data=link_data,
                    exhaust_dci=exhaust_dci,
                    export_source=export_source,
                )

        datasets = builder.datasets
        if datasets:
            for dset_name, sub_builder in datasets.items():
                self.write_dataset(
                    parent=group,
                    builder=sub_builder,
                    link_data=link_data,
                    exhaust_dci=exhaust_dci,
                    export_source=export_source,
                )

        links = builder.links
        if links:
            for link_name, sub_builder in links.items():
                # Note: sub_builder is a LinkBuilder not the builder within.
                self.write_link(group, sub_builder, export_source)

        attributes = builder.attributes
        self.write_attributes(group, attributes)
        self._written_builders.set_written(builder)  # record that the builder has been written
        return group

    @docval(
        {"name": "obj", "type": (Group, Array), "doc": "the Zarr object to add attributes to"},
        {
            "name": "attributes",
            "type": dict,
            "doc": "a dict containing the attributes on the Group or Dataset, indexed by attribute name",
        },
    )
    def write_attributes(self, **kwargs):
        """Set (i.e., write) the attributes on a given Zarr Group or Array."""
        obj, attributes = getargs("obj", "attributes", kwargs)

        for key, value in attributes.items():
            # Case 1: list, set, tuple type attributes
            if isinstance(value, (set, list, tuple)) or (isinstance(value, np.ndarray) and np.ndim(value) != 0):
                # Convert to tuple for writing (e.g., numpy arrays are not JSON serializable)
                if isinstance(value, np.ndarray):
                    tmp = tuple(value.tolist())
                else:
                    tmp = tuple(value)
                # Attempt write of the attribute
                try:
                    obj.attrs[key] = tmp
                # Numpy scalars and bytes are not JSON serializable. Try to convert to a serializable type instead
                except TypeError as e:
                    try:
                        # TODO: refactor this to be more readable
                        tmp = tuple(
                            [
                                (
                                    i.item()
                                    if (isinstance(i, np.generic) and not isinstance(i, np.bytes_))
                                    else i.decode("utf-8") if isinstance(i, (bytes, np.bytes_)) else i
                                )
                                for i in value
                            ]
                        )
                        obj.attrs[key] = tmp
                    except:  # noqa: E722
                        raise TypeError(str(e) + " type=" + str(type(value)) + "  data=" + str(value)) from e
            # Case 2: References
            elif isinstance(value, (Builder, ReferenceBuilder)):
                refs = self._create_ref(value, ref_link_source=self.path)
                tmp = {"zarr_dtype": "object", "value": refs}
                obj.attrs[key] = tmp
            # Case 3: Scalar attributes
            else:
                # Attempt to write the attribute
                try:
                    obj.attrs[key] = value
                # Numpy scalars and bytes are not JSON serializable. Try to convert to a serializable type instead
                except TypeError as e:
                    try:
                        val = value.item if isinstance(value, np.ndarray) else value
                        # TODO: refactor this to be more readable
                        val = (
                            value.item()
                            if (isinstance(value, np.generic) and not isinstance(value, np.bytes_))
                            else val.decode("utf-8") if isinstance(value, (bytes, np.bytes_)) else val
                        )
                        obj.attrs[key] = val
                    except:  # noqa: E722
                        msg = str(e) + "key=" + key + " type=" + str(type(value)) + "  data=" + str(value)
                        raise TypeError(msg) from e

    def __get_path(self, builder):
        """Get the path to the builder.
        If builder.location is set then it is used as the path, otherwise the function
        determines the path by constructing it iteratively from the parents of the
        builder.
        """
        if builder.location is not None:
            path = os.path.normpath(os.path.join(builder.location, builder.name)).replace("\\", "/")
        else:
            curr = builder
            names = list()
            while curr is not None and curr.name != ROOT_NAME:
                names.append(curr.name)
                curr = curr.parent
            delim = "/"
            path = "%s%s" % (delim, delim.join(reversed(names)))
        return path

    @staticmethod
    def get_zarr_parent_path(zarr_object):
        """
        Get the absolute Unix path to the parent of a zarr_object from the root of the Zarr file
        :param zarr_object: Object for which we are looking up the path
        :type zarr_object: Zarr Group or Array
        :return: String with the path
        """
        parent_path = "/" + os.path.dirname(zarr_object.path).replace("\\", "/")
        return parent_path

    def __is_ref(self, dtype):
        if isinstance(dtype, DtypeSpec):
            return self.__is_ref(dtype.dtype)
        elif isinstance(dtype, RefSpec):
            return True
        elif isinstance(dtype, np.dtype):
            return False
        else:
            return dtype == DatasetBuilder.OBJECT_REF_TYPE

    def resolve_ref(self, zarr_ref):
        """
        Get the full path to the object linked to by the zarr reference

        The function only constructs the links to the targe object, but it does not check if the object exists

        :param zarr_ref: Dict with `source` and `path` keys or a `ZarrReference` object
        :return: 1) name of the target object
                 2) the target zarr object within the target file
        """
        # Extract the path as defined in the zarr_ref object
        if zarr_ref.get("source", None) is None:
            source_file = str(zarr_ref["path"])
        else:
            source_file = str(zarr_ref["source"])

        if not self.is_remote():
            if isinstance(self.source, str) and self.source.startswith(("s3://")):
                source_file = self.source
            else:
                # Join with source_file to resolve the relative path
                source_file = os.path.normpath(os.path.join(self.source, source_file))
        else:
            # get rid of extra "/" and "./" in the path root and source_file
            root_path = str(self.path).rstrip("/")
            source_path = str(source_file).lstrip(".")
            source_file = root_path + source_path

        object_path = zarr_ref.get("path", None)
        if object_path:
            target_name = os.path.basename(object_path)
        else:
            target_name = ROOT_NAME

        target_zarr_obj = self.__open_file_consolidated(
            store=source_file,
            mode="r",
            storage_options=self.__storage_options,
        )
        if object_path is not None:
            try:
                target_zarr_obj = target_zarr_obj[object_path]
            except Exception:
                raise ValueError("Found bad link to object %s in file %s" % (object_path, source_file))
        # Return the create path
        return target_name, target_zarr_obj

    def _create_ref(self, ref_object, ref_link_source=None):
        """
        Create a ZarrReference object that points to the given container

        :param ref_object: the object to be referenced
        :type ref_object: Builder, Container, ReferenceBuilder
        :returns: ZarrReference object
        """
        if isinstance(ref_object, Builder):
            if isinstance(ref_object, LinkBuilder):
                builder = ref_object.builder
            else:
                builder = ref_object
        elif isinstance(ref_object, ReferenceBuilder):
            builder = ref_object.builder

        path = self.__get_path(builder)  # This is the internal path in the store to the item.

        # get the object id if available
        object_id = builder.get("object_id", None)
        # determine the object_id of the source by following the parents of the builder until we find the root
        # the root builder should be the same as the source file containing the reference
        curr = builder
        while curr is not None and curr.name != ROOT_NAME:
            curr = curr.parent

        if curr:
            source_object_id = curr.get("object_id", None)
        # We did not find ROOT_NAME as a parent. This should only happen if we have an invalid
        # file as a source, e.g., if during testing we use an arbitrary builder. We check this
        # anyways to avoid potential errors just in case
        else:
            source_object_id = None
            warn_msg = "Could not determine source_object_id for builder with path: %s" % path
            warnings.warn(warn_msg)

        # by checking os.isdir makes sure we have a valid link path to a dir for Zarr. For conversion
        # between backends a user should always use export which takes care of creating a clean set of builders.
        if ref_link_source is None:
            # TODO: Refactor appending a dataset of references so this doesn't need to be called.
            ref_link_source = (
                builder.source if (builder.source is not None and os.path.isdir(builder.source)) else self.source
            )

        if not isinstance(ref_link_source, str):
            # self.path is sometimes given as the ref_link_source. It can
            # be either a (str, Path, *SUPPORTED_ZARR_STORES). That being said,
            # when self.path is a Path, it is converted to a str in __init__.
            # We only have to deal with *SUPPORTED_ZARR_STORES and strings.
            ref_link_source = ref_link_source.path

        # Note: We want want to construct the relative path with
        # os.path.relpath(<absolute_path_to_the_target>, <absolute_path_to_the_file_that_is_being_exported_to>)
        # That being said, we want to avoid a reference being defined as '.' because '.' means whatever file you
        # are in. This does not help if you are trying to access a link/ref in another file and the source says
        # '.' so look in yourself. That is why the dirname is there.

        # Note: Don't use just os.path.relpath() with just a single arg, i.e., source. This will make the
        # path relative to the working directory. We want it relative to where it lives in the file system.
        if not isinstance(self.path, str):
            str_path = self.path.path
        else:
            str_path = self.path
        rel_source = os.path.relpath(os.path.abspath(ref_link_source), os.path.abspath(str_path))

        # Return the ZarrReference object
        ref = ZarrReference(
            source=rel_source,
            path=path,
            object_id=object_id,
            source_object_id=source_object_id,
        )
        return ref

    def __add_link__(self, parent, target_source, target_path, link_name):
        """
        Add a link to the file
        :param parent: The parent Zarr group containing the link
        :type parent: zarr.hierarchy.Group
        :param target_source: Source path within the Zarr file to the linked object
        :type target_source: str
        :param target_path: Path to the Zarr file containing the linked object
        :param link_name: Name of the link
        :type link_name: str
        """
        if "zarr_link" not in parent.attrs:
            parent.attrs["zarr_link"] = []
        zarr_link = list(parent.attrs["zarr_link"])
        if not isinstance(target_source, str):  # a store
            target_source = target_source.path
        zarr_link.append({"source": target_source, "path": target_path, "name": link_name})
        parent.attrs["zarr_link"] = zarr_link

    @docval(
        {"name": "parent", "type": Group, "doc": "the parent Zarr object"},
        {"name": "builder", "type": LinkBuilder, "doc": "the LinkBuilder to write"},
        {"name": "export_source", "type": str, "doc": "The source of the builders when exporting", "default": None},
    )
    def write_link(self, **kwargs):
        parent, builder, export_source = getargs("parent", "builder", "export_source", kwargs)
        if self.get_written(builder):
            self.logger.debug(
                "Skipping LinkBuilder '%s' already written to parent group '%s'" % (builder.name, parent.name)
            )
            return
        self.logger.debug("Writing LinkBuilder '%s' to parent group '%s'" % (builder.name, parent.name))

        target_builder = builder.builder

        group_filename = self.__get_store_path(parent.store)
        if export_source is not None:
            if target_builder.source in (group_filename, export_source):
                # Case 1:
                # target_builder.source == export_source
                # This means we have a SoftLink for a group and so we want the exported link to
                # also point "inwards" in the file being created.
                #################################
                # Case 2:
                # target_builder.source == group_filename
                # This is still a SoftLink; however, it is from adding a link to a group after FileA
                # has been read and we are exporting that to FileB. We still want the link to be "inwards".
                ref_link_source = group_filename
            else:
                # Create an ExternalLink to whatever file that has what we are targeting.
                ref_link_source = target_builder.source
        else:
            # This is when we are not exporting and so export_source will be None.
            # We use target_builder.source instead of builder source in case we creating an external link
            # during write.
            ref_link_source = target_builder.source

        name = builder.name
        # Get the reference
        zarr_ref = self._create_ref(builder, ref_link_source=ref_link_source)

        self.__add_link__(parent, zarr_ref.source, zarr_ref.path, name)
        self._written_builders.set_written(builder)  # record that the builder has been written

    @classmethod
    def __setup_chunked_dataset__(cls, parent, name, data, options=None):
        """
        Setup a dataset for writing to one-chunk-at-a-time based on the given DataChunkIterator. This
        is a helper function for write_dataset()
        :param parent: The parent object to which the dataset should be added
        :type parent: Zarr Group or File
        :param name: The name of the dataset
        :type name: str
        :param data: The data to be written.
        :type data: AbstractDataChunkIterator
        :param options: Dict with options for creating a dataset. available options are 'dtype' and 'io_settings'
        :type options: dict
        """
        io_settings = {}
        if options is not None:
            if "io_settings" in options:
                io_settings = options.get("io_settings")
        # Define the chunking options if the user has not set them explicitly. We need chunking for the iterative write.
        if "chunks" not in io_settings:
            recommended_chunks = data.recommended_chunk_shape()
            io_settings["chunks"] = True if recommended_chunks is None else recommended_chunks
        # Define the shape of the data if not provided by the user
        if "shape" not in io_settings:
            io_settings["shape"] = data.recommended_data_shape()
        if "dtype" not in io_settings:
            if (options is not None) and ("dtype" in options):
                io_settings["dtype"] = options["dtype"]
            else:
                io_settings["dtype"] = data.dtype
            if isinstance(io_settings["dtype"], str):
                # map to real dtype if we were given a string
                io_settings["dtype"] = cls.__dtypes.get(io_settings["dtype"])
        try:
            dset = parent.create_dataset(name, **io_settings)
            dset.attrs["zarr_dtype"] = np.dtype(io_settings["dtype"]).str
        except Exception as exc:
            raise Exception("Could not create dataset %s in %s" % (name, parent.name)) from exc
        return dset

    @docval(
        {"name": "parent", "type": Group, "doc": "the parent Zarr object"},  # noqa: C901
        {"name": "builder", "type": DatasetBuilder, "doc": "the DatasetBuilder to write"},
        {
            "name": "link_data",
            "type": bool,
            "doc": "If not specified otherwise link (True) or copy (False) Zarr Datasets",
            "default": True,
        },
        {
            "name": "exhaust_dci",
            "type": bool,
            "doc": (
                "exhaust DataChunkIterators one at a time. If False, add "
                "them to the internal queue self.__dci_queue and exhaust them concurrently at the end"
            ),
            "default": True,
        },
        {
            "name": "force_data",
            "type": None,
            "doc": "Used internally to force the data being used when we have to load the data",
            "default": None,
        },
        {"name": "export_source", "type": str, "doc": "The source of the builders when exporting", "default": None},
        returns="the Zarr array that was created",
        rtype=Array,
    )
    def write_dataset(self, **kwargs):  # noqa: C901
        parent, builder, link_data, exhaust_dci, export_source = getargs(
            "parent", "builder", "link_data", "exhaust_dci", "export_source", kwargs
        )

        force_data = getargs("force_data", kwargs)

        if exhaust_dci and self.__dci_queue is None:
            self.__dci_queue = ZarrIODataChunkIteratorQueue()

        if self.get_written(builder):
            return None
        name = builder.name
        data = builder.data if force_data is None else force_data
        options = dict()
        # Check if data is a h5py.Dataset to infer I/O settings if necessary
        if ZarrDataIO.is_h5py_dataset(data):
            # Wrap the h5py.Dataset in ZarrDataIO with chunking and compression settings inferred from the input data
            data = ZarrDataIO.from_h5py_dataset(h5dataset=data)
        # Separate data values and io_settings for write
        if isinstance(data, ZarrDataIO):
            options["io_settings"] = data.io_settings
            link_data = data.link_data
            data = data.data
        else:
            options["io_settings"] = {}

        if builder.dimension_labels is not None:
            builder.attributes["_ARRAY_DIMENSIONS"] = builder.dimension_labels

        attributes = builder.attributes
        options["dtype"] = builder.dtype

        linked = False

        # Write a regular Zarr array
        dset = None
        if isinstance(data, Array):
            # copy the dataset
            data_filename = self.__get_store_path(data.store)
            str_path = self.path
            if not isinstance(str_path, str):  # a store
                str_path = self.path.path
            rel_data_filename = os.path.relpath(os.path.abspath(data_filename), os.path.abspath(str_path))
            if link_data:
                if export_source is None:  # not exporting
                    self.__add_link__(parent, rel_data_filename, data.name, name)
                    linked = True
                    dset = None
                else:  # exporting
                    data_parent = "/".join(data.name.split("/")[:-1])
                    # Case 1: The dataset is NOT in the export source, create a link to preserve the external link.
                    # I have three files, FileA, FileB, FileC. I want to export FileA to FileB. FileA has an
                    # EXTERNAL link to a dataset in Filec. This case preserves the link to FileC to also be in FileB.
                    if data_filename != export_source:
                        self.__add_link__(parent, rel_data_filename, data.name, name)
                        linked = True
                        dset = None
                    # Case 2: If the dataset is in the export source and has a DIFFERENT path as the builder,
                    # then create a link.
                    # I have two files: FileA and FileB. I want to export FileA to FileB. FileA has an
                    # INTERNAL link. This case preserves the link to also be in FileB.
                    ###############
                    elif parent.name != data_parent:
                        self.__add_link__(parent, ".", data.name, name)
                        linked = True
                        dset = None

                    ###############
                    # Case 3: The dataset is in the export source and has the SAME path as the builder, so copy.
                    ###############
                    else:
                        zarr.copy(data, parent, name=name)
                        dset = parent[name]
            else:
                zarr.copy(data, parent, name=name)
                dset = parent[name]
        # When converting data between backends we may see an HDMFDataset, e.g., a H55ReferenceDataset, with references
        elif isinstance(data, HDMFDataset):
            # If we have a dataset of containers we need to make the references to the containers
            if len(data) > 0 and isinstance(data[0], Container):
                ref_data = [self._create_ref(data[i], ref_link_source=self.path) for i in range(len(data))]
                shape = (len(data),)
                type_str = "object"
                dset = parent.require_dataset(
                    name,
                    shape=shape,
                    dtype=object,
                    object_codec=self.__codec_cls(),
                    **options["io_settings"],
                )
                dset.attrs["zarr_dtype"] = type_str
                dset[:] = ref_data
                self._written_builders.set_written(builder)  # record that the builder has been written
            # If we have a regular dataset, then load the data and write the builder after load
            else:
                # TODO This code path is also exercised when data is a
                # hdmf.backends.hdf5.h5_utils.BuilderH5ReferenceDataset (aka.  ReferenceResolver)
                # check that this is indeed the right thing to do here

                # We can/should not update the data in the builder itself so we load the data here and instead
                # force write_dataset when we call it recursively to use the data we loaded, rather than the
                # dataset that is set on the builder
                dset = self.write_dataset(
                    parent=parent,
                    builder=builder,
                    link_data=link_data,
                    force_data=data[:],
                    export_source=export_source,
                )
                self._written_builders.set_written(builder)  # record that the builder has been written
        # Write a compound dataset
        elif isinstance(options["dtype"], list):
            refs = list()
            type_str = list()
            for i, dts in enumerate(options["dtype"]):
                if self.__is_ref(dts["dtype"]):
                    refs.append(i)
                    type_str.append({"name": dts["name"], "dtype": "object"})
                else:
                    i = [
                        dts,
                    ]
                    t = self.__resolve_dtype_helper__(i)
                    type_str.append(self.__serial_dtype__(t)[0])

            if len(refs) > 0:

                self._written_builders.set_written(builder)  # record that the builder has been written

                # gather items to write
                new_items = []
                for j, item in enumerate(data):
                    new_item = list(item)
                    for i in refs:
                        new_item[i] = self._create_ref(item[i], ref_link_source=self.path)
                    new_items.append(tuple(new_item))

                # Create dtype for storage, replacing values to match hdmf's hdf5 behavior
                # ---
                # TODO: Replace with a simple one-liner once __resolve_dtype_helper__ is
                # compatible with zarr's need for fixed-length string dtypes.
                # dtype = self.__resolve_dtype_helper__(options['dtype'])

                new_dtype = []
                for field in options["dtype"]:
                    if field["dtype"] is str or field["dtype"] in (
                        "str",
                        "text",
                        "utf",
                        "utf8",
                        "utf-8",
                        "isodatetime",
                    ):
                        # Zarr does not support variable length strings
                        new_dtype.append((field["name"], "O"))
                    elif isinstance(field["dtype"], dict):
                        # eg. for some references, dtype will be of the form
                        # {'target_type': 'Baz', 'reftype': 'object'}
                        # which should just get serialized as an object
                        new_dtype.append((field["name"], "O"))
                    else:
                        new_dtype.append((field["name"], self.__resolve_dtype_helper__(field["dtype"])))
                dtype = np.dtype(new_dtype)

                # cast and store compound dataset
                arr = np.array(new_items, dtype=dtype)
                dset = parent.require_dataset(
                    name,
                    shape=(len(arr),),
                    dtype=dtype,
                    object_codec=self.__codec_cls(),
                    **options["io_settings"],
                )
                dset.attrs["zarr_dtype"] = type_str
                dset[...] = arr
            else:
                # write a compound datatype
                dset = self.__list_fill__(parent, name, data, options)
        # Write a dataset of references
        elif self.__is_ref(options["dtype"]):
            # Note: ref_link_source is set to self.path because we do not do external references
            # We only support external links.
            if isinstance(data, ReferenceBuilder):
                shape = (1,)
                type_str = "object"
                refs = self._create_ref(data, ref_link_source=self.path)
            else:
                shape = (len(data),)
                type_str = "object"
                refs = [self._create_ref(item, ref_link_source=self.path) for item in data]

            dset = parent.require_dataset(
                name,
                shape=shape,
                dtype=object,
                object_codec=self.__codec_cls(),
                **options["io_settings"],
            )
            self._written_builders.set_written(builder)  # record that the builder has been written
            dset.attrs["zarr_dtype"] = type_str
            if hasattr(refs, "__len__"):
                dset[:] = np.array(refs)
            else:
                dset[0] = refs
        # write a 'regular' dataset without DatasetIO info
        else:
            if isinstance(data, (str, bytes)):
                dset = self.__scalar_fill__(parent, name, data, options)
            # Iterative write of a data chunk iterator
            elif isinstance(data, AbstractDataChunkIterator):
                dset = self.__setup_chunked_dataset__(parent, name, data, options)
                self.__dci_queue.append(dataset=dset, data=data)
            elif hasattr(data, "__len__"):
                dset = self.__list_fill__(parent, name, data, options)
            else:
                dset = self.__scalar_fill__(parent, name, data, options)
        if not linked:
            self.write_attributes(dset, attributes)
        # record that the builder has been written
        self._written_builders.set_written(builder)
        # Exhaust the DataChunkIterator if the dataset was given this way. Note this is a no-op
        # if the self.__dci_queue is empty
        if exhaust_dci:
            self.__dci_queue.exhaust_queue()
        return dset

    __dtypes = {
        "float": np.float32,
        "float32": np.float32,
        "double": np.float64,
        "float64": np.float64,
        "long": np.int64,
        "int64": np.int64,
        "uint64": np.uint64,
        "int": np.int32,
        "int32": np.int32,
        "int16": np.int16,
        "int8": np.int8,
        "bool": np.bool_,
        "bool_": np.bool_,
        "text": str,
        "utf": str,
        "utf8": str,
        "utf-8": str,
        "ascii": bytes,
        "bytes": bytes,
        "str": str,
        "isodatetime": str,
        "string_": bytes,
        "uint32": np.uint32,
        "uint16": np.uint16,
        "uint8": np.uint8,
        "ref": ZarrReference,
        "reference": ZarrReference,
        "object": ZarrReference,
    }

    @classmethod
    def __serial_dtype__(cls, dtype):
        if isinstance(dtype, type):
            return dtype.__name__
        elif isinstance(dtype, np.dtype):
            if dtype.names is None:
                return dtype.type.__name__
            else:
                ret = list()
                for n in dtype.names:
                    item = dict()
                    item["name"] = n
                    item["dtype"] = cls.__serial_dtype__(dtype[n])
                    ret.append(item)
                return ret
        # TODO Does not work when Reference in compound datatype
        elif dtype == ZarrReference:
            return "object"

    @classmethod
    def __resolve_dtype__(cls, dtype, data):
        dtype = cls.__resolve_dtype_helper__(dtype)
        if dtype is None:
            dtype = cls.get_type(data)
        return dtype

    @classmethod
    def __resolve_dtype_helper__(cls, dtype):
        if dtype is None:
            return None
        elif isinstance(dtype, (type, np.dtype)):
            return dtype
        elif isinstance(dtype, str):
            return cls.__dtypes.get(dtype)
        elif isinstance(dtype, dict):
            return cls.__dtypes.get(dtype["reftype"])
        elif isinstance(dtype, list):
            return np.dtype([(x["name"], cls.__resolve_dtype_helper__(x["dtype"])) for x in dtype])
        else:
            raise ValueError(f"Can't resolve dtype {dtype}")

    @classmethod
    def get_type(cls, data):
        if isinstance(data, str):
            return cls.__dtypes.get("str")
        elif isinstance(data, bytes):
            return cls.__dtypes.get("bytes")
        elif not hasattr(data, "__len__"):
            return type(data)
        else:
            if len(data) == 0:
                raise ValueError("cannot determine type for empty data")
            return cls.get_type(data[0])

    __reserve_attribute = ("zarr_dtype", "zarr_link")

    def __list_fill__(self, parent, name, data, options=None):  # noqa: C901
        dtype = None
        io_settings = dict()
        if options is not None:
            dtype = options.get("dtype")
            if options.get("io_settings") is not None:
                io_settings = options.get("io_settings")
        # Determine the dtype
        if not isinstance(dtype, type):
            try:
                dtype = self.__resolve_dtype__(dtype, data)
            except Exception as exc:
                msg = "cannot add %s to %s - could not determine type" % (name, parent.name)  # noqa: F821
                raise Exception(msg) from exc

        # Set the type_str
        type_str = self.__serial_dtype__(dtype)

        # Determine the shape and update the dtype if necessary when dtype==object
        if "shape" in io_settings:  # Use the shape set by the user
            data_shape = io_settings.pop("shape")
        # If we have a numeric numpy-like array (e.g., numpy.array or h5py.Dataset) then use its shape
        elif isinstance(dtype, np.dtype) and np.issubdtype(dtype, np.number) or dtype == np.bool_:
            # HDMF's get_data_shape may return the maxshape of an HDF5 dataset which can include None values
            # which Zarr does not allow for dataset shape. Check for the shape attribute first before falling
            # back on get_data_shape
            if hasattr(data, "shape") and data.shape is not None:
                data_shape = data.shape
            # This is a fall-back just in case. However this should not happen for standard numpy and h5py arrays
            else:  # pragma: no cover
                data_shape = get_data_shape(data)  # pragma: no cover
        # Deal with object dtype
        elif isinstance(dtype, np.dtype):
            data = data[:]  # load the data in case we come from HDF5 or another on-disk data source we don't know
            data_shape = (len(data),)
            # if we have a compound data type
            if dtype.names:
                data_shape = get_data_shape(data)
                # If strings are part of our compound type then we need to use Object type instead
                # otherwise we try to keep the native compound datatype that numpy is using
                for substype in dtype.fields.items():
                    if np.issubdtype(substype[1][0], np.flexible) or np.issubdtype(substype[1][0], np.object_):
                        dtype = object
                        io_settings["object_codec"] = self.__codec_cls()
                        break
            # sometimes bytes and strings can hide as object in numpy array so lets try
            # to write those as strings and bytes rather than as objects
            elif len(data) > 0 and isinstance(data, np.ndarray):
                if isinstance(data.item(0), bytes):
                    dtype = bytes
                    data_shape = get_data_shape(data)
                elif isinstance(data.item(0), str):
                    dtype = str
                    data_shape = get_data_shape(data)
            # Set encoding for objects
            else:
                dtype = object
                io_settings["object_codec"] = self.__codec_cls()
        # Determine the shape from the data if all other cases have not been hit
        else:
            data_shape = get_data_shape(data)

        # Create the dataset
        dset = parent.require_dataset(name, shape=data_shape, dtype=dtype, **io_settings)
        dset.attrs["zarr_dtype"] = type_str

        # Write the data to file
        if dtype == object:  # noqa: E721
            for c in np.ndindex(data_shape):
                o = data
                for i in c:
                    o = o[i]
                # bytes are not JSON serializable
                dset[c] = o if not isinstance(o, (bytes, np.bytes_)) else o.decode("utf-8")
            return dset
        # standard write
        else:
            try:
                dset[:] = np.array(data)
            # If data is an h5py.Dataset then this will copy the data
            # For compound data types containing strings Zarr sometimes does not like writing multiple values
            # try to write them one-at-a-time instead then
            except ValueError:
                for i in range(len(data)):
                    dset[i] = data[i]
            except TypeError:  # If data is an h5py.Dataset with strings, they may need to be decoded
                for c in np.ndindex(data_shape):
                    o = data
                    for i in c:
                        o = o[i]
                    # bytes are not JSON serializable
                    dset[c] = o if not isinstance(o, (bytes, np.bytes_)) else o.decode("utf-8")
        return dset

    def __scalar_fill__(self, parent, name, data, options=None):
        dtype = None
        io_settings = dict()
        if options is not None:
            dtype = options.get("dtype")
            io_settings = options.get("io_settings")
            if io_settings is None:
                io_settings = dict()
        if not isinstance(dtype, type):
            try:
                dtype = self.__resolve_dtype__(dtype, data)
            except Exception as exc:
                msg = "cannot add %s to %s - could not determine type" % (name, parent.name)
                raise Exception(msg) from exc
        if dtype == object:  # noqa: E721
            io_settings["object_codec"] = self.__codec_cls()

        dset = parent.require_dataset(name, shape=(1,), dtype=dtype, **io_settings)
        dset[:] = data
        type_str = "scalar"
        dset.attrs["zarr_dtype"] = type_str
        return dset

    @docval(returns="a GroupBuilder representing the NWB Dataset", rtype="GroupBuilder")
    def read_builder(self):
        f_builder = self.__read_group(self.__file, ROOT_NAME)
        return f_builder

    def __set_built(self, zarr_obj, builder):
        fpath = self.__get_store_path(zarr_obj.store)
        path = zarr_obj.path
        path = os.path.join(fpath, path)
        self.__built.setdefault(path, builder)

    @docval(
        {
            "name": "zarr_obj",
            "type": (Array, Group),
            "doc": "the Zarr object to the corresponding Container/Data object for",
        }
    )
    def get_container(self, **kwargs):
        """
        Get the container for the corresponding Zarr Group or Dataset

        :raises ValueError: When no builder has been constructed yet for the given h5py object
        """
        zarr_obj = getargs("zarr_obj", kwargs)
        builder = self.get_builder(zarr_obj)
        container = self.manager.construct(builder)
        return container  # TODO: This method should be moved to HDMFIO

    @docval(
        {"name": "zarr_obj", "type": (Array, Group), "doc": "the Zarr object to the corresponding Builder object for"}
    )
    def get_builder(self, **kwargs):  # TODO: move this to HDMFIO (define skeleton in there at least)
        """
        Get the builder for the corresponding Group or Dataset

        :raises ValueError: When no builder has been constructed
        """
        zarr_obj = kwargs["zarr_obj"]
        builder = self.__get_built(zarr_obj)
        if builder is None:
            msg = "%s has not been built" % (zarr_obj.name)
            raise ValueError(msg)
        return builder

    def __get_built(self, zarr_obj):
        """
        Look up a builder for the given zarr object
        :param zarr_obj: The Zarr object to be built
        :type zarr_obj: Zarr Group or Dataset
        :return: Builder in the self.__built cache or None
        """

        fpath = self.__get_store_path(zarr_obj.store)
        path = zarr_obj.path
        path = os.path.join(fpath, path)
        return self.__built.get(path, None)

    def __read_group(self, zarr_obj, name=None):
        ret = self.__get_built(zarr_obj)
        if ret is not None:
            return ret

        if name is None:
            name = str(os.path.basename(zarr_obj.name))

        # Note: The source should be from the zarr object and not assumed to be
        # from the file being read.
        if isinstance(zarr_obj.store, ConsolidatedMetadataStore):
            source = zarr_obj.store.store.path
        else:
            source = zarr_obj.store.path

        # Create the GroupBuilder
        attributes = self.__read_attrs(zarr_obj)
        ret = GroupBuilder(name=name, source=source, attributes=attributes)
        ret.location = ZarrIO.get_zarr_parent_path(zarr_obj)

        # read sub groups
        for sub_name, sub_group in zarr_obj.groups():
            sub_builder = self.__read_group(sub_group, sub_name)
            ret.set_group(sub_builder)

        # read sub datasets
        for sub_name, sub_array in zarr_obj.arrays():
            sub_builder = self.__read_dataset(sub_array, sub_name)
            ret.set_dataset(sub_builder)

        # read the links
        self.__read_links(zarr_obj=zarr_obj, parent=ret)

        self._written_builders.set_written(ret)  # record that the builder has been written
        self.__set_built(zarr_obj, ret)
        return ret

    def __read_links(self, zarr_obj, parent):
        """
        Read the links associated with a zarr group
        :param zarr_obj: The Zarr group we should read links from
        :type zarr_obj: zarr.hierarchy.Group
        :param parent: GroupBuilder with which the links need to be associated
        :type parent: GroupBuilder
        """
        # read links
        if "zarr_link" in zarr_obj.attrs:
            links = zarr_obj.attrs["zarr_link"]
            for link in links:
                link_name = link["name"]
                target_name, target_zarr_obj = self.resolve_ref(link)
                # NOTE: __read_group and __read_dataset return the cached builders if the target has already been built
                if isinstance(target_zarr_obj, Group):
                    builder = self.__read_group(target_zarr_obj, target_name)
                else:
                    builder = self.__read_dataset(target_zarr_obj, target_name)
                link_builder = LinkBuilder(builder=builder, name=link_name, source=self.source)
                link_builder.location = os.path.join(parent.location, parent.name)
                self._written_builders.set_written(link_builder)  # record that the builder has been written
                parent.set_link(link_builder)

    def __read_dataset(self, zarr_obj, name):
        ret = self.__get_built(zarr_obj)
        if ret is not None:
            return ret

        if "zarr_dtype" in zarr_obj.attrs:
            zarr_dtype = zarr_obj.attrs["zarr_dtype"]
        elif hasattr(zarr_obj, "dtype"):  # Fallback for invalid files that are missing zarr_type
            zarr_dtype = zarr_obj.dtype
            warnings.warn(
                "Inferred dtype from zarr type. Dataset missing zarr_dtype: " + str(name) + "   " + str(zarr_obj)
            )
        else:
            raise ValueError("Dataset missing zarr_dtype: " + str(name) + "   " + str(zarr_obj))

        if isinstance(zarr_obj.store, ConsolidatedMetadataStore):
            source = zarr_obj.store.store.path
        else:
            source = zarr_obj.store.path

        kwargs = {
            "attributes": self.__read_attrs(zarr_obj),
            "dtype": zarr_dtype,
            "maxshape": zarr_obj.shape,
            "chunks": not (zarr_obj.shape == zarr_obj.chunks),
            "source": source,
        }
        dtype = kwargs["dtype"]

        # By default, use the zarr.core.Array as data for lazy data load
        data = zarr_obj

        # Read scalar dataset
        if dtype == "scalar":
            data = zarr_obj[()]

        if isinstance(dtype, list):
            # Check compound dataset where one of the subsets contains references
            has_reference = False
            for i, dts in enumerate(dtype):
                if dts["dtype"] == "object":  # check items for object reference
                    has_reference = True
                    break
            retrieved_dtypes = [dtype_dict["dtype"] for dtype_dict in dtype]
            if has_reference:
                data = BuilderZarrTableDataset(zarr_obj, self, retrieved_dtypes)
        elif self.__is_ref(dtype):
            # Array of references
            data = BuilderZarrReferenceDataset(data, self)

        kwargs["data"] = data
        if name is None:
            name = str(os.path.basename(zarr_obj.name))
        ret = DatasetBuilder(name, **kwargs)  # create builder object for dataset
        ret.location = ZarrIO.get_zarr_parent_path(zarr_obj)
        self._written_builders.set_written(ret)  # record that the builder has been written
        self.__set_built(zarr_obj, ret)
        return ret

    def __read_attrs(self, zarr_obj):
        ret = dict()
        for k in zarr_obj.attrs.keys():
            if k not in self.__reserve_attribute:
                v = zarr_obj.attrs[k]
                if isinstance(v, dict) and "zarr_dtype" in v:
                    if v["zarr_dtype"] == "object":
                        target_name, target_zarr_obj = self.resolve_ref(v["value"])
                        if isinstance(target_zarr_obj, zarr.hierarchy.Group):
                            ret[k] = self.__read_group(target_zarr_obj, target_name)
                        else:
                            ret[k] = self.__read_dataset(target_zarr_obj, target_name)
                    else:
                        raise NotImplementedError("Unsupported zarr_dtype for attribute " + str(v))
                else:
                    ret[k] = v
        return ret
