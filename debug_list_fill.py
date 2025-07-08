"""Debug the exact issue by adding print statements to trace execution."""
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane
from hdmf_zarr import NWBZarrIO
import numpy as np
import tempfile
import os
from hdmf.utils import get_data_shape

# Let's patch the __list_fill__ method to add debugging
from hdmf_zarr.backend import ZarrIO
original_list_fill = ZarrIO.__list_fill__

def debug_list_fill(self, parent, name, data, options=None):
    """Debug version of __list_fill__ with print statements."""
    if name == 'pixel_mask':
        print(f"\n=== DEBUG __list_fill__ for {name} ===")
        print(f"Data: {data}")
        print(f"Data type: {type(data)}")
        if hasattr(data, 'shape'):
            print(f"Data shape: {data.shape}")
        if hasattr(data, 'dtype'):
            print(f"Data dtype: {data.dtype}")
        print(f"get_data_shape(data): {get_data_shape(data)}")
        if hasattr(data, '__len__'):
            print(f"Data length: {len(data)}")
        
        # Check what happens when we slice the data
        data_slice = data[:]
        print(f"Data slice: {data_slice}")
        print(f"Data slice type: {type(data_slice)}")
        if hasattr(data_slice, 'shape'):
            print(f"Data slice shape: {data_slice.shape}")
        if hasattr(data_slice, 'dtype'):
            print(f"Data slice dtype: {data_slice.dtype}")
        print(f"get_data_shape(data_slice): {get_data_shape(data_slice)}")
        
        # Check the options
        if options:
            print(f"Options: {options}")
            if 'dtype' in options:
                print(f"Options dtype: {options['dtype']}")
        
        print("=== END DEBUG ===\n")
    
    return original_list_fill(self, parent, name, data, options)

# Monkey patch for debugging
ZarrIO.__list_fill__ = debug_list_fill

def test_debug_write():
    """Test the debug write process."""
    nwbfile = mock_NWBFile()
    # Add PlaneSegmentation with pixel_mask
    n_rois = 2
    plane_segmentation = PlaneSegmentation(
        description="no description.",
        imaging_plane=mock_ImagingPlane(nwbfile=nwbfile),
        name="PlaneSegmentation",
    )

    for i in range(n_rois):
        pixel_mask = [(x, x, 1.0) for x in range(2)]
        plane_segmentation.add_roi(pixel_mask=pixel_mask)

    if "ophys" not in nwbfile.processing:
        nwbfile.create_processing_module("ophys", "ophys")
    nwbfile.processing["ophys"].add(plane_segmentation)

    # Use temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # write it to disk
        nwbfile_path = os.path.join(temp_dir, "debug.nwb")
        with NWBZarrIO(nwbfile_path, "w") as write_io:
            write_io.write(nwbfile)

if __name__ == "__main__":
    test_debug_write()