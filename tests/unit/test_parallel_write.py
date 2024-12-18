"""Module for testing the parallel write feature for the ZarrIO."""

import unittest
import platform
from typing import Tuple, Dict
from io import StringIO
from unittest.mock import patch

import numpy as np
from numpy.testing import assert_array_equal
from hdmf_zarr import ZarrIO
from hdmf.common import DynamicTable, VectorData, get_manager
from hdmf.data_utils import GenericDataChunkIterator, DataChunkIterator

try:
    import tqdm  # noqa: F401

    TQDM_INSTALLED = True
except ImportError:
    TQDM_INSTALLED = False


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
        data = dictionary["data"]

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
    data = np.array([1.0, 2.0, 3.0])
    column = VectorData(name="TestColumn", description="", data=PickleableDataChunkIterator(data=data))
    dynamic_table = DynamicTable(name="TestTable", description="", id=list(range(3)), columns=[column])

    zarr_top_level_path = str(tmpdir / "test_parallel_write.zarr")
    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
        io.write(container=dynamic_table, number_of_jobs=number_of_jobs)

    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="r") as io:
        dynamic_table_roundtrip = io.read()
        data_roundtrip = dynamic_table_roundtrip["TestColumn"].data
        assert_array_equal(data_roundtrip, data)


def test_mixed_iterator_types(tmpdir):
    number_of_jobs = 2

    generic_iterator_data = np.array([1.0, 2.0, 3.0])
    generic_iterator_column = VectorData(
        name="TestGenericIteratorColumn",
        description="",
        data=PickleableDataChunkIterator(data=generic_iterator_data),
    )

    classic_iterator_data = np.array([4.0, 5.0, 6.0])
    classic_iterator_column = VectorData(
        name="TestClassicIteratorColumn",
        description="",
        data=DataChunkIterator(data=classic_iterator_data),
    )

    unwrappped_data = np.array([7.0, 8.0, 9.0])
    unwrapped_column = VectorData(
        name="TestUnwrappedColumn",
        description="",
        data=unwrappped_data,
    )
    dynamic_table = DynamicTable(
        name="TestTable",
        description="",
        id=list(range(3)),
        columns=[generic_iterator_column, classic_iterator_column, unwrapped_column],
    )

    zarr_top_level_path = str(tmpdir / "test_mixed_iterator_types.zarr")
    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
        io.write(container=dynamic_table, number_of_jobs=number_of_jobs)

    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="r") as io:
        dynamic_table_roundtrip = io.read()
        generic_iterator_data_roundtrip = dynamic_table_roundtrip["TestGenericIteratorColumn"].data
        assert_array_equal(generic_iterator_data_roundtrip, generic_iterator_data)

        classic_iterator_data_roundtrip = dynamic_table_roundtrip["TestClassicIteratorColumn"].data
        assert_array_equal(classic_iterator_data_roundtrip, classic_iterator_data)

        generic_iterator_data_roundtrip = dynamic_table_roundtrip["TestUnwrappedColumn"].data
        assert_array_equal(generic_iterator_data_roundtrip, unwrappped_data)


def test_mixed_iterator_pickleability(tmpdir):
    number_of_jobs = 2

    pickleable_iterator_data = np.array([1.0, 2.0, 3.0])
    pickleable_iterator_column = VectorData(
        name="TestGenericIteratorColumn",
        description="",
        data=PickleableDataChunkIterator(data=pickleable_iterator_data),
    )

    not_pickleable_iterator_data = np.array([4.0, 5.0, 6.0])
    not_pickleable_iterator_column = VectorData(
        name="TestClassicIteratorColumn",
        description="",
        data=NotPickleableDataChunkIterator(data=not_pickleable_iterator_data),
    )

    dynamic_table = DynamicTable(
        name="TestTable",
        description="",
        id=list(range(3)),
        columns=[pickleable_iterator_column, not_pickleable_iterator_column],
    )

    zarr_top_level_path = str(tmpdir / "test_mixed_iterator_pickleability.zarr")
    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
        io.write(container=dynamic_table, number_of_jobs=number_of_jobs)

    with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="r") as io:
        dynamic_table_roundtrip = io.read()

        pickleable_iterator_data_roundtrip = dynamic_table_roundtrip["TestGenericIteratorColumn"].data
        assert_array_equal(pickleable_iterator_data_roundtrip, pickleable_iterator_data)

        not_pickleable_iterator_data_roundtrip = dynamic_table_roundtrip["TestClassicIteratorColumn"].data
        assert_array_equal(not_pickleable_iterator_data_roundtrip, not_pickleable_iterator_data)


