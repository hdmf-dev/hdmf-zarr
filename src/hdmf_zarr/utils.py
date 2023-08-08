"""Collection of utility I/O classes for the ZarrIO backend store"""
from zarr.hierarchy import Group
import zarr
import numcodecs
import gc
import numpy as np
import multiprocessing
from collections import deque
from collections.abc import Iterable
from typing import Optional, Union, Literal
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from threadpoolctl import threadpool_limits

import json
import logging

from hdmf.data_utils import DataIO, DataChunkIterator, DataChunk
from hdmf.query import HDMFDataset
from hdmf.utils import (docval,
                        getargs)

from hdmf.spec import (SpecWriter,
                       SpecReader)


# Necessary definitions to avoid parallelization bugs
# Inherited from SpikeInterface experience

# see
# https://stackoverflow.com/questions/10117073/how-to-use-initializer-to-set-up-my-multiprocess-pool
# the tricks is : theses 2 variables are global per worker
# so they are not share in the same process
global _worker_context
global _operation_to_run


def initializer_wrapper(
    operation_to_run: callable,
    process_initialization: callable,
    initialization_arguments: Iterable,  # TODO: eventually standardize with typing.Iterable[typing.Any]
    max_threads_per_process: Optional[int] = None
): # keyword arguments here are just for readability, ProcessPool only takes a tuple
    """
    Needed as a part of a bug fix with cloud memory leaks discovered by SpikeInterface team.

    Recommended fix is to have global wrappers for the working initializer that limits the
    threads used per process.
    """
    global _worker_context
    if max_threads_per_process is None:
        _worker_context = process_initialization(*initialization_arguments)
    else:
        with threadpool_limits(limits=max_threads_per_process):
            _worker_context = process_initialization(*initialization_arguments)
    _worker_context["max_threads_per_process"] = max_threads_per_process
    global _operation_to_run
    _operation_to_run = operation_to_run


def function_wrapper(args):
    """
    Needed as a part of a bug fix with cloud memory leaks discovered by SpikeInterface team.

    Recommended fix is to have a global wrapper for the executor.map level.
    """
    zarr_store_path, relative_dataset_path, iterator, buffer_selection = args
    global _worker_context
    global _operation_to_run
    max_threads_per_process = _worker_context["max_threads_per_process"]
    if max_threads_per_process is None:
        return _operation_to_run(_worker_context, zarr_store_path, relative_dataset_path, iterator, buffer_selection)
    else:
        with threadpool_limits(limits=max_threads_per_process):
            return _operation_to_run(_worker_context, zarr_store_path, relative_dataset_path, iterator, buffer_selection)


def _write_buffer_zarr(
    worker_context,
    zarr_store_path,
    relative_dataset_path,
    iterator,
    buffer_selection,
):
    zarr_store = zarr.open(store=zarr_store_path, mode="r+") #storage_options=storage_options) # TODO, figure out propagation of storage options
    zarr_dataset = zarr_store[relative_dataset_path]

    data = iterator._get_data(selection=buffer_selection)
    zarr_dataset[buffer_selection] = data

    # An issue detected in cloud usage by the SpikeInterface team
    # Fix memory leak by forcing garbage collection
    del data
    gc.collect()


