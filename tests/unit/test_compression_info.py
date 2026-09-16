"""
Tests for zarr array info display with compression data
"""
import unittest
import shutil
import tempfile
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

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_info_with_consolidated_metadata(self):
        """
        Test that array info is available when using consolidated metadata.
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = BloscCodec(cname='zstd', clevel=3, shuffle='shuffle')

        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressors=compressor,
        )

        # Write data with ZarrIO
        with ZarrIO(str(self.test_path), mode='w') as io:
            # Create a simple group structure
            group_builder = GroupBuilder('root', attributes={'namespace': 'test'})
            dataset_builder = DatasetBuilder(
                'data',
                data_io,
                attributes={},
            )
            group_builder.set_dataset(dataset_builder)

            # Write with consolidated metadata
            io.write_builder(group_builder, consolidate_metadata=True)

        # Read back and check that info is available
        with ZarrIO(str(self.test_path), mode='r') as io:
            builder = io.read_builder()
            data_builder = builder['data']

            # Get the zarr array from the builder
            zarr_array = data_builder.data

            # Check that the compressor configured above survived the round trip
            blosc = [c for c in zarr_array.compressors if isinstance(c, BloscCodec)]
            self.assertEqual(len(blosc), 1)
            self.assertEqual(blosc[0].to_dict()['configuration']['cname'], 'zstd')

            # Check that the stored size is measured rather than reported as a placeholder
            self.assertGreater(zarr_array.nbytes_stored(), 0)
            self.assertLess(zarr_array.nbytes_stored(), zarr_array.nbytes)

    def test_info_without_consolidated_metadata(self):
        """
        Test that array info works correctly without consolidated metadata as a baseline.
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = BloscCodec(cname='zstd', clevel=3, shuffle='shuffle')

        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressors=compressor,
        )

        # Write data with ZarrIO without consolidation
        with ZarrIO(str(self.test_path), mode='w') as io:
            # Create a simple group structure
            group_builder = GroupBuilder('root', attributes={'namespace': 'test'})
            dataset_builder = DatasetBuilder(
                'data',
                data_io,
                attributes={},
            )
            group_builder.set_dataset(dataset_builder)

            # Write without consolidated metadata
            io.write_builder(group_builder, consolidate_metadata=False)

        # Read back and check that info is available
        with ZarrIO(str(self.test_path), mode='r') as io:
            builder = io.read_builder()
            data_builder = builder['data']

            # Get the zarr array from the builder
            zarr_array = data_builder.data

            # Check that the compressor configured above survived the round trip
            blosc = [c for c in zarr_array.compressors if isinstance(c, BloscCodec)]
            self.assertEqual(len(blosc), 1)
            self.assertEqual(blosc[0].to_dict()['configuration']['cname'], 'zstd')

            # Check that the stored size is measured rather than reported as a placeholder
            self.assertGreater(zarr_array.nbytes_stored(), 0)
            self.assertLess(zarr_array.nbytes_stored(), zarr_array.nbytes)

    def test_info_display_format(self):
        """
        Test that the info property displays correctly formatted output.
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = BloscCodec(cname='zstd', clevel=3, shuffle='shuffle')

        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressors=compressor,
        )

        # Write data with ZarrIO with consolidated metadata
        with ZarrIO(str(self.test_path), mode='w') as io:
            group_builder = GroupBuilder('root', attributes={'namespace': 'test'})
            dataset_builder = DatasetBuilder(
                'data',
                data_io,
                attributes={},
            )
            group_builder.set_dataset(dataset_builder)
            io.write_builder(group_builder, consolidate_metadata=True)

        # Read back and check info display
        with ZarrIO(str(self.test_path), mode='r') as io:
            builder = io.read_builder()
            data_builder = builder['data']
            zarr_array = data_builder.data

            # Get the info string representation
            info_str = str(zarr_array.info)

            # Check that the info string contains expected fields
            self.assertIn('Compressors', info_str)
            self.assertIn('BloscCodec', info_str)

            # Stored size requires walking the store, which info_complete does
            complete_str = str(zarr_array.info_complete())
            self.assertIn('No. bytes stored', complete_str)
            self.assertIn('Storage ratio', complete_str)


if __name__ == '__main__':
    unittest.main()
