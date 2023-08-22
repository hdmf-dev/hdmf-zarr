"""Module for testing the parallel write feature for the ZarrIO."""
from pathlib import Path
from typing import Tuple, Dict

import numpy as np
from hdmf_zarr import ZarrIO
from hdmf.common import DynamicTable, VectorData
from hdmf.data_utils import GenericDataChunkIterator


class TestDataChunkIterator(GenericDataChunkIterator):
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

        iterator = TestDataChunkIterator(data=data, **dictionary["base_kwargs"])
        return iterator

def test_parallel_write(tmpdir):
    number_of_jobs = 2
    column = VectorData(name="TestColumn", description="", data=TestDataChunkIterator(data=np.array([1., 2., 3.])))
    dynamic_table = DynamicTable(name="TestTable", description="", columns=[column])

    zarr_top_level_path = str(tmpdir / f"example_parallel_zarr_{number_of_jobs}.zarr")
    with ZarrIO(path=zarr_top_level_path, mode="w") as io:
        io.write(dynamic_table, number_of_jobs=number_of_jobs)