class ZarrIODataChunkIteratorQueue(deque):
    """
    Helper class used by ZarrIO to manage the write for DataChunkIterators
    Each queue element must be a tupple of two elements:
    1) the dataset to write to and 2) the AbstractDataChunkIterator with the data
    """
    def __init__(self):
        self.logger = logging.getLogger('%s.%s' % (self.__class__.__module__, self.__class__.__qualname__))
        super().__init__()

    @classmethod
    def __write_chunk__(cls, dset: HDMFDataset, data: DataChunkIterator):
        """
        Internal helper function used to read a chunk from the given DataChunkIterator
        and write it to the given Dataset
        :param dset: The Dataset to write to
        :type dset: HDMFDataset
        :param data: The DataChunkIterator to read from
        :type data: DataChunkIterator
        :param buffer_index: The index of the next chunk within the DataChunkIterator, optional.
        Only used with multiprocessing for serializing the selections of the iteration.
        Default is to perform direct iteration on the in-memory DataChunkIterator for the single process.
        :type buffer_index: integer or None
        :return: True of a chunk was written, False otherwise
        :rtype: bool
        """
        # Read the next data block
        try:
            chunk_i = next(data)
        except StopIteration:
            return False
        # Determine the minimum array size required to store the chunk
        min_bounds = chunk_i.get_min_bounds()
        resize_required = False
        min_shape = list(dset.shape)
        if len(min_bounds) > len(dset.shape):
            raise ValueError("Shape of data chunk does not match the shape of the dataset")
        else:
            for si, sv in enumerate(dset.shape):
                if si < len(min_bounds):
                    if sv < min_bounds[si]:
                        min_shape[si] = min_bounds[si]
                        resize_required = True
                else:
                    break

        # Expand the dataset if needed
        if resize_required:
            dset.resize(min_shape)
        # Write the data
        dset[chunk_i.selection] = chunk_i.data
        # Chunk written and we need to continue

        return True
    
    def exhaust_queue(
        self,
        number_of_jobs: int = 1,
        max_threads_per_process: Union[None, int] = None,
        multiprocessing_context: Union[None, Literal["fork", "spawn"]] = None,
    ):
        """
        Read and write from any queued DataChunkIterators in a round-robin fashion (single job) or a single dataset at a time (multiple jobs).
        :param number_of_jobs: The number of jobs used to write the datasets. The default is 1.
        :type number_of_jobs: integer
        :param max_threads_per_process: Limits the number of threads used by each process. The default is None (no limits).
        :type max_threads_per_process: integer or None
        :param multiprocessing_context: Context for multiprocessing. It can be None (default), "fork" or "spawn".
        Note that "fork" is only available on UNIX systems (not Windows).
        :type multiprocessing_context: string or None
        """
        self.logger.debug("Exhausting DataChunkIterator from queue (length %d)" % len(self))
        if number_of_jobs > 1:
            buffer_map = list()

            display_progress = False
            for (zarr_dataset, iterator) in iter(self):
                display_progress = display_progress or iterator.display_progress
                iterator.display_progress = False
                iterator._base_kwargs.update(display_progress=False)

                for buffer_selection in iterator.buffer_selection_generator:
                    buffer_map_args = (zarr_dataset.store.path, zarr_dataset.path, iterator, buffer_selection)
                    buffer_map.append(buffer_map_args)

            operation_to_run = _write_buffer_zarr
            process_initialization = dict
            initialization_arguments = ()
            
            with ProcessPoolExecutor(
                max_workers=number_of_jobs,
                initializer=initializer_wrapper,
                mp_context=multiprocessing.get_context(method=multiprocessing_context),
                initargs=(operation_to_run, process_initialization, initialization_arguments, max_threads_per_process),
            ) as executor:
                results = executor.map(function_wrapper, buffer_map)

                if display_progress:
                    from tqdm import tqdm

                    results = tqdm(results, desc="Writing in parallel with Zarr", total=len(buffer_map), position=0)

                for result in results:
                    pass
                #    if self.handle_returns:
                #        returns.append(res)
                #    if self.gather_func is not None:
                #        self.gather_func(res)
        else:
            # Iterate through our queue and write data chunks in a round-robin fashion until all in-memory iterators are exhausted
            while len(self) > 0:
                dset, data = self.popleft()
                if self.__write_chunk__(dset, data):
                    self.append(dataset=dset, data=data)
                #assert False
        self.logger.debug("Exhausted DataChunkIterator from queue (length %d)" % len(self))

    def append(self, dataset, data):
        """
        Append a value to the queue
        :param dataset: The dataset where the DataChunkIterator is written to
        :type dataset: Zarr array
        :param data: DataChunkIterator with the data to be written
        :type data: AbstractDataChunkIterator
        """
        super().append((dataset, data))


class ZarrSpecWriter(SpecWriter):
    """
    Class used to write format specs to Zarr
    """

    @docval({'name': 'group', 'type': Group, 'doc': 'the Zarr file to write specs to'})
    def __init__(self, **kwargs):
        self.__group = getargs('group', kwargs)

    @staticmethod
    def stringify(spec):
        """
        Converts a spec into a JSON string to write to a dataset
        """
        return json.dumps(spec, separators=(',', ':'))

    def __write(self, d, name):
        data = self.stringify(d)
        dset = self.__group.require_dataset(name,
                                            shape=(1, ),
                                            dtype=object,
                                            object_codec=numcodecs.JSON(),
                                            compressor=None)
        dset.attrs['zarr_dtype'] = 'scalar'
        dset[0] = data
        return dset

    def write_spec(self, spec, path):
        """Write a spec to the given path"""
        return self.__write(spec, path)

    def write_namespace(self, namespace, path):
        """Write a namespace to the given path"""
        return self.__write({'namespaces': [namespace]}, path)


