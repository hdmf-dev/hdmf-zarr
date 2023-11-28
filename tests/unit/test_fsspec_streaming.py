import unittest
from hdmf_zarr import NWBZarrIO
from .utils import check_s3fs_ffspec_installed

HAVE_FSSPEC = check_s3fs_ffspec_installed()


class TestFSSpecStreaming(unittest.TestCase):
    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_fsspec_streaming(self):
        # PLACEHOLDER test file from Allen Institute for Neural Dynamics
        # TODO: store a small test file and use it to speed up testing
        remote_path = (
            "s3://aind-open-data/ecephys_625749_2022-08-03_15-15-06_nwb_2023-05-16_16-34-55/"
            "ecephys_625749_2022-08-03_15-15-06_nwb/"
            "ecephys_625749_2022-08-03_15-15-06_experiment1_recording1.nwb.zarr/"
        )

        with NWBZarrIO(remote_path, mode="r", storage_options=dict(anon=True)) as io:
            nwbfile = io.read()

        self.assertEqual(nwbfile.identifier, "ecephys_625749_2022-08-03_15-15-06")
        self.assertEqual(len(nwbfile.devices), 2)
        self.assertEqual(len(nwbfile.electrode_groups), 2)
        self.assertEqual(len(nwbfile.electrodes), 1152)
        self.assertEqual(nwbfile.institution, "AIND")
