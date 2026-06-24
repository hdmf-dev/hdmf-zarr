import unittest
from hdmf_zarr import NWBZarrIO, NWBZarrV2IO
from .helpers.utils import check_s3fs_ffspec_installed

HAVE_FSSPEC = check_s3fs_ffspec_installed()


class TestFSSpecStreaming(unittest.TestCase):
    """Stream remote NWB Zarr files. The current S3 test fixtures are zarr v2, so
    these tests instantiate :class:`NWBZarrV2IO` directly; the convenience
    :meth:`NWBZarrIO.read_nwb` auto-dispatcher is exercised separately below."""

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
        with NWBZarrV2IO(self.s3_aind_path, mode="r", storage_options=dict(anon=True)) as io:
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
        In zarr v3, consolidated metadata is handled transparently.
        """
        with NWBZarrV2IO(self.https_s3_path, mode="r") as read_io:
            read_io.open()
            self.assertIsNotNone(read_io._file)

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_is_remote_with_consolidated(self):
        """Test that is_remote() returns True for remote HTTPS stores with consolidated metadata."""
        with NWBZarrV2IO(self.https_s3_path, mode="r") as read_io:
            read_io.open()
            self.assertTrue(read_io.is_remote())

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_is_remote_without_consolidated(self):
        """Test that is_remote() returns True for remote HTTPS stores without consolidated metadata."""
        with NWBZarrV2IO(self.https_s3_path, mode="r-") as read_io:
            read_io.open()
            self.assertTrue(read_io.is_remote())

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_fsspec_streaming_via_read_nwb(self):
        """
        Test reading from s3 using the convenience function NWBZarrIO.read_nwb
        """
        # Test with a s3:// URL
        nwbfile = NWBZarrIO.read_nwb(self.s3_aind_path)
        self.assertEqual(nwbfile.identifier, "ecephys_625749_2022-08-03_15-15-06")
        self.assertEqual(nwbfile.institution, "AIND")

    @unittest.skipIf(not HAVE_FSSPEC, "fsspec not installed")
    def test_resolve_ref_self_reference_over_fsspec(self):
        """Regression: `resolve_ref` must not re-open the URL for `source == "."` self-references.

        Without the fix in `ZarrIO.resolve_ref`, reading any non-trivial NWB Zarr file over
        fsspec fails with `PathNotFoundError: nothing found at path ''` because hdmf-zarr
        writes every same-file reference as `{"source": ".", "path": ...}` and the resolver
        previously passed the `"."` to `__open_file_consolidated`, which interpreted it as
        an empty key in the fsspec store. The fix short-circuits the `"."` case and reuses
        the already-open file directly. This test reads a public DANDI Zarr file end-to-end
        and asserts the read completes; without the fix, the call raises before returning.
        """
        # DANDI 000719 file used in this repo's S3 streaming tutorial (PR #330).
        url = "https://dandiarchive.s3.amazonaws.com/zarr/c8c6b848-fbc6-4f58-85ff-e3f2618ee983/"
        nwbfile = NWBZarrIO.read_nwb(url)
        self.assertEqual(nwbfile.identifier, "7208f856-f527-479f-973d-e6e72326a8ea")
        self.assertIsNotNone(nwbfile.subject)
        self.assertEqual(nwbfile.subject.subject_id, "R6")
