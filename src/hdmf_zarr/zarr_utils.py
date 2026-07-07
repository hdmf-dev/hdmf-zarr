"""
Utilities for the Zarr I/O backend,
e.g., for wrapping Zarr arrays on read, wrapping arrays for configuring write, or
writing the spec among others
"""

import json
from abc import ABCMeta, abstractmethod
from copy import copy
import numpy as np

from zarr import Array

from hdmf.build import DatasetBuilder
from hdmf.data_utils import append_data
from hdmf.query import HDMFDataset, ReferenceResolver, ContainerResolver, BuilderResolver
from hdmf.utils import docval, popargs, get_docval


class ZarrDataset(HDMFDataset):
    """
    Extension of HDMFDataset to add Zarr compatibility
    """

    @docval(
        {"name": "dataset", "type": (np.ndarray, Array), "doc": "the Zarr file lazily evaluate"},
        {"name": "io", "type": "ZarrIO", "doc": "the IO object that was used to read the underlying dataset"},
    )
    def __init__(self, **kwargs):
        self.__io = popargs("io", kwargs)
        super().__init__(**kwargs)

    @property
    def io(self):
        return self.__io

    def __len__(self):
        # In zarr v3, Array does not implement __len__
        return self.dataset.shape[0]

    @property
    def shape(self):
        return self.dataset.shape


class ZarrStringDataset(ZarrDataset):
    """
    Lazy wrapper for Zarr arrays whose dtype is ``numpy.dtypes.StringDType``.

    In zarr-python v3, variable-length string datasets are stored with numpy's
    ``StringDType``. Neither h5py nor HDMF's generic dtype inference handle that
    dtype directly, so on read we wrap the array in this class instead of
    materializing it (e.g. ``list(zarr_obj[:])``). Materializing would pull an
    entire (potentially millions-of-entries) column into memory on open and, for
    multidimensional arrays, would collapse to a list of row arrays that no longer
    supports ``data[i, j]`` indexing or exposes ``shape``/``dtype``.

    Accessed elements are decoded to native Python ``str`` on demand so that other
    backends (e.g. ``HDF5IO``) can consume them while chunked/lazy access is
    preserved. ``dtype`` is reported as object so HDMF infers a ``utf8`` (variable
    length string) type when re-building the dataset.
    """

    @property
    def dtype(self):
        return np.dtype(object)

    def __getitem__(self, arg):
        value = self.dataset[arg]
        if isinstance(value, np.ndarray):
            # Convert StringDType -> object array of native Python str, preserving shape
            return value.astype(object)
        # Single element access returns a scalar Python str
        return str(value)

    def __array__(self, dtype=None):
        # Support np.asarray(...) used by consumers such as h5py during export
        arr = self.dataset[:].astype(object)
        return arr.astype(dtype) if dtype is not None else arr


class DatasetOfReferences(ZarrDataset, ReferenceResolver, metaclass=ABCMeta):
    """
    An extension of the base ReferenceResolver class to add more abstract methods for
    subclasses that will read Zarr references
    """

    @abstractmethod
    def get_object(self, zarr_obj):
        """
        A class that maps an Zarr object to a Builder or Container
        """
        pass

    def invert(self):
        """
        Return an object that defers reference resolution
        but in the opposite direction.
        """
        if not hasattr(self, "__inverted"):
            cls = self.get_inverse_class()
            docval = get_docval(cls.__init__)
            kwargs = dict()
            for arg in docval:
                kwargs[arg["name"]] = getattr(self, arg["name"])
            self.__inverted = cls(**kwargs)
        return self.__inverted

    def _get_ref(self, ref):
        # In zarr v3, references may be stored as JSON strings
        if isinstance(ref, str):
            try:
                ref = json.loads(ref)
            except (json.JSONDecodeError, TypeError):
                pass
        name, zarr_obj = self.io.resolve_ref(ref)  # ref is a json dict containing the path to the object
        return self.get_object(zarr_obj)

    def __iter__(self):
        for ref in super().__iter__():
            yield self._get_ref(ref)

    def __next__(self):
        return self._get_ref(super().__next__())

    def append(self, arg):
        # Building the root parent first.
        # (Doing so will correctly set the parent of the child builder, which is needed to create the reference)
        # Note: If the arg is a nested child such that objB is the parent of arg and objA is the parent of objB
        # (and objA is not the root), then we need to have objA already added to the root as a child. Otherwise,
        # the loop will use objA as the root. This might not raise an error (meaning the path could be correct),
        # but it could lead to having an incorrect path for the reference.
        # Having objA NOT be an orphaned container ensures correct functionality.
        child = arg
        while True:
            if child.parent is not None:
                parent = child.parent
                child = parent
            else:
                parent = child
                break
        self.io.manager.build(parent)
        builder = self.io.manager.build(arg)

        # Create ZarrReference
        ref = self.io._create_ref(builder)
        # In zarr v3, serialize as JSON string
        ref_str = json.dumps(dict(ref))
        append_data(self.dataset, ref_str)


class BuilderResolverMixin(BuilderResolver):  # refactor to backend/utils.py
    """
    A mixin for adding to Zarr reference-resolving types
    the get_object method that returns Builders
    """

    def get_object(self, zarr_obj):
        """
        A class that maps an Zarr object to a Builder
        """
        return self.io.get_builder(zarr_obj)


