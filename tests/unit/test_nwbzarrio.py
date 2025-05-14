import unittest
from hdmf_zarr import NWBZarrIO
import os
import shutil
from datetime import datetime
from dateutil.tz import tzlocal
import numpy as np

try:
    from pynwb import NWBFile
    from pynwb.ophys import PlaneSegmentation
    from pynwb.testing.mock.file import mock_NWBFile
    from pynwb.testing.mock.ophys import mock_ImagingPlane

    PYNWB_AVAILABLE = True
except ImportError:
    PYNWB_AVAILABLE = False


@unittest.skipIf(not PYNWB_AVAILABLE, "PyNWB not installed")
class TestNWBZarrIO(unittest.TestCase):

    def setUp(self):
        self.filepath = "test_io.zarr"

    def tearDown(self):
        if os.path.exists(self.filepath):
            shutil.rmtree(self.filepath)

    def write_test_file(self):
        # Create the NWBFile
        nwbfile = NWBFile(
            session_description="my first synthetic recording",
            identifier="EXAMPLE_ID",
            session_start_time=datetime.now(tzlocal()),
            experimenter="Dr. Bilbo Baggins",
            lab="Bag End Laboratory",
            institution="University of Middle Earth at the Shire",
            experiment_description="I went on an adventure with thirteen dwarves to reclaim vast treasures.",
            session_id="LONELYMTN",
        )

        # Create a device
        nwbfile.create_device(name="array", description="the best array", manufacturer="Probe Company 9000")
        with NWBZarrIO(path=self.filepath, mode="w") as io:
            io.write(nwbfile)

    def test_read_nwb(self):
        """
        Test reading a local file with NWBZarrIO.read_nwb.

        NOTE: See TestFSSpecStreaming.test_fsspec_streaming_via_read_nwb for corresponding tests
              for reading a remote file with NWBZarrIO.read_nwb
        """
        self.write_test_file()
        nwbfile = NWBZarrIO.read_nwb(path=self.filepath)
        self.assertEqual(len(nwbfile.devices), 1)
        self.assertTupleEqual(nwbfile.experimenter, ("Dr. Bilbo Baggins",))

class TestNWBZarrIOCompoundDtype(unittest.TestCase):
    def setUp(self):
        self.filepath = "test_io.zarr"

    def tearDown(self):
        if os.path.exists(self.filepath):
            shutil.rmtree(self.filepath)

    def test_write_dataset_compound_dtype(self):
        # Create a mock NWB file with pixel_mask PlaneSegmentation
        nwbfile = mock_NWBFile()
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

        # write it to disk
        with NWBZarrIO(self.filepath, "w") as read_io:
            read_io.write(nwbfile)

        # read it back
        with NWBZarrIO(self.filepath, "r") as read_io:
            nwbfile = read_io.read()
            expected_dtype = np.dtype([('x', '<u4'), ('y', '<u4'), ('weight', '<f4')])
            actual_dtype = nwbfile.processing["ophys"].data_interfaces['PlaneSegmentation'].pixel_mask.data.dtype

            self.assertEqual(actual_dtype.descr, expected_dtype.descr)
