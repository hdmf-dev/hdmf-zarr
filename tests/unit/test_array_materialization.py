"""Tests for reading a full zarr Array to numpy on the calling thread.

hdmf_zarr.backend patches ``zarr.Array.__array__`` so that numpy coercion of a zarr
Array (e.g. when h5py copies it during a Zarr -> HDF5 export) reads on the calling
thread. This keeps zarr's shared "zarr_io" event-loop thread free of the read, so a
cyclic-GC finalizer that acquires h5py's "phil" lock on that thread cannot deadlock
against the caller holding "phil".
"""

import asyncio
import time
from unittest import TestCase

import numpy as np
import zarr
from zarr.core.sync import _get_loop

# Importing the backend installs the Array.__array__ patch.
import hdmf_zarr.backend  # noqa: F401


class TestArrayMaterialization(TestCase):

    def test_asarray_values_1d(self):
        z = zarr.create_array(store={}, shape=(50,), chunks=(8,), dtype="f8")
        z[:] = np.arange(50)
        np.testing.assert_array_equal(np.asarray(z), np.arange(50))

    def test_asarray_values_2d(self):
        z = zarr.create_array(store={}, shape=(10, 3), chunks=(4, 2), dtype="i4")
        expected = np.arange(30).reshape(10, 3)
        z[:] = expected
        np.testing.assert_array_equal(np.asarray(z), expected)

    def test_asarray_dtype_coercion(self):
        z = zarr.create_array(store={}, shape=(5,), chunks=(2,), dtype="i4")
        z[:] = np.arange(5)
        arr = np.asarray(z, dtype="f4")
        self.assertEqual(arr.dtype, np.dtype("f4"))
        np.testing.assert_array_equal(arr, np.arange(5, dtype="f4"))

    def test_copy_false_raises(self):
        z = zarr.create_array(store={}, shape=(3,), chunks=(2,), dtype="i4")
        z[:] = np.arange(3)
        with self.assertRaises(ValueError):
            z.__array__(copy=False)

    def test_read_runs_on_calling_thread(self):
        """np.asarray must not depend on the shared zarr_io loop thread.

        Occupy that single loop thread with a synchronous block; the read still
        returns promptly because it runs on the calling thread. Without the patch,
        the read would dispatch to the blocked loop and wait for it.
        """
        z = zarr.create_array(store={}, shape=(100,), chunks=(10,), dtype="f8")
        z[:] = np.arange(100)

        async def _block(seconds):
            time.sleep(seconds)  # synchronous: occupies the single loop thread

        loop = _get_loop()
        block_seconds = 3.0
        future = asyncio.run_coroutine_threadsafe(_block(block_seconds), loop)
        try:
            time.sleep(0.2)  # ensure the block task is running on the loop thread
            start = time.perf_counter()
            arr = np.asarray(z)
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, block_seconds - 1.0)
            np.testing.assert_array_equal(arr, np.arange(100))
        finally:
            future.result(timeout=block_seconds + 5.0)
