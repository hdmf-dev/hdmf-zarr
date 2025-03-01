import unittest
from hdmf_zarr import NWBZarrIO
from .utils import check_s3fs_ffspec_installed

import zarr

HAVE_FSSPEC = check_s3fs_ffspec_installed()


class TestFSSpecStreaming(unittest.TestCase):

    def setUp(self):
        # PLACEHOLDER test file from Allen Institute for Neural Dynamics
        # TODO: store a small test file and use it to speed up testing
        self.s3_aind_path = (
            "s3://aind-open-data/ecephys_625749_2022-08-03_15-15-06_nwb_2023-05-16_16-34-55/"
            "ecephys_625749_2022-08-03_15-15-06_nwb/"
            "ecephys_625749_2022-08-03_15-15-06_experiment1_recording1.nwb.zarr/"
        )
        # DANDISET: 000719/icephys_9_27_2024
        self.https_s3_path = "https://dandiarchive.s3.amazonaws.com/zarr/7515c603-9940-4598-aa1b-8bf32dc9b10c/"

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_fsspec_streaming(self):
        with NWBZarrIO(self.s3_aind_path, mode="r", storage_options=dict(anon=True)) as io:
            nwbfile = io.read()

        self.assertEqual(nwbfile.identifier, "ecephys_625749_2022-08-03_15-15-06")
        self.assertEqual(len(nwbfile.devices), 2)
        self.assertEqual(len(nwbfile.electrode_groups), 2)
        self.assertEqual(len(nwbfile.electrodes), 1152)
        self.assertEqual(nwbfile.institution, "AIND")

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_s3_open_with_consolidated_(self):
        """
        The file is a Zarr file with consolidated metadata.
        """
        with NWBZarrIO(self.https_s3_path, mode="r") as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.ConsolidatedMetadataStore)
        with NWBZarrIO(self.https_s3_path, mode="-r") as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.FSStore)

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_fsspec_streaming_via_read_nwb(self):
        """
        Test reading from s3 using the convenience function NWBZarrIO.read_nwb
        """
        # Test with a s3:// URL
        nwbfile = NWBZarrIO.read_nwb(self.s3_aind_path)
        self.assertEqual(nwbfile.identifier, "ecephys_625749_2022-08-03_15-15-06")
        self.assertEqual(nwbfile.institution, "AIND")