class ContainerResolverMixin(ContainerResolver):  # refactor to backend/utils.py
    """
    A mixin for adding to Zarr reference-resolving types
    the get_object method that returns Containers
    """

    def get_object(self, zarr_obj):
        """
        A class that maps an Zarr object to a Container
        """
        return self.io.get_container(zarr_obj)


class AbstractZarrTableDataset(DatasetOfReferences):
    """
    Extension of DatasetOfReferences to serve as the base class for resolving Zarr
    references in compound datasets to either Builders and Containers.
    """

    @docval(
        {"name": "dataset", "type": (np.ndarray, Array), "doc": "the Zarr file lazily evaluate"},
        {"name": "io", "type": "ZarrIO", "doc": "the IO object that was used to read the underlying dataset"},
        {"name": "types", "type": (list, tuple), "doc": "the list/tuple of reference types"},
    )
    def __init__(self, **kwargs):
        types = popargs("types", kwargs)
        super().__init__(**kwargs)
        self.__refgetters = dict()
        for i, t in enumerate(types):
            if t == DatasetBuilder.OBJECT_REF_TYPE:
                self.__refgetters[i] = self._get_ref
            elif t is str:
                self.__refgetters[i] = self._get_utf
        self.__types = types
        tmp = list()
        for i in range(len(self.dataset.dtype)):
            sub = self.dataset.dtype[i]
            if np.issubdtype(sub, np.dtype("O")):
                tmp.append("object")
            elif np.issubdtype(sub, np.str_):
                # In zarr v3, string fields in compound dtypes use fixed-length Unicode
                # Check if this field holds JSON-serialized references
                tmp.append("object" if types[i] == DatasetBuilder.OBJECT_REF_TYPE else "utf")
            elif sub.metadata:
                if "vlen" in sub.metadata:
                    t = sub.metadata["vlen"]
                    if t is str:
                        tmp.append("utf")
                    elif t is bytes:
                        tmp.append("ascii")
            else:
                tmp.append(sub.type.__name__)
        self.__dtype = tmp

    @property
    def types(self):
        return self.__types

    @property
    def dtype(self):
        return self.__dtype

    def __getitem__(self, arg):
        rows = copy(super().__getitem__(arg))
        if np.issubdtype(type(arg), np.integer):
            # In zarr v3, structured array elements are 0-d numpy void with typed fields.
            # Convert to list so we can replace fields with resolved references (Python objects).
            row_list = list(rows.item()) if hasattr(rows, 'item') and rows.ndim == 0 else list(rows)
            self.__swap_refs(row_list)
            return row_list
        else:
            result = []
            for row in rows:
                row_list = list(row.item()) if hasattr(row, 'item') and row.ndim == 0 else list(row)
                self.__swap_refs(row_list)
                result.append(row_list)
            return result

    def __swap_refs(self, row):
        for i in self.__refgetters:
            getref = self.__refgetters[i]
            row[i] = getref(row[i])

    def _get_utf(self, string):
        """
        Decode a dataset element to unicode
        """
        return string.decode("utf-8") if isinstance(string, bytes) else string

    def __get_regref(self, ref):
        obj = self._get_ref(ref)
        return obj[ref]

    def resolve(self, manager):
        return self[0 : len(self)]

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


class AbstractZarrReferenceDataset(DatasetOfReferences):
    """
    Extension of DatasetOfReferences to serve as the base class for resolving Zarr
    references in datasets to either Builders and Containers.
    """

    def __getitem__(self, arg):
        ref = super().__getitem__(arg)
        if isinstance(ref, np.ndarray) and ref.ndim > 0:
            return [self._get_ref(x) for x in ref]
        else:
            # In zarr v3, scalar indexing may return a 0-d array; extract the item
            if isinstance(ref, np.ndarray) and ref.ndim == 0:
                ref = ref.item()
            return self._get_ref(ref)

    @property
    def dtype(self):
        return "object"


class ContainerZarrTableDataset(ContainerResolverMixin, AbstractZarrTableDataset):
    """
    A reference-resolving dataset for resolving references inside tables
    (i.e. compound dtypes) that returns resolved references as Containers
    """

    @classmethod
    def get_inverse_class(cls):
        return BuilderZarrTableDataset


class BuilderZarrTableDataset(BuilderResolverMixin, AbstractZarrTableDataset):
    """
    A reference-resolving dataset for resolving references inside tables
    (i.e. compound dtypes) that returns resolved references as Builders
    """

    @classmethod
    def get_inverse_class(cls):
        return ContainerZarrTableDataset


class ContainerZarrReferenceDataset(ContainerResolverMixin, AbstractZarrReferenceDataset):
    """
    A reference-resolving dataset for resolving object references that returns
    resolved references as Containers
    """

    @classmethod
    def get_inverse_class(cls):
        return BuilderZarrReferenceDataset


class BuilderZarrReferenceDataset(BuilderResolverMixin, AbstractZarrReferenceDataset):
    """
    A reference-resolving dataset for resolving object references that returns
    resolved references as Builders
    """

    @classmethod
    def get_inverse_class(cls):
        return ContainerZarrReferenceDataset