@unittest.skipIf(not TQDM_INSTALLED, "optional tqdm module is not installed")
def test_simple_tqdm(tmpdir):
    number_of_jobs = 2
    expected_desc = f"Writing Zarr datasets with {number_of_jobs} jobs"

    zarr_top_level_path = str(tmpdir / "test_simple_tqdm.zarr")
    with patch("sys.stderr", new=StringIO()) as tqdm_out:
        with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
            column = VectorData(
                name="TestColumn",
                description="",
                data=PickleableDataChunkIterator(
                    data=np.array([1.0, 2.0, 3.0]),
                    display_progress=True,
                ),
            )
            dynamic_table = DynamicTable(
                name="TestTable",
                description="",
                columns=[column],
                id=list(range(3)),  # must provide id's when all columns are iterators
            )
            io.write(container=dynamic_table, number_of_jobs=number_of_jobs)

    assert expected_desc in tqdm_out.getvalue()


@unittest.skipIf(not TQDM_INSTALLED, "optional tqdm module is not installed")
def test_compound_tqdm(tmpdir):
    number_of_jobs = 2
    expected_desc_pickleable = f"Writing Zarr datasets with {number_of_jobs} jobs"
    expected_desc_not_pickleable = "Writing non-parallel dataset..."

    zarr_top_level_path = str(tmpdir / "test_compound_tqdm.zarr")
    with patch("sys.stderr", new=StringIO()) as tqdm_out:
        with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
            pickleable_column = VectorData(
                name="TestPickleableIteratorColumn",
                description="",
                data=PickleableDataChunkIterator(
                    data=np.array([1.0, 2.0, 3.0]),
                    display_progress=True,
                ),
            )
            not_pickleable_column = VectorData(
                name="TestNotPickleableColumn",
                description="",
                data=NotPickleableDataChunkIterator(
                    data=np.array([4.0, 5.0, 6.0]),
                    display_progress=True,
                    progress_bar_options=dict(desc=expected_desc_not_pickleable, position=1),
                ),
            )
            dynamic_table = DynamicTable(
                name="TestTable",
                description="",
                columns=[pickleable_column, not_pickleable_column],
                id=list(range(3)),  # must provide id's when all columns are iterators
            )
            io.write(container=dynamic_table, number_of_jobs=number_of_jobs)

    tqdm_out_value = tqdm_out.getvalue()
    assert expected_desc_pickleable in tqdm_out_value
    assert expected_desc_not_pickleable in tqdm_out_value


def test_extra_keyword_argument_propagation(tmpdir):
    number_of_jobs = 2

    column = VectorData(name="TestColumn", description="", data=np.array([1.0, 2.0, 3.0]))
    dynamic_table = DynamicTable(name="TestTable", description="", id=list(range(3)), columns=[column])

    zarr_top_level_path = str(tmpdir / "test_extra_parallel_write_keyword_arguments.zarr")

    test_keyword_argument_pairs = [
        dict(max_threads_per_process=2, multiprocessing_context=None),
        dict(max_threads_per_process=None, multiprocessing_context="spawn"),
        dict(max_threads_per_process=2, multiprocessing_context="spawn"),
    ]
    if platform.system() != "Windows":
        test_keyword_argument_pairs.extend(
            [
                dict(max_threads_per_process=None, multiprocessing_context="spawn"),
                dict(max_threads_per_process=2, multiprocessing_context="spawn"),
            ]
        )

    for test_keyword_argument_pair in test_keyword_argument_pairs:
        test_max_threads_per_process = test_keyword_argument_pair["max_threads_per_process"]
        test_multiprocessing_context = test_keyword_argument_pair["multiprocessing_context"]
        with ZarrIO(path=zarr_top_level_path, manager=get_manager(), mode="w") as io:
            io.write(
                container=dynamic_table,
                number_of_jobs=number_of_jobs,
                max_threads_per_process=test_max_threads_per_process,
                multiprocessing_context=test_multiprocessing_context,
            )

            assert io._ZarrIO__dci_queue.max_threads_per_process == test_max_threads_per_process
            assert io._ZarrIO__dci_queue.multiprocessing_context == test_multiprocessing_context
