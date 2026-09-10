"""Module for testing the parallel write feature for the ZarrIO."""

import unittest
from itertools import product
import platform
import warnings
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple, Dict
from io import StringIO
from unittest.mock import patch

import pytest
import zarr
import numpy as np
from numpy.testing import assert_array_equal
from hdmf_zarr import ZarrIO, ZarrDataIO
from hdmf_zarr.utils import ZarrIODataChunkIteratorQueue
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


@pytest.mark.parametrize(
    "shape,chunks,shards,buffers",
    [
        ((8,), (2,), (8,), (4,)),
        ((22,), (2,), (8,), (6,)),
        ((22, 14), (2, 2), (8, 8), (6, 10)),
        ((18,), (2,), (8,), (8,)),
        ((34,), (2,), (8,), (16,)),
        ((6,), (2,), (8,), (6,)),
        ((16, 12), (2, 2), (8, 8), (8, 4)),
        ((18, 6), (2, 2), (8, 8), (8, 6)),
        ((16,), (2,), None, (4,)),
    ],
)
def test_sharded_iterator_write_routing(tmp_path, shape, chunks, shards, buffers):
    """Check data and executor admission, without relying on a race occurring."""

    tasks = []

    class RecordingExecutor(ProcessPoolExecutor):
        def map(self, fn, iterable, **kwargs):
            items = list(iterable)
            tasks.extend(items)
            return super().map(fn, items, **kwargs)

    data = np.arange(1, np.prod(shape) + 1, dtype="int32").reshape(shape)
    iterator = PickleableDataChunkIterator(data, chunk_shape=chunks, buffer_shape=buffers)
    column = VectorData(name="values", description="", data=ZarrDataIO(iterator, chunks=chunks, shards=shards))
    table = DynamicTable(name="table", description="", id=list(range(shape[0])), columns=[column])
    store = str(tmp_path / "data.zarr")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with patch("hdmf_zarr.utils.ProcessPoolExecutor", wraps=RecordingExecutor) as executor:
            with ZarrIO(store, manager=get_manager(), mode="w") as io:
                io.write(table, number_of_jobs=2, multiprocessing_context="spawn")
    assert executor.called
    fallback_warnings = [w for w in caught if "Writing dataset 'values' sequentially" in str(w.message)]
    assert not fallback_warnings
    array = zarr.open_group(store, mode="r")["values"]
    assert array.shards == shards
    assert_array_equal(array[:], data)

    # Inspect actual submitted tasks: every cell is owned once, and no shard is
    # touched by two tasks, even when the source buffers cross shard boundaries.
    coverage = np.zeros(shape, dtype="int32")
    shard_owners = set()
    for _, path, _, selection in tasks:
        assert path == "values"
        coverage[selection] += 1
        if shards is not None:
            for shard_id in product(
                *(range(part.start // size, (part.stop - 1) // size + 1) for part, size in zip(selection, shards))
            ):
                assert shard_id not in shard_owners
                shard_owners.add(shard_id)
    if shards is None or ZarrIODataChunkIteratorQueue._buffers_contain_shards(shape, shards, buffers):
        expected = list(
            PickleableDataChunkIterator(data, chunk_shape=chunks, buffer_shape=buffers).buffer_selection_generator
        )
        assert [task[3] for task in tasks] == expected
    assert_array_equal(coverage, np.ones(shape, dtype="int32"))


def test_mixed_shard_alignment(tmp_path):
    """Both aligned and misaligned buffers use shard-owned tasks."""

    data = np.arange(1, 17, dtype="int32")
    columns = [
        VectorData(
            name=name,
            description="",
            data=ZarrDataIO(
                PickleableDataChunkIterator(data, chunk_shape=(2,), buffer_shape=buffer),
                chunks=(2,),
                shards=(8,),
            ),
        )
        for name, buffer in (("unsafe", (4,)), ("safe", (8,)))
    ]
    table = DynamicTable(name="table", description="", id=list(range(16)), columns=columns)
    store = str(tmp_path / "mixed.zarr")
    with patch("hdmf_zarr.utils.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as executor:
        with patch.object(
            ZarrIODataChunkIteratorQueue,
            "__write_chunk__",
            wraps=ZarrIODataChunkIteratorQueue.__write_chunk__,
        ) as sequential_write:
            with ZarrIO(store, manager=get_manager(), mode="w") as io:
                io.write(table, number_of_jobs=2, multiprocessing_context="spawn")
    assert executor.called
    sequential_write.assert_not_called()
    group = zarr.open_group(store, mode="r")
    for name in ("unsafe", "safe"):
        assert_array_equal(group[name][:], data)


def test_auto_shards_iterator(tmp_path):
    """Use Zarr's resolved layout to decide whether automatic shards are safe."""

    data = np.arange(1, 65, dtype="int32")
    iterator = PickleableDataChunkIterator(data, chunk_shape=(2,), buffer_shape=(2,))
    table = DynamicTable(
        name="table",
        description="",
        id=list(range(len(data))),
        columns=[VectorData(name="values", description="", data=ZarrDataIO(iterator, chunks=(2,), shards="auto"))],
    )
    store = str(tmp_path / "auto.zarr")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with patch("hdmf_zarr.utils.ProcessPoolExecutor", wraps=ProcessPoolExecutor) as executor:
            with ZarrIO(store, manager=get_manager(), mode="w") as io:
                io.write(table, number_of_jobs=2, multiprocessing_context="spawn")
    array = zarr.open_group(store, mode="r")["values"]
    assert array.shards is not None
    assert executor.called
    fallback = [w for w in caught if "Writing dataset 'values' sequentially" in str(w.message)]
    assert not fallback
    assert_array_equal(array[:], data)


@pytest.mark.parametrize(
    "shape,shards,buffers",
    [((22,), (8,), (6,)), ((22, 14), (8, 8), (6, 10)), ((18, 6), (8, 8), (8, 6))],
)
def test_shard_buffer_pieces(shape, shards, buffers):
    """Source reads partition the data and never exceed the buffer dimensions."""
    coverage = np.zeros(shape, dtype="int32")
    for shard in ZarrIODataChunkIteratorQueue._iter_shard_selections(shape, shards):
        for piece in ZarrIODataChunkIteratorQueue._iter_shard_buffer_selections(shard, buffers):
            for selection, owner, limit in zip(piece, shard, buffers):
                assert owner.start <= selection.start < selection.stop <= owner.stop
                assert selection.stop - selection.start <= limit
            coverage[piece] += 1
    assert_array_equal(coverage, np.ones(shape, dtype="int32"))
