"""Debug script to understand the data shape issue."""
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane
from hdmf_zarr import NWBZarrIO
import numpy as np
import tempfile
import os
from hdmf.utils import get_data_shape

def debug_data_shape():
    """Debug the data shape issue."""
    nwbfile = mock_NWBFile()
    # Add PlaneSegmentation with pixel_mask
    n_rois = 3  # Small number for easier debugging
    plane_segmentation = PlaneSegmentation(
        description="no description.",
        imaging_plane=mock_ImagingPlane(nwbfile=nwbfile),
        name="PlaneSegmentation",
    )

    for i in range(n_rois):
        pixel_mask = [(x, x, 1.0) for x in range(2)]  # Only 2 pixels per ROI
        plane_segmentation.add_roi(pixel_mask=pixel_mask)

    if "ophys" not in nwbfile.processing:
        nwbfile.create_processing_module("ophys", "ophys")
    nwbfile.processing["ophys"].add(plane_segmentation)

    print("=== ORIGINAL DATA ===")
    original_data = nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data
    print(f"Original data: {original_data[:]}")
    original_array = np.array(original_data[:])
    print(f"Original data shape: {original_array.shape}")
    print(f"Original data dtype: {original_array.dtype}")
    print(f"get_data_shape(original_data): {get_data_shape(original_data)}")

    # Use temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # write it to disk
        nwbfile_path = os.path.join(temp_dir, "debug.nwb")
        with NWBZarrIO(nwbfile_path, "w") as write_io:
            write_io.write(nwbfile)

        # read it back
        with NWBZarrIO(nwbfile_path, "r") as read_io:
            read_nwbfile = read_io.read()
            
            print("\n=== AFTER READ ===")
            read_data = read_nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data
            raw_data = read_data[:]
            print(f"Read data: {raw_data}")
            print(f"Read data shape: {raw_data.shape}")
            print(f"Read data dtype: {raw_data.dtype}")
            print(f"get_data_shape(read_data): {get_data_shape(read_data)}")
            print(f"Type of read_data: {type(read_data)}")
            
            # Check if the data is a Zarr array
            if hasattr(read_data, 'shape'):
                print(f"read_data.shape: {read_data.shape}")
            
            # Let's manually check what get_data_shape returns
            print(f"Raw data shape: {raw_data.shape}")
            print(f"get_data_shape(raw_data): {get_data_shape(raw_data)}")
            
            # Check individual elements
            print(f"First element: {raw_data[0]}")
            print(f"First element shape: {raw_data[0].shape}")
            print(f"First element content: {raw_data[0][0]}, {raw_data[0][1]}, {raw_data[0][2]}")
            
            # Let's check if this is the issue with compound data
            if raw_data.dtype.names:
                print(f"Compound dtype detected: {raw_data.dtype}")
                print(f"Field names: {raw_data.dtype.names}")
                print(f"Field types: {[raw_data.dtype.fields[name][0] for name in raw_data.dtype.names]}")
                
                # Let's see what the first element's fields look like
                first_elem = raw_data[0]
                print(f"First element x field: {first_elem['x']}")
                print(f"First element y field: {first_elem['y']}")
                print(f"First element weight field: {first_elem['weight']}")
                
                # Check if the issue is with the compound data fields being duplicated
                for i, field_name in enumerate(raw_data.dtype.names):
                    field_data = raw_data[field_name]
                    print(f"Field '{field_name}' data: {field_data}")
                    print(f"Field '{field_name}' shape: {field_data.shape}")
                    print(f"Field '{field_name}' data: {field_data[:3]}")  # First 3 elements

if __name__ == "__main__":
    debug_data_shape()