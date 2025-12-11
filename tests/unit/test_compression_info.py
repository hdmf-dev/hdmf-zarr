"""
Tests for zarr array info display with compression data
"""
import unittest
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import zarr
from numcodecs import Blosc

from hdmf_zarr import ZarrIO, ZarrDataIO
from hdmf.spec import GroupSpec, DatasetSpec
from hdmf.build import GroupBuilder, DatasetBuilder, BuildManager, TypeMap
from hdmf.backends.utils import NamespaceToBuilderHelper


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

    def test_nbytes_stored_with_consolidated_metadata(self):
        """
        Test that nbytes_stored is correctly computed when using consolidated metadata.
        This tests the monkey-patch fix for ConsolidatedMetadataStore.getsize().
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = Blosc(cname='zstd', clevel=3, shuffle=Blosc.SHUFFLE)
        
        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressor=compressor,
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
        
        # Read back and check that nbytes_stored is available
        with ZarrIO(str(self.test_path), mode='r') as io:
            builder = io.read_builder()
            data_builder = builder['data']
            
            # Get the zarr array from the builder
            zarr_array = data_builder.data
            
            # Check that nbytes_stored is not -1 (which would cause info to hide compression data)
            self.assertGreater(zarr_array.nbytes_stored, 0, 
                             "nbytes_stored should be positive with consolidated metadata")
            
            # Check that info items include storage information
            info_dict = dict(zarr_array.info_items())
            self.assertIn('No. bytes stored', info_dict,
                         "Info should include 'No. bytes stored' field")
            self.assertIn('Storage ratio', info_dict,
                         "Info should include 'Storage ratio' field")

    def test_nbytes_stored_without_consolidated_metadata(self):
        """
        Test that nbytes_stored works correctly without consolidated metadata as a baseline.
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = Blosc(cname='zstd', clevel=3, shuffle=Blosc.SHUFFLE)
        
        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressor=compressor,
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
        
        # Read back and check that nbytes_stored is available
        with ZarrIO(str(self.test_path), mode='r-') as io:
            builder = io.read_builder()
            data_builder = builder['data']
            
            # Get the zarr array from the builder
            zarr_array = data_builder.data
            
            # Check that nbytes_stored is positive
            self.assertGreater(zarr_array.nbytes_stored, 0,
                             "nbytes_stored should be positive without consolidated metadata")
            
            # Check that info items include storage information
            info_dict = dict(zarr_array.info_items())
            self.assertIn('No. bytes stored', info_dict,
                         "Info should include 'No. bytes stored' field")
            self.assertIn('Storage ratio', info_dict,
                         "Info should include 'Storage ratio' field")

    def test_info_display_format(self):
        """
        Test that the info property displays correctly formatted output.
        """
        # Create some test data with compression using ZarrDataIO
        data = np.arange(10000, dtype='i4').reshape(100, 100)
        compressor = Blosc(cname='zstd', clevel=3, shuffle=Blosc.SHUFFLE)
        
        data_io = ZarrDataIO(
            data=data,
            chunks=(10, 10),
            compressor=compressor,
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
            self.assertIn('Compressor', info_str,
                         "Info should display Compressor")
            self.assertIn('No. bytes stored', info_str,
                         "Info should display 'No. bytes stored'")
            self.assertIn('Storage ratio', info_str,
                         "Info should display 'Storage ratio'")


if __name__ == '__main__':
    unittest.main()
