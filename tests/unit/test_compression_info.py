"""
Tests for zarr array info display with compression data
"""

import unittest
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from zarr.codecs import BloscCodec

from hdmf_zarr import ZarrIO, ZarrDataIO
from hdmf.build import GroupBuilder, DatasetBuilder


class TestZarrCompressionInfo(unittest.TestCase):
    """
    Test that zarr array .info displays compression information correctly
    when using consolidated metadata stores.
    """

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_path = self.test_dir / "test.zarr"
        # 10000 sequential int32 values compress far below their 40000 raw bytes
        self.data = np.arange(10000, dtype="i4").reshape(100, 100)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @contextmanager
    def write_compressed_array(self, consolidate_metadata):
        """Write a single Blosc-compressed dataset and return the array read back from disk."""
        data_io = ZarrDataIO(
            data=self.data,
            chunks=(10, 10),
            compressors=BloscCodec(cname="zstd", clevel=3, shuffle="shuffle"),
        )
        with ZarrIO(str(self.test_path), mode="w") as io:
            group_builder = GroupBuilder("root", attributes={"namespace": "test"})
            group_builder.set_dataset(DatasetBuilder("data", data_io, attributes={}))
            io.write_builder(group_builder, consolidate_metadata=consolidate_metadata)

        with ZarrIO(str(self.test_path), mode="r") as io:
            yield io.read_builder()["data"].data

    def assert_compressor_round_tripped(self, zarr_array):
        """The Blosc codec configured on ZarrDataIO must survive the write and be read back."""
        blosc_codecs = [c for c in zarr_array.compressors if isinstance(c, BloscCodec)]
        self.assertEqual(len(blosc_codecs), 1, f"expected one BloscCodec, got {zarr_array.compressors}")
        self.assertEqual(blosc_codecs[0].cname.value, "zstd")
        self.assertEqual(blosc_codecs[0].clevel, 3)

    def assert_stored_size_reported(self, zarr_array):
        """Stored size must be a real measurement, and the data must actually be smaller on disk."""
        nbytes_stored = zarr_array.nbytes_stored()
        self.assertGreater(nbytes_stored, 0)
        self.assertLess(nbytes_stored, zarr_array.nbytes)

    def test_info_with_consolidated_metadata(self):
        """
        Stored size is reported when the store carries consolidated metadata.

        Reporting it requires walking the store, which consolidated metadata does not cover.
        """
        with self.write_compressed_array(consolidate_metadata=True) as zarr_array:
            self.assert_compressor_round_tripped(zarr_array)
            self.assert_stored_size_reported(zarr_array)

    def test_info_without_consolidated_metadata(self):
        """
        Stored size is reported when the store carries no consolidated metadata.
        """
        with self.write_compressed_array(consolidate_metadata=False) as zarr_array:
            self.assert_compressor_round_tripped(zarr_array)
            self.assert_stored_size_reported(zarr_array)

    def test_info_display_format(self):
        """
        The full info listing names the compressor and the storage-size fields.
        """
        with self.write_compressed_array(consolidate_metadata=True) as zarr_array:
            info_str = str(zarr_array.info_complete())
            self.assertIn("No. bytes stored", info_str)
            self.assertIn("Storage ratio", info_str)
            self.assertIn("BloscCodec", info_str)
            self.assertIn("BloscCodec", str(zarr_array.info))


if __name__ == "__main__":
    unittest.main()
