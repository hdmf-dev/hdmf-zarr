"""Test to reproduce the pixel mask export bug."""
from pynwb.ophys import PlaneSegmentation
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.ophys import mock_ImagingPlane
from hdmf_zarr import NWBZarrIO
import numpy as np
import tempfile
import os

def test_export_pixel_mask():
    """Test the pixel mask export bug."""
    nwbfile = mock_NWBFile()
    # Add PlaneSegmentation with pixel_mask
    n_rois = 10
    plane_segmentation = PlaneSegmentation(
        description="no description.",
        imaging_plane=mock_ImagingPlane(nwbfile=nwbfile),
        name="PlaneSegmentation",
    )

    for _ in range(n_rois):
        pixel_mask = [(x, x, 1.0) for x in range(10)]
        plane_segmentation.add_roi(pixel_mask=pixel_mask)

    if "ophys" not in nwbfile.processing:
        nwbfile.create_processing_module("ophys", "ophys")
    nwbfile.processing["ophys"].add(plane_segmentation)

    print("Before write")
    print(f"{np.array(nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:]).shape = }") # (100, 3)
    print(f"{nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:3] = }") # [(0, 0, 1.0), (1, 1, 1.0), (2, 2, 1.0)]

    # Use temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # write it to disk
        nwbfile_path = os.path.join(temp_dir, "pixel_mask_export_bug.nwb")
        with NWBZarrIO(nwbfile_path, "w") as read_io:
            read_io.write(nwbfile)

        # read it back
        with NWBZarrIO(nwbfile_path, "r") as read_io:
            nwbfile = read_io.read()

            print("After write, before export")
            print(f"{nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:].shape = }") # (100, 3)
            print(f"{nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:3] = }")
            # array([[(0, 0, 1.), (0, 0, 1.), (0, 0, 1.)],
            # [(1, 1, 1.), (1, 1, 1.), (1, 1, 1.)],
            # [(2, 2, 1.), (2, 2, 1.), (2, 2, 1.)]],
            # dtype=[('x', '<u4'), ('y', '<u4'), ('weight', '<f4')])

            # Export to a new path
            export_path = os.path.join(temp_dir, "pixel_mask_export_bug_exported.nwb")
            with NWBZarrIO(export_path, "w") as export_io:
                nwbfile.set_modified()
                export_io.export(nwbfile=nwbfile, src_io=read_io, write_args=dict(link_data=False))
    
        # Check first export
        with NWBZarrIO(export_path, "r") as export_io:
            nwbfile = export_io.read()
            print("After export")
            print(f"{nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:].shape = }") # (100, 3, 3)
            print(f"{nwbfile.processing['ophys'].data_interfaces['PlaneSegmentation'].pixel_mask.data[:3] = }")
            # array([[[(0, 0, 0.), (0, 0, 0.), (1, 1, 1.)],
        #     [(0, 0, 0.), (0, 0, 0.), (1, 1, 1.)],
        #     [(0, 0, 0.), (0, 0, 0.), (1, 1, 1.)]],

        #    [[(1, 1, 1.), (1, 1, 1.), (1, 1, 1.)],
        #     [(1, 1, 1.), (1, 1, 1.), (1, 1, 1.)],
        #     [(1, 1, 1.), (1, 1, 1.), (1, 1, 1.)]],

        #    [[(2, 2, 2.), (2, 2, 2.), (1, 1, 1.)],
        #     [(2, 2, 2.), (2, 2, 2.), (1, 1, 1.)],
        #     [(2, 2, 2.), (2, 2, 2.), (1, 1, 1.)]]]],
        #   dtype=[('x', '<u4'), ('y', '<u4'), ('weight', '<f4')])

            # Try another export (this will fail)
            try:
                double_export_path = os.path.join(temp_dir, "pixel_mask_export_bug_exported_double.nwb")
                with NWBZarrIO(double_export_path, "w") as double_export_io:
                    nwbfile.set_modified()
                    double_export_io.export(nwbfile=nwbfile, src_io=export_io, write_args=dict(link_data=False))  # This line throws an error
            except Exception as e:
                print(f"Error during double export: {e}")


if __name__ == "__main__":
    test_export_pixel_mask()