class ZarrSpecReader(SpecReader):
    """
    Class to read format specs from Zarr
    """

    @docval({'name': 'group', 'type': Group, 'doc': 'the Zarr file to read specs from'},
            {'name': 'source', 'type': str, 'doc': 'the path spec files are relative to', 'default': '.'})
    def __init__(self, **kwargs):
        self.__group, source = getargs('group', 'source', kwargs)
        super_kwargs = {'source': source}
        super(ZarrSpecReader, self).__init__(**super_kwargs)

    def __read(self, path):
        s = self.__group[path][0]
        d = json.loads(s)
        return d

    def read_spec(self, spec_path):
        """Read a spec from the given path"""
        return self.__read(spec_path)

    def read_namespace(self, ns_path):
        """Read a namespace from the given path"""
        ret = self.__read(ns_path)
        ret = ret['namespaces']
        return ret


class ZarrDataIO(DataIO):
    """
    Wrap data arrays for write via ZarrIO to customize I/O behavior, such as compression and chunking
    for data arrays.
    """

    @docval({'name': 'data',
             'type': (np.ndarray, list, tuple, zarr.Array, Iterable),
             'doc': 'the data to be written. NOTE: If an zarr.Array is used, all other settings but link_data' +
                    ' will be ignored as the dataset will either be linked to or copied as is in ZarrIO.'},
            {'name': 'chunks',
             'type': (list, tuple),
             'doc': 'Chunk shape',
             'default': None},
            {'name': 'fillvalue',
             'type': None,
             'doc': 'Value to be returned when reading uninitialized parts of the dataset',
             'default': None},
            {'name': 'compressor',
             'type': (numcodecs.abc.Codec, bool),
             'doc': 'Zarr compressor filter to be used. Set to True to use Zarr default.'
                    'Set to False to disable compression)',
             'default': None},
            {'name': 'filters',
             'type': (list, tuple),
             'doc': 'One or more Zarr-supported codecs used to transform data prior to compression.',
             'default': None},
            {'name': 'link_data',
             'type': bool,
             'doc': 'If data is an zarr.Array should it be linked to or copied. NOTE: This parameter is only ' +
                    'allowed if data is an zarr.Array',
             'default': False}
            )
    def __init__(self, **kwargs):
        # TODO Need to add error checks and warnings to ZarrDataIO to check for parameter collisions and add tests
        data, chunks, fill_value, compressor, filters, self.__link_data = getargs(
            'data', 'chunks', 'fillvalue', 'compressor', 'filters', 'link_data', kwargs)
        # NOTE: dtype and shape of the DataIO base class are not yet supported by ZarrDataIO.
        #       These parameters are used to create empty data to allocate the data but
        #       leave the I/O to fill the data to the user.
        super(ZarrDataIO, self).__init__(data=data,
                                         dtype=None,
                                         shape=None)
        if not isinstance(data, zarr.Array) and self.__link_data:
            self.__link_data = False
        self.__iosettings = dict()
        if chunks is not None:
            self.__iosettings['chunks'] = chunks
        if fill_value is not None:
            self.__iosettings['fill_value'] = fill_value
        if compressor is not None:
            if isinstance(compressor, bool):
                # Disable compression by setting compressor to None
                if not compressor:
                    self.__iosettings['compressor'] = None
                # To use default settings simply do not specify any compressor settings
                else:
                    pass
            # use the user-specified compressor
            else:
                self.__iosettings['compressor'] = compressor
        if filters is not None:
            self.__iosettings['filters'] = filters

    @property
    def link_data(self):
        return self.__link_data

    @property
    def io_settings(self):
        return self.__iosettings


class ZarrReference(dict):
    """
    Data structure to describe a reference to another container used with the ZarrIO backend
    """

    @docval({'name': 'source',
             'type': str,
             'doc': 'Source of referenced object',
             'default': None},
            {'name': 'path',
             'type': str,
             'doc': 'Path of referenced object',
             'default': None}
            )
    def __init__(self, **kwargs):
        dest_source, dest_path = getargs('source', 'path', kwargs)
        super(ZarrReference, self).__init__()
        super(ZarrReference, self).__setitem__('source', dest_source)
        super(ZarrReference, self).__setitem__('path', dest_path)

    @property
    def source(self):
        return super(ZarrReference, self).__getitem__('source')

    @property
    def path(self):
        return super(ZarrReference, self).__getitem__('path')

    @source.setter
    def source(self, s):
        super(ZarrReference, self).__setitem__('source', s)

    @path.setter
    def path(self, p):
        super(ZarrReference, self).__setitem__('path', p)
