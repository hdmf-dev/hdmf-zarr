"""Debug the exact writing process."""
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane
from hdmf_zarr import NWBZarrIO
import numpy as np
import tempfile
import os
from hdmf.utils import get_data_shape

def debug_write_process():
    """Debug the exact writing process."""
    
    # Create the original data
    original_data = [(0, 0, 1.0), (1, 1, 1.0), (0, 0, 1.0), (1, 1, 1.0)]
    print("=== Original data ===")
    print(f"Original data: {original_data}")
    print(f"Original data length: {len(original_data)}")
    
    # Convert to numpy array to simulate what happens during writing
    np_array = np.array(original_data)
    print(f"Numpy array: {np_array}")
    print(f"Numpy array shape: {np_array.shape}")
    print(f"Numpy array dtype: {np_array.dtype}")
    
    # Check what get_data_shape returns
    print(f"get_data_shape(original_data): {get_data_shape(original_data)}")
    print(f"get_data_shape(np_array): {get_data_shape(np_array)}")
    
    # Create a compound dtype like the one that would be created
    compound_dtype = np.dtype([('x', '<u4'), ('y', '<u4'), ('weight', '<f4')])
    np_compound = np.array(original_data, dtype=compound_dtype)
    print(f"Compound array: {np_compound}")
    print(f"Compound array shape: {np_compound.shape}")
    print(f"Compound array dtype: {np_compound.dtype}")
    print(f"get_data_shape(np_compound): {get_data_shape(np_compound)}")
    
    # What happens when we load it back?
    loaded_data = np_compound[:]
    print(f"Loaded data: {loaded_data}")
    print(f"Loaded data shape: {loaded_data.shape}")
    print(f"get_data_shape(loaded_data): {get_data_shape(loaded_data)}")
    
    # Now let's create a Zarr array to see what happens
    import zarr
    zarr_array = zarr.array(np_compound)
    print(f"Zarr array: {zarr_array[:]}")
    print(f"Zarr array shape: {zarr_array.shape}")
    print(f"Zarr array dtype: {zarr_array.dtype}")
    
    # What happens when we reload from Zarr?
    zarr_loaded = zarr_array[:]
    print(f"Zarr loaded: {zarr_loaded}")
    print(f"Zarr loaded shape: {zarr_loaded.shape}")
    print(f"get_data_shape(zarr_loaded): {get_data_shape(zarr_loaded)}")

if __name__ == "__main__":
    debug_write_process()