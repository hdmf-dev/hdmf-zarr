"""
Module for testing the ZarrDataIO class.

Many of the functions of ZarrDataIO are covered in tests related to ZarrIO and data conversion,
such as test_io_convert.TestHDF5toZarrWithFilters.  However, those tests are in the context of
more complex operations and are more akin to integration tests This module focuses on test for
specific unit functions of ZarrDataIO.
"""

import numcodecs
import h5py
import os
import shutil
import unittest

import numpy as np

try:
    import hdf5plugin

    HDF5PLUGIN = True
except ImportError:
    HDF5PLUGIN = False
from hdmf.testing import TestCase
from hdmf_zarr.utils import ZarrDataIO
from tests.unit.utils import get_temp_filepath


class TestZarrDataIO(TestCase):
    """Test the ZarrDataIO class"""

    def setUp(self):
        self.hdf_filename = get_temp_filepath()
        self.zarr_filename = get_temp_filepath()

    def tearDown(self):
        # clean up any opened files
        for fn in [self.hdf_filename, self.zarr_filename]:
            if fn is not None and os.path.exists(fn):
                if os.path.isdir(fn):
                    shutil.rmtree(fn)
                else:
                    os.remove(fn)

    def test_hdf5_to_zarr_filters_scaleoffset(self):
        """Test that we warn when the scaleoffset filter is being used in HDF5 in ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(name="test_dset", data=[1, 2, 3, 4, 5], scaleoffset=10)
        # test that we warn due to the scaleoffset
        msg = "/test_dset HDF5 scaleoffset filter ignored in Zarr"
        with self.assertWarnsWith(UserWarning, msg):
            filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 0)
        # Close the HDF5 file
        h5file.close()

    def test_hdf5_to_zarr_filters_lzf(self):
        """Test that we warn when the lzf filter is being used in HDF5 in ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(name="test_dset", data=[1, 2, 3, 4, 5], compression="lzf")
        # test that we warn due to the scaleoffset
        msg = "/test_dset HDF5 szip or lzf compression ignored in Zarr"
        with self.assertWarnsWith(UserWarning, msg):
            filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 0)
        # Close the HDF5 file
        h5file.close()

    @unittest.skipIf(not HDF5PLUGIN, "hdf5_plugin not installed")
    def test_hdf5_to_zarr_filters_lz4(self):
        """Test that we warn when the lz4 filter is being used in HDF5 in ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test_dset",
            data=[1, 2, 3, 4, 5],
            **hdf5plugin.LZ4(),
        )
        # test that we warn due to the scaleoffset
        msg = "/test_dset HDF5 lz4 compression ignored in Zarr"
        with self.assertWarnsWith(UserWarning, msg):
            filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 0)
        # Close the HDF5 file
        h5file.close()

    @unittest.skipIf(not HDF5PLUGIN, "hdf5_plugin not installed")
    def test_hdf5_to_zarr_filters_bitshuffle(self):
        """Test that we warn when the bitshuffle filter is being used in HDF5 in ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test_dset",
            data=[1, 2, 3, 4, 5],
            **hdf5plugin.Bitshuffle(nelems=0, lz4=True),
        )
        # test that we warn due to the scaleoffset
        msg = "/test_dset HDF5 bitshuffle compression ignored in Zarr"
        with self.assertWarnsWith(UserWarning, msg):
            filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 0)
        # Close the HDF5 file
        h5file.close()

    @unittest.skipIf(not HDF5PLUGIN, "hdf5_plugin not installed")
    def test_hdf5_to_zarr_filters_other_unsupported(self):
        """
        Test that we warn when an unsupported filter is used in HDF5 with ZarrDataIO.hdf5_to_zarr_filters.
        This test is to ensure that the catch-all at the end of the loop works.
        """
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset_FciDecomp = h5file.create_dataset(
            name="test_fcidecomp",
            data=[1, 2, 3, 4, 5],
            **hdf5plugin.FciDecomp(),
        )
        # test that we warn due to the FciDecomp
        msg = r"/test_fcidecomp HDF5 filter id 32018 with properties .* ignored in Zarr."
        with self.assertWarnsRegex(UserWarning, msg):
            filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset_FciDecomp)
        self.assertEqual(len(filters), 0)
        # Close the HDF5 file
        h5file.close()

    def test_hdf5_to_zarr_filters_shuffle(self):
        """Test HDF5 shuffle filter works with ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset_int = h5file.create_dataset(
            name="test_int",
            data=np.arange(5, dtype="int32"),
            shuffle=True,
        )
        h5dset_float = h5file.create_dataset(
            name="test_float",
            data=np.arange(5, dtype="float32"),
            shuffle=True,
        )
        # test that we apply shuffle filter on int data
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset_int)
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], numcodecs.Shuffle)
        # test that we apply shuffle filter on float data
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset_float)
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], numcodecs.Shuffle)
        h5file.close()

    @unittest.skipIf(not HDF5PLUGIN, "hdf5_plugin not installed")
    def test_hdf5_to_zarr_filters_blosclz(self):
        """Test HDF5 blosclz filter works with ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test_int",
            data=np.arange(100, dtype="float32"),
            **hdf5plugin.Blosc(cname="blosclz", clevel=9, shuffle=hdf5plugin.Blosc.SHUFFLE),
        )
        # test that we apply shuffle filter on int data
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], numcodecs.Blosc)
        self.assertEqual(filters[0].cname, "blosclz")
        self.assertEqual(filters[0].clevel, 9)
        self.assertEqual(filters[0].shuffle, hdf5plugin.Blosc.SHUFFLE)
        h5file.close()

    @unittest.skipIf(not HDF5PLUGIN, "hdf5_plugin not installed")
    def test_hdf5_to_zarr_filters_zstd(self):
        """Test HDF5 zstd filter works with ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test_int",
            data=np.arange(100, dtype="float32"),
            **hdf5plugin.Zstd(clevel=22),
        )
        # test that we apply shuffle filter on int data
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], numcodecs.Zstd)
        self.assertEqual(filters[0].level, 22)
        # Close the HDF5 file
        h5file.close()

    def test_hdf5_to_zarr_filters_gzip(self):
        """Test HDF5 gzip filter works with ZarrDataIO.hdf5_to_zarr_filters."""
        # Create a test HDF5 dataset with scaleoffset
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test_int",
            data=np.arange(100, dtype="float32"),
            compression="gzip",
            compression_opts=2,
        )
        # test that we apply shuffle filter on int data
        filters = ZarrDataIO.hdf5_to_zarr_filters(h5dset)
        self.assertEqual(len(filters), 1)
        self.assertIsInstance(filters[0], numcodecs.Zlib)
        self.assertEqual(filters[0].level, 2)
        # Close the HDF5 file
        h5file.close()

    def test_is_h5py_dataset(self):
        """Test ZarrDataIO.is_h5py_dataset"""
        h5file = h5py.File(self.hdf_filename, mode="a")
        arr = np.arange(10)
        h5dset = h5file.create_dataset(name="test", data=arr)
        self.assertTrue(ZarrDataIO.is_h5py_dataset(h5dset))
        self.assertFalse(ZarrDataIO.is_h5py_dataset(arr))

    def test_from_h5py_dataset(self):
        """Test ZarrDataIO.from_h5py_dataset"""
        h5file = h5py.File(self.hdf_filename, mode="a")
        h5dset = h5file.create_dataset(
            name="test",
            data=np.arange(1000).reshape((10, 100)),
            compression="gzip",
            compression_opts=6,
            shuffle=True,
            fillvalue=100,
            chunks=(5, 10),
        )
        re_zarrdataio = ZarrDataIO.from_h5py_dataset(h5dset)
        # Test that all settings are being presevered when creating the ZarrDataIO object
        self.assertIsInstance(re_zarrdataio, ZarrDataIO)
        self.assertEqual(re_zarrdataio.data, h5dset)
        self.assertEqual(re_zarrdataio.fillvalue, 100)
        self.assertEqual(re_zarrdataio.chunks, (5, 10))
        self.assertEqual(len(re_zarrdataio.io_settings["filters"]), 2)
        self.assertIsInstance(re_zarrdataio.io_settings["filters"][0], numcodecs.Shuffle)
        self.assertIsInstance(re_zarrdataio.io_settings["filters"][1], numcodecs.Zlib)
        # Close the HDF5 file
        h5file.close()

    def test_from_h5py_dataset_bytes_fillvalue(self):
        """
        Test ZarrDataIO.from_h5py_dataset with a fillvalue that is in bytes, which needs to be handled
        separately since bytes are not JSON serializable by default
        """
        h5file = h5py.File(self.hdf_filename, mode="a")
        # print(np.arange(10, dtype=np.int8).tobytes())
        h5dset = h5file.create_dataset(
            name="test_str",
            data=[b"hello", b"world", b"go"],
            fillvalue=b"None",
        )
        re_zarrdataio = ZarrDataIO.from_h5py_dataset(h5dset)
        # Test that all settings are being presevered when creating the ZarrDataIO object
        self.assertIsInstance(re_zarrdataio, ZarrDataIO)
        self.assertEqual(re_zarrdataio.io_settings["fill_value"], str("None"))
        # Close the HDF5 file
        h5file.close()
