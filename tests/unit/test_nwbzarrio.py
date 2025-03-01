import unittest
from hdmf_zarr import NWBZarrIO
import os
import shutil
from datetime import datetime
from dateutil.tz import tzlocal

try:
    from pynwb import NWBFile

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
