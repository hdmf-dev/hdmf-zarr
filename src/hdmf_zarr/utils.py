"""Collection of utility I/O classes for the ZarrIO backend store."""

import gc
import traceback
import multiprocessing
import math
import json
import logging
import os
from collections import deque
from collections.abc import Iterable
from typing import Optional, Union, Literal, Tuple, Dict, Any
from concurrent.futures import ProcessPoolExecutor
from threadpoolctl import threadpool_limits
from warnings import warn

import numcodecs
import zarr
import numpy as np
from zarr.hierarchy import Group

from hdmf.data_utils import DataIO, GenericDataChunkIterator, DataChunkIterator, AbstractDataChunkIterator
from hdmf.query import HDMFDataset
from hdmf.utils import docval, getargs

from hdmf.spec import SpecWriter, SpecReader


# Necessary definitions to avoid parallelization bugs, Inherited from SpikeInterface experience
# see
# https://stackoverflow.com/questions/10117073/how-to-use-initializer-to-set-up-my-multiprocess-pool
# the tricks is : these 2 variables are global per worker
# so they are not share in the same process
global _worker_context
global _operation_to_run


class ZarrIODataChunkIteratorQueue(deque):
    """
    Helper class used by ZarrIO to manage the write for DataChunkIterators
    Each queue element must be a tuple of two elements:
    1) the dataset to write to and 2) the AbstractDataChunkIterator with the data
    :param number_of_jobs: The number of jobs used to write the datasets. The default is 1.
    :type number_of_jobs: integer
    :param max_threads_per_process: Limits the number of threads used by each process. The default is None (no limits).
    :type max_threads_per_process: integer or None
    :param multiprocessing_context: Context for multiprocessing. It can be None (default), "fork" or "spawn".
    Note that "fork" is only available on UNIX systems (not Windows).
    :type multiprocessing_context: string or None
    """

    def __init__(
        self,
        number_of_jobs: int = 1,
        max_threads_per_process: Union[None, int] = None,
        multiprocessing_context: Union[None, Literal["fork", "spawn"]] = None,
    ):
        self.logger = logging.getLogger("%s.%s" % (self.__class__.__module__, self.__class__.__qualname__))

        self.number_of_jobs = number_of_jobs
        self.max_threads_per_process = max_threads_per_process
        self.multiprocessing_context = multiprocessing_context

        super().__init__()

    @classmethod
    def __write_chunk__(cls, dset: HDMFDataset, data: DataChunkIterator):
        """
        Internal helper function used to read a chunk from the given DataChunkIterator
        and write it to the given Dataset
        :param dset: The Dataset to write to.
        :type dset: HDMFDataset
        :param data: The DataChunkIterator to read from.
        :type data: DataChunkIterator
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

    def exhaust_queue(self):
        """
        Read and write from any queued DataChunkIterators.

        Operates in a round-robin fashion for a single job.
        Operates on a single dataset at a time with multiple jobs.
        """
        self.logger.debug(f"Exhausting DataChunkIterator from queue (length {len(self)})")

        if self.number_of_jobs > 1:
            parallelizable_iterators = list()
            buffer_map = list()
            size_in_MB_per_iteration = list()

            display_progress = False
            r_bar_in_MB = (
                "| {n_fmt}/{total_fmt} MB [Elapsed: {elapsed}, Remaining: {remaining}, Rate:{rate_fmt}{postfix}]"
            )
            bar_format = "{l_bar}{bar}" + f"{r_bar_in_MB}"
            progress_bar_options = dict(
                desc=f"Writing Zarr datasets with {self.number_of_jobs} jobs",
                position=0,
                bar_format=bar_format,
                unit="MB",
            )
            for zarr_dataset, iterator in iter(self):
                # Parallel write only works well with GenericDataChunkIterators
                # Due to perfect alignment between chunks and buffers
                if not isinstance(iterator, GenericDataChunkIterator):
                    continue

                # Iterator must be pickleable as well, to be sent across jobs
                is_iterator_pickleable, reason = self._is_pickleable(iterator=iterator)
                if not is_iterator_pickleable:
                    self.logger.debug(
                        f"Dataset {zarr_dataset.path} was not pickleable during parallel write.\n\nReason: {reason}"
                    )
                    continue

                # Add this entry to a running list to remove after initial pass (cannot mutate during iteration)
                parallelizable_iterators.append((zarr_dataset, iterator))

                # Disable progress at the iterator level and aggregate enable option
                display_progress = display_progress or iterator.display_progress
                iterator.display_progress = False
                per_iterator_progress_options = {
                    key: value
                    for key, value in iterator.progress_bar_options.items()
                    if key not in ["desc", "total", "file"]
                }
                progress_bar_options.update(**per_iterator_progress_options)

                iterator_itemsize = iterator.dtype.itemsize
                for buffer_selection in iterator.buffer_selection_generator:
                    buffer_map_args = (zarr_dataset.store.path, zarr_dataset.path, iterator, buffer_selection)
                    buffer_map.append(buffer_map_args)
                    buffer_size_in_MB = (
                        math.prod([slice_.stop - slice_.start for slice_ in buffer_selection]) * iterator_itemsize / 1e6
                    )
                    size_in_MB_per_iteration.append(buffer_size_in_MB)
            progress_bar_options.update(
                total=int(sum(size_in_MB_per_iteration)),  # int() to round down to nearest integer for better display
            )

            if parallelizable_iterators:  # Avoid spinning up ProcessPool if no candidates during this exhaustion
                # Remove candidates for parallelization from the queue
                for zarr_dataset, iterator in parallelizable_iterators:
                    self.remove((zarr_dataset, iterator))

                operation_to_run = self._write_buffer_zarr
                process_initialization = dict
                initialization_arguments = ()
                with ProcessPoolExecutor(
                    max_workers=self.number_of_jobs,
                    initializer=self.initializer_wrapper,
                    mp_context=multiprocessing.get_context(method=self.multiprocessing_context),
                    initargs=(
                        operation_to_run,
                        process_initialization,
                        initialization_arguments,
                        self.max_threads_per_process,
                    ),
                ) as executor:
                    results = executor.map(self.function_wrapper, buffer_map)

                    if display_progress:
                        try:  # Import warnings are also issued at the level of the iterator instantiation
                            from tqdm import tqdm

                            results = tqdm(iterable=results, **progress_bar_options)

                            # executor map must be iterated to deploy commands over jobs
                            for size_in_MB, result in zip(size_in_MB_per_iteration, results):
                                results.update(n=int(size_in_MB))  # int() to round down for better display
                        except Exception as exception:  # pragma: no cover
                            warn(
                                message=(
                                    "Unable to setup progress bar due to"
                                    f"\n{type(exception)}: {str(exception)}\n\n{traceback.format_exc()}"
                                ),
                                stacklevel=2,
                            )
                            # executor map must be iterated to deploy commands over jobs
                            for result in results:
                                pass
                    else:
                        # executor map must be iterated to deploy commands over jobs
                        for result in results:
                            pass

        # Iterate through remaining queue and write DataChunks in a round-robin fashion until exhausted
        while len(self) > 0:
            zarr_dataset, iterator = self.popleft()
            if self.__write_chunk__(zarr_dataset, iterator):
                self.append(dataset=zarr_dataset, data=iterator)

        self.logger.debug(f"Exhausted DataChunkIterator from queue (length {len(self)})")

    def append(self, dataset, data):
        """
        Append a value to the queue
        :param dataset: The dataset where the DataChunkIterator is written to
        :type dataset: Zarr array
        :param data: DataChunkIterator with the data to be written
        :type data: AbstractDataChunkIterator
        """
        super().append((dataset, data))

    @staticmethod
    def _is_pickleable(iterator: AbstractDataChunkIterator) -> Tuple[bool, Optional[str]]:
        """
        Determine if the iterator can be pickled.

        Returns both the bool and the reason if False.
        """
        try:
            dictionary = iterator._to_dict()
            iterator._from_dict(dictionary=dictionary)

            return True, None
        except Exception as exception:
            base_hdmf_not_implemented_messages = (
                "The `._to_dict()` method for pickling has not been defined for this DataChunkIterator!",
                "The `._from_dict()` method for pickling has not been defined for this DataChunkIterator!",
            )

            if isinstance(exception, NotImplementedError) and str(exception) in base_hdmf_not_implemented_messages:
                reason = "The pickling methods for the iterator have not been defined."
            else:
                reason = (
                    f"The pickling methods for the iterator have been defined but throw the error:\n\n"
                    f"{type(exception)}: {str(exception)}\n\nwith traceback\n\n{traceback.format_exc()},"
                )

            return False, reason

    @staticmethod
    def initializer_wrapper(
        operation_to_run: callable,
        process_initialization: callable,
        initialization_arguments: Iterable,  # TODO: eventually standardize with typing.Iterable[typing.Any]
        max_threads_per_process: Optional[int] = None,
    ):  # keyword arguments here are just for readability, ProcessPool only takes a tuple
        """
        Needed as a part of a bug fix with cloud memory leaks discovered by SpikeInterface team.

        Recommended fix is to have global wrappers for the working initializer that limits the
        threads used per process.
        """
        global _worker_context
        global _operation_to_run

        if max_threads_per_process is None:
            _worker_context = process_initialization(*initialization_arguments)
        else:
            with threadpool_limits(limits=max_threads_per_process):
                _worker_context = process_initialization(*initialization_arguments)
        _worker_context["max_threads_per_process"] = max_threads_per_process
        _operation_to_run = operation_to_run

    @staticmethod
    def _write_buffer_zarr(
        worker_context: Dict[str, Any],
        zarr_store_path: str,
        relative_dataset_path: str,
        iterator: AbstractDataChunkIterator,
        buffer_selection: Tuple[slice, ...],
    ):
        # TODO, figure out propagation of storage options
        zarr_store = zarr.open(store=zarr_store_path, mode="r+")  # storage_options=storage_options)
        zarr_dataset = zarr_store[relative_dataset_path]

        data = iterator._get_data(selection=buffer_selection)
        zarr_dataset[buffer_selection] = data

        # An issue detected in cloud usage by the SpikeInterface team
        # Fix memory leak by forcing garbage collection
        del data
        gc.collect()

    @staticmethod
    def function_wrapper(args: Tuple[str, str, AbstractDataChunkIterator, Tuple[slice, ...]]):
        """
        Needed as a part of a bug fix with cloud memory leaks discovered by SpikeInterface team.

        Recommended fix is to have a global wrapper for the executor.map level.
        """
        zarr_store_path, relative_dataset_path, iterator, buffer_selection = args
        global _worker_context
        global _operation_to_run

        max_threads_per_process = _worker_context["max_threads_per_process"]
        if max_threads_per_process is None:
            return _operation_to_run(
                _worker_context,
                zarr_store_path,
                relative_dataset_path,
                iterator,
                buffer_selection,
            )
        else:
            with threadpool_limits(limits=max_threads_per_process):
                return _operation_to_run(
                    _worker_context,
                    zarr_store_path,
                    relative_dataset_path,
                    iterator,
                    buffer_selection,
                )


class ZarrSpecWriter(SpecWriter):
    """
    Class used to write format specs to Zarr
    """

    @docval({"name": "group", "type": Group, "doc": "the Zarr file to write specs to"})
    def __init__(self, **kwargs):
        self.__group = getargs("group", kwargs)

    @staticmethod
    def stringify(spec):
        """
        Converts a spec into a JSON string to write to a dataset
        """
        return json.dumps(spec, separators=(",", ":"))

    def __write(self, d, name):
        data = self.stringify(d)
        dset = self.__group.require_dataset(
            name,
            shape=(1,),
            dtype=object,
            object_codec=numcodecs.JSON(),
            compressor=None,
        )
        dset.attrs["zarr_dtype"] = "scalar"
        dset[0] = data
        return dset

    def write_spec(self, spec, path):
        """Write a spec to the given path"""
        return self.__write(spec, path)

    def write_namespace(self, namespace, path):
        """Write a namespace to the given path"""
        return self.__write({"namespaces": [namespace]}, path)


class ZarrSpecReader(SpecReader):
    """
    Class to read format specs from Zarr
    """

    @docval({"name": "group", "type": Group, "doc": "the Zarr file to read specs from"})
    def __init__(self, **kwargs):
        self.__group = getargs("group", kwargs)
        source = "%s:%s" % (os.path.abspath(self.__group.store.path), self.__group.name)
        super().__init__(source=source)
        self.__cache = None

    def __read(self, path):
        s = self.__group[path][0]
        d = json.loads(s)
        return d

    def read_spec(self, spec_path):
        """Read a spec from the given path"""
        return self.__read(spec_path)

    def read_namespace(self, ns_path):
        """Read a namespace from the given path"""
        if self.__cache is None:
            self.__cache = self.__read(ns_path)
        ret = self.__cache["namespaces"]
        return ret


class ZarrDataIO(DataIO):
    """
    Wrap data arrays for write via ZarrIO to customize I/O behavior, such as compression and chunking
    for data arrays.
    """

    @docval(
        {
            "name": "data",
            "type": (np.ndarray, list, tuple, zarr.Array, Iterable),
            "doc": (
                "the data to be written. NOTE: If an zarr.Array is used, all other settings but link_data "
                "will be ignored as the dataset will either be linked to or copied as is in ZarrIO."
            ),
        },
        {
            "name": "chunks",
            "type": (list, tuple),
            "doc": "Chunk shape",
            "default": None,
        },
        {
            "name": "fillvalue",
            "type": None,
            "doc": "Value to be returned when reading uninitialized parts of the dataset",
            "default": None,
        },
        {
            "name": "compressor",
            "type": (numcodecs.abc.Codec, bool),
            "doc": (
                "Zarr compressor filter to be used. Set to True to use Zarr default. "
                "Set to False to disable compression)"
            ),
            "default": None,
        },
        {
            "name": "filters",
            "type": (list, tuple),
            "doc": "One or more Zarr-supported codecs used to transform data prior to compression.",
            "default": None,
        },
        {
            "name": "link_data",
            "type": bool,
            "doc": (
                "If data is an zarr.Array should it be linked to or copied. NOTE: This parameter is only "
                "allowed if data is an zarr.Array"
            ),
            "default": False,
        },
    )
    def __init__(self, **kwargs):
        # TODO Need to add error checks and warnings to ZarrDataIO to check for parameter collisions and add tests
        data, chunks, fill_value, compressor, filters, self.__link_data = getargs(
            "data", "chunks", "fillvalue", "compressor", "filters", "link_data", kwargs
        )
        # NOTE: dtype and shape of the DataIO base class are not yet supported by ZarrDataIO.
        #       These parameters are used to create empty data to allocate the data but
        #       leave the I/O to fill the data to the user.
        super().__init__(data=data, dtype=None, shape=None)
        if not isinstance(data, zarr.Array) and self.__link_data:
            self.__link_data = False
        self.__iosettings = dict()
        if chunks is not None:
            self.__iosettings["chunks"] = chunks
        if fill_value is not None:
            self.__iosettings["fill_value"] = fill_value
        if compressor is not None:
            if isinstance(compressor, bool):
                # Disable compression by setting compressor to None
                if not compressor:
                    self.__iosettings["compressor"] = None
                # To use default settings simply do not specify any compressor settings
                else:
                    pass
            # use the user-specified compressor
            else:
                self.__iosettings["compressor"] = compressor
        if filters is not None:
            self.__iosettings["filters"] = filters

    @property
    def link_data(self) -> bool:
        """Bool indicating should it be linked to or copied. NOTE: Only applies to zarr.Array type data"""
        return self.__link_data

    @property
    def io_settings(self) -> dict:
        """Dict with the io settings to use"""
        return self.__iosettings

    def get_io_params(self) -> dict:
        """
        Returns a dict with the I/O parameters specified in this DataIO.
        """
        ret = dict(self.__iosettings)
        ret['link_data'] = self.__link_data
        return ret

    @staticmethod
    def from_h5py_dataset(h5dataset, **kwargs):
        """
        Factory method to create a ZarrDataIO instance from a h5py.Dataset.
        The ZarrDataIO object wraps the h5py.Dataset and the io filter settings
        are inferred from filters used in h5py such that the options in Zarr match
        (if possible) the options used in HDF5.

        :param dataset: h5py.Dataset object that should be wrapped
        :type dataset: h5py.Dataset
        :param kwargs: Other keyword arguments to pass to ZarrDataIO.__init__

        :returns: ZarrDataIO object wrapping the dataset
        """
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dataset)
        fillval = h5dataset.fillvalue if "fillvalue" not in kwargs else kwargs.pop("fillvalue")
        if isinstance(fillval, bytes):  # bytes are not JSON serializable so use string instead
            fillval = fillval.decode("utf-8")
        chunks = h5dataset.chunks if "chunks" not in kwargs else kwargs.pop("chunks")
        re = ZarrDataIO(
            data=h5dataset,
            filters=filters,
            fillvalue=fillval,
            chunks=chunks,
            **kwargs,
        )
        return re

    @staticmethod
    def hdf5_to_zarr_filters(h5dataset) -> list:
        """From the given h5py.Dataset infer the corresponding filters to use in Zarr"""
        # Based on https://github.com/fsspec/kerchunk/blob/617d9ce06b9d02375ec0e5584541fcfa9e99014a/kerchunk/hdf.py#L181
        filters = []
        # Check for unsupported filters
        if h5dataset.scaleoffset:
            # TODO: translate to  numcodecs.fixedscaleoffset.FixedScaleOffset()
            warn(f"{h5dataset.name} HDF5 scaleoffset filter ignored in Zarr")
        if h5dataset.compression in ("szip", "lzf"):
            warn(f"{h5dataset.name} HDF5 szip or lzf compression ignored in Zarr")
        # Add the shuffle filter if possible
        if h5dataset.shuffle and h5dataset.dtype.kind != "O":
            # cannot use shuffle if we materialised objects
            filters.append(numcodecs.Shuffle(elementsize=h5dataset.dtype.itemsize))
        # iterate through all the filters and add them to the list
        for filter_id, properties in h5dataset._filters.items():
            filter_id_str = str(filter_id)
            if filter_id_str == "32001":
                blosc_compressors = ("blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd")
                (_1, _2, bytes_per_num, total_bytes, clevel, shuffle, compressor) = properties
                pars = dict(
                    blocksize=total_bytes,
                    clevel=clevel,
                    shuffle=shuffle,
                    cname=blosc_compressors[compressor],
                )
                filters.append(numcodecs.Blosc(**pars))
            elif filter_id_str == "32015":
                filters.append(numcodecs.Zstd(level=properties[0]))
            elif filter_id_str == "gzip":
                filters.append(numcodecs.Zlib(level=properties))
            elif filter_id_str == "32004":
                warn(f"{h5dataset.name} HDF5 lz4 compression ignored in Zarr")
            elif filter_id_str == "32008":
                warn(f"{h5dataset.name} HDF5 bitshuffle compression ignored in Zarr")
            elif filter_id_str == "shuffle":  # already handled above
                pass
            else:
                warn(f"{h5dataset.name} HDF5 filter id {filter_id} with properties {properties} ignored in Zarr.")
        return filters

    @staticmethod
    def is_h5py_dataset(obj):
        """Check if the object is an instance of h5py.Dataset without requiring import of h5py"""
        return (obj.__class__.__module__, obj.__class__.__name__) == ("h5py._hl.dataset", "Dataset")


class ZarrReference(dict):
    """
    Data structure to describe a reference to another container used with the ZarrIO backend
    """

    @docval(
        {
            "name": "source",
            "type": str,
            "doc": "Source of referenced object. Usually the relative path to the "
            "Zarr file containing the referenced object",
            "default": None,
        },
        {
            "name": "path",
            "type": str,
            "doc": "Path of referenced object within the source",
            "default": None,
        },
        {
            "name": "object_id",
            "type": str,
            "doc": "Object_id of the referenced object (if available)",
            "default": None,
        },
        {
            "name": "source_object_id",
            "type": str,
            "doc": "Object_id of the source (should always be available)",
            "default": None,
        },
    )
    def __init__(self, **kwargs):
        dest_source, dest_path, dest_object_id, dest_source_object_id = getargs(
            "source", "path", "object_id", "source_object_id", kwargs
        )
        super(ZarrReference, self).__init__()
        self.source = dest_source
        self.path = dest_path
        self.object_id = dest_object_id
        self.source_object_id = dest_source_object_id

    @property
    def source(self) -> str:
        return super().__getitem__("source")

    @property
    def path(self) -> str:
        return super().__getitem__("path")

    @property
    def object_id(self) -> str:
        return super().__getitem__("object_id")

    @property
    def source_object_id(self) -> str:
        return super().__getitem__("source_object_id")

    @source.setter
    def source(self, source: str):
        super().__setitem__("source", source)

    @path.setter
    def path(self, path: str):
        super().__setitem__("path", path)

    @object_id.setter
    def object_id(self, object_id: str):
        super().__setitem__("object_id", object_id)

    @source_object_id.setter
    def source_object_id(self, object_id: str):
        super().__setitem__("source_object_id", object_id)
