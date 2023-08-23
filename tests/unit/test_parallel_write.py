"""Module for testing the parallel write feature for the ZarrIO."""
from pathlib import Path
from typing import Tuple, Dict

import numpy as np
from hdmf_zarr import ZarrIO
from hdmf.common import DynamicTable, VectorData
from hdmf.data_utils import GenericDataChunkIterator, DataChunkIterator


class PickleableDataChunkIterator(GenericDataChunkIterator):
    """Generic data chunk iterator used for specific testing purposes."""

    def __init__(self, data, **base_kwargs):
        self.data = data

        self._base_kwargs = base_kwargs
        super().__init__(**base_kwargs)

    def _get_dtype(self) -> np.dtype:
        return self.data.dtype

    def _get_maxshape(self) -> tuple:
        return self.data.shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        return self.data[selection]

    def __reduce__(self):
        instance_constructor = self._from_dict
        initialization_args = (self._to_dict(),)
        return (instance_constructor, initialization_args)

    def _to_dict(self) -> Dict:
        dictionary = dict()
        # Note this is not a recommended way to pickle contents
        # ~~ Used for testing purposes only ~~
        dictionary["data"] = self.data
        dictionary["base_kwargs"] = self._base_kwargs

        return dictionary

    @staticmethod
    def _from_dict(dictionary: dict) -> GenericDataChunkIterator:  # TODO: need to investigate the need of base path
        source_type = dictionary["data"]

        iterator = PickleableDataChunkIterator(data=data, **dictionary["base_kwargs"])
        return iterator

class NotPickleableDataChunkIterator(GenericDataChunkIterator):
    """Generic data chunk iterator used for specific testing purposes."""

    def __init__(self, data, **base_kwargs):
        self.data = data

        self._base_kwargs = base_kwargs
        super().__init__(**base_kwargs)

    def _get_dtype(self) -> np.dtype:
        return self.data.dtype

    def _get_maxshape(self) -> tuple:
        return self.data.shape

    def _get_data(self, selection: Tuple[slice]) -> np.ndarray:
        return self.data[selection]
    
def test_parallel_write(tmpdir):
    number_of_jobs = 2
    column = VectorData(name="TestColumn", description="", data=PickleableDataChunkIterator(data=np.array([1., 2., 3.])))
    dynamic_table = DynamicTable(name="TestTable", description="", columns=[column])

    zarr_top_level_path = str(tmpdir / f"example_parallel_zarr_{number_of_jobs}.zarr")
    with ZarrIO(path=zarr_top_level_path,  manager=get_manager(), mode="w") as io:
        io.write(dynamic_table, number_of_jobs=number_of_jobs)
        
def test_mixed_iterator_types(tmpdir):
    number_of_jobs = 2
    generic_column = VectorData(name="TestGenericColumn", description="", data=PickleableDataChunkIterator(data=np.array([1., 2., 3.])))
    classic_column = VectorData(name="TestClassicColumn", description="", data=DataChunkIterator(data=np.array([4., 5., 6.])))
    unwrapped_column = VectorData(name="TestUnwrappedColumn", description="", data=np.array([7., 8., 9.]))
    dynamic_table = DynamicTable(name="TestTable", description="", columns=[generic_column, classic_column, unwrapped_column])

    zarr_top_level_path = str(tmpdir / f"example_parallel_zarr_{number_of_jobs}.zarr")
    with ZarrIO(path=zarr_top_level_path,  manager=get_manager(), mode="w") as io:
        io.write(dynamic_table, number_of_jobs=number_of_jobs)
    # TODO: ensure can write a Zarr file with three datasets, one wrapped in a Generic iterator, one wrapped in DataChunkIterator, one not wrapped at all

def test_mixed_iterator_pickleability(tmpdir):
    pass # TODO: ensure can write a Zarr file with two datasets, one wrapped in pickleable one wrapped in not-pickleable

def test_tqdm(tmpdir):
    pass # TODO: grab stdout with dispaly_progress enabled and ensure it looks as expected (consult HDMF generic iterator tests)

def test_extra_args(tmpdir):
    pass # TODO? Should we test if the other arguments like thread count can be passed?
    # I mean, anything _can_ be passed, but how to test if it was actually used? Seems difficult...
