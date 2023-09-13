"""
Utilities for the HDF5 I/O backend,
e.g., for wrapping HDF5 datasets on read, wrapping arrays for configuring write, or
writing the spec among others"""

from collections import deque
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from copy import copy

from hdmf.build import (Builder,
                        GroupBuilder,
                        DatasetBuilder,
                        LinkBuilder,
                        BuildManager,
                        RegionBuilder,
                        ReferenceBuilder,
                        TypeMap)

import json
import numpy as np
import warnings
import os
import logging

#from Zarrpy import Group, Dataset, RegionReference, Reference, special_dtype
#from Zarrpy import filters as Zarrpy_filter
from zarr import Array as ZarrArray

from hdmf.array import Array
from hdmf.query import HDMFDataset, ReferenceResolver, ContainerResolver, BuilderResolver
from hdmf.utils import docval, getargs, popargs, get_docval


class ZarrDataset(HDMFDataset):
    @docval({'name': 'dataset', 'type': (np.ndarray, ZarrArray, Array), 'doc': 'the Zarr file lazily evaluate'},
            {'name': 'io', 'type': 'ZarrIO', 'doc': 'the IO object that was used to read the underlying dataset'})
    def __init__(self, **kwargs):
        self.__io = popargs('io', kwargs)
        super().__init__(**kwargs)

    @property
    def io(self):
        return self.__io

    @property
    def shape(self):
        return self.dataset.shape


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
        if not hasattr(self, '__inverted'):
            cls = self.get_inverse_class()
            docval = get_docval(cls.__init__)
            kwargs = dict()
            for arg in docval:
                kwargs[arg['name']] = getattr(self, arg['name'])
            self.__inverted = cls(**kwargs)
        return self.__inverted

    def _get_ref(self, ref):
        # return self.get_object(self.dataset.file[ref])
        # breakpoint()
        name, zarr_obj = self.io.resolve_ref(ref) # ref is a json dict containing the path to the object
        return self.get_object(zarr_obj)

    def __iter__(self):
        for ref in super().__iter__():
            yield self._get_ref(ref)

    def __next__(self):
        return self._get_ref(super().__next__())


class BuilderResolverMixin(BuilderResolver):# refactor to backend/utils.py
    """
    A mixin for adding to Zarr reference-resolving types
    the get_object method that returns Builders
    """

    def get_object(self, zarr_obj):
        """
        A class that maps an Zarr object to a Builder
        """
        return self.io.get_builder(zarr_obj)


class ContainerResolverMixin(ContainerResolver): # refactor to backend/utils.py
    """
    A mixin for adding to Zarr reference-resolving types
    the get_object method that returns Containers
    """

    def get_object(self, zarr_obj):
        """
        A class that maps an Zarr object to a Container
        """
        return self.io.get_container(zarr_obj)


class AbstractZarrTableDataset(DatasetOfReferences): # Table refers to compound dataset

    @docval({'name': 'dataset', 'type': (np.ndarray, ZarrArray, Array), 'doc': 'the Zarr file lazily evaluate'},
            {'name': 'io', 'type': 'ZarrIO', 'doc': 'the IO object that was used to read the underlying dataset'},
            {'name': 'types', 'type': (list, tuple),
             'doc': 'the list/tuple of reference types'})
    def __init__(self, **kwargs):
        types = popargs('types', kwargs)
        super().__init__(**kwargs)
        self.__refgetters = dict()
        for i, t in enumerate(types):
            # if t is RegionReference: # not yet supported
            #     self.__refgetters[i] = self.__get_regref
            if t == DatasetBuilder.OBJECT_REF_TYPE:
                # breakpoint()
                self.__refgetters[i] = self._get_ref
            elif t is str:
                # we need this for when we read compound data types
                # that have unicode sub-dtypes since Zarrpy does not
                # store UTF-8 in compound dtypes
                self.__refgetters[i] = self._get_utf
        self.__types = types
        tmp = list()
        for i in range(len(self.dataset.dtype)):
            sub = self.dataset.dtype[i]
            if sub.metadata:
                if 'vlen' in sub.metadata:
                    t = sub.metadata['vlen']
                    if t is str:
                        tmp.append('utf')
                    elif t is bytes:
                        tmp.append('ascii')
                elif 'ref' in sub.metadata:
                    t = sub.metadata['ref']
                    if t is Reference:
                        tmp.append('object')
                    elif t is RegionReference:
                        tmp.append('region')
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
            self.__swap_refs(rows)
        else:
            for row in rows:
                self.__swap_refs(row)
        return rows

    def __swap_refs(self, row):
        for i in self.__refgetters:
            getref = self.__refgetters[i]
            row[i] = getref(row[i])

    def _get_utf(self, string):
        """
        Decode a dataset element to unicode
        """
        return string.decode('utf-8') if isinstance(string, bytes) else string

    def __get_regref(self, ref):
        obj = self._get_ref(ref)
        return obj[ref]

    def resolve(self, manager):
        return self[0:len(self)]

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


class AbstractZarrReferenceDataset(DatasetOfReferences):

    def __getitem__(self, arg):
        ref = super().__getitem__(arg)
        if isinstance(ref, np.ndarray):
            return [self._get_ref(x) for x in ref]
        else:
            return self._get_ref(ref)

    @property
    def dtype(self):
        return 'object'


class AbstractZarrRegionDataset(AbstractZarrReferenceDataset):

    def __getitem__(self, arg):
        obj = super().__getitem__(arg)
        ref = self.dataset[arg]
        return obj[ref]

    @property
    def dtype(self):
        return 'region'


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


class BuilderZarrReferenceDataset(BuilderResolverMixin, AbstractZarrReferenceDataset): # BuilderH5ReferenceDataset
    """
    A reference-resolving dataset for resolving object references that returns
    resolved references as Builders
    """

    @classmethod
    def get_inverse_class(cls):
        return ContainerZarrReferenceDataset


class ContainerZarrRegionDataset(ContainerResolverMixin, AbstractZarrRegionDataset):
    """
    A reference-resolving dataset for resolving region references that returns
    resolved references as Containers
    """

    @classmethod
    def get_inverse_class(cls):
        return BuilderZarrRegionDataset


class BuilderZarrRegionDataset(BuilderResolverMixin, AbstractZarrRegionDataset):
    """
    A reference-resolving dataset for resolving region references that returns
    resolved references as Builders
    """

    @classmethod
    def get_inverse_class(cls):
        return ContainerZarrRegionDataset
