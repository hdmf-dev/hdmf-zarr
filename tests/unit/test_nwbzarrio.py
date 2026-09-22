import unittest
from unittest.mock import patch
from hdmf_zarr import NWBZarrIO
import os
import shutil
from datetime import datetime
from dateutil.tz import tzlocal
import numpy as np
import zarr

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
        nwbfile.create_device(name="array", description="the best array")
        with NWBZarrIO(path=self.filepath, mode="w") as io:
            io.write(nwbfile)

    def test_read_nwb(self):
        """
        Test reading a local file with NWBZarrIO.read_nwb.
        """
        self.write_test_file()
        nwbfile = NWBZarrIO.read_nwb(path=self.filepath)
        self.assertEqual(len(nwbfile.devices), 1)
        self.assertTupleEqual(nwbfile.experimenter, ("Dr. Bilbo Baggins",))

    def test_read_nwb_s3_uses_anonymous_storage_options(self):
        """
        An s3:// path is opened anonymously, so that public DANDI assets are readable
        without credentials.
        """
        with (
            patch("hdmf_zarr.nwb.NWBZarrIO.__init__", return_value=None) as mock_init,
            patch("hdmf_zarr.nwb.NWBZarrIO.read", return_value="nwbfile"),
        ):
            NWBZarrIO.read_nwb(path="s3://bucket/file.nwb.zarr")
        self.assertEqual(mock_init.call_args.kwargs["storage_options"], dict(anon=True))

    def test_read_nwb_local_path_passes_no_storage_options(self):
        """
        A local path is opened without storage options, so no fsspec store is constructed.
        """
        with (
            patch("hdmf_zarr.nwb.NWBZarrIO.__init__", return_value=None) as mock_init,
            patch("hdmf_zarr.nwb.NWBZarrIO.read", return_value="nwbfile"),
        ):
            NWBZarrIO.read_nwb(path="local.nwb.zarr")
        self.assertIsNone(mock_init.call_args.kwargs["storage_options"])


@unittest.skipIf(not PYNWB_AVAILABLE, "PyNWB not installed")
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
            expected_dtype = np.dtype([("x", "<u4"), ("y", "<u4"), ("weight", "<f4")])
            actual_dtype = nwbfile.processing["ophys"].data_interfaces["PlaneSegmentation"].pixel_mask.data.dtype

            self.assertEqual(actual_dtype.descr, expected_dtype.descr)

    def test_compound_dtype_export_no_duplication(self):
        """Test that compound data types are exported correctly without data duplication."""
        # Create a mock NWB file with pixel_mask PlaneSegmentation
        nwbfile = mock_NWBFile()
        n_rois = 5
        plane_segmentation = PlaneSegmentation(
            description="no description.",
            imaging_plane=mock_ImagingPlane(nwbfile=nwbfile),
            name="PlaneSegmentation",
        )
        for i in range(n_rois):
            pixel_mask = [(x, x, 1.0) for x in range(3)]  # 3 pixels per ROI
            plane_segmentation.add_roi(pixel_mask=pixel_mask)
        if "ophys" not in nwbfile.processing:
            nwbfile.create_processing_module("ophys", "ophys")
        nwbfile.processing["ophys"].add(plane_segmentation)

        # write it to disk
        with NWBZarrIO(self.filepath, "w") as write_io:
            write_io.write(nwbfile)

        # read it back
        with NWBZarrIO(self.filepath, "r") as read_io:
            read_nwbfile = read_io.read()

            # Check that the data has the correct shape
            pixel_mask_data = read_nwbfile.processing["ophys"].data_interfaces["PlaneSegmentation"].pixel_mask.data
            self.assertEqual(pixel_mask_data.shape, (15,))  # 5 ROIs * 3 pixels = 15 records

            # Check that the data is not duplicated
            first_record = pixel_mask_data[0]
            self.assertEqual(first_record["x"], 0)
            self.assertEqual(first_record["y"], 0)
            self.assertEqual(first_record["weight"], 1.0)

            # Export to a new file
            export_path = self.filepath + "_exported"
            with NWBZarrIO(export_path, "w") as export_io:
                read_nwbfile.set_modified()
                export_io.export(nwbfile=read_nwbfile, src_io=read_io, write_args=dict(link_data=False))

        # Read the exported file
        with NWBZarrIO(export_path, "r") as export_read_io:
            exported_nwbfile = export_read_io.read()

            # Check that the exported data still has the correct shape
            exported_pixel_mask_data = (
                exported_nwbfile.processing["ophys"].data_interfaces["PlaneSegmentation"].pixel_mask.data
            )
            self.assertEqual(exported_pixel_mask_data.shape, (15,))  # Still 15 records, not (15, 3)

            # Check that the data is still correct
            first_record = exported_pixel_mask_data[0]
            self.assertEqual(first_record["x"], 0)
            self.assertEqual(first_record["y"], 0)
            self.assertEqual(first_record["weight"], 1.0)

            # Test double export (this should not fail)
            double_export_path = self.filepath + "_double_exported"
            with NWBZarrIO(double_export_path, "w") as double_export_io:
                exported_nwbfile.set_modified()
                double_export_io.export(
                    nwbfile=exported_nwbfile, src_io=export_read_io, write_args=dict(link_data=False)
                )

        # Clean up additional files
        if os.path.exists(export_path):
            shutil.rmtree(export_path)
        if os.path.exists(double_export_path):
            shutil.rmtree(double_export_path)


@unittest.skipIf(not PYNWB_AVAILABLE, "PyNWB not installed")
class TestNWBZarrIOCompoundReferenceExport(unittest.TestCase):
    """Export of a file with a compound reference column (e.g., epochs.timeseries) using the
    default ``link_data=True`` path, which routes the descriptor produced by ``__read_dataset``
    straight into ``write_dataset`` without going through the BuildManager."""

    def setUp(self):
        self.filepath = "test_compound_ref_export.zarr"
        self.export_path = "test_compound_ref_export_exported.zarr"

    def tearDown(self):
        for path in (self.filepath, self.export_path):
            if os.path.exists(path):
                shutil.rmtree(path)

    def write_test_file(self):
        from pynwb import TimeSeries

        nwbfile = NWBFile(
            session_description="compound reference export",
            identifier="EXAMPLE_ID",
            session_start_time=datetime(2024, 1, 1, tzinfo=tzlocal()),
        )
        ts = TimeSeries(name="ts", data=np.arange(10.0), unit="v", rate=1.0)
        nwbfile.add_acquisition(ts)
        nwbfile.add_epoch(0.0, 1.0, timeseries=[ts])
        nwbfile.add_epoch(1.0, 2.0, timeseries=[ts])
        with NWBZarrIO(self.filepath, mode="w") as io:
            io.write(nwbfile)

    def test_export_with_link_data(self):
        self.write_test_file()

        with NWBZarrIO(self.filepath, mode="r") as read_io:
            with NWBZarrIO(self.export_path, mode="w") as export_io:
                export_io.export(src_io=read_io)

        # The on-disk form: a structured dtype whose reference field holds plain target paths.
        exported = zarr.open_group(self.export_path, mode="r")["intervals/epochs/timeseries"]
        self.assertEqual(exported.dtype.names, ("idx_start", "count", "timeseries"))
        self.assertEqual(exported.attrs["_REFERENCE_FIELDS"], ["timeseries"])
        self.assertEqual(exported.shape, (2,))
        rows = exported[:]
        for row in range(2):
            self.assertEqual(int(rows[row]["idx_start"]), row)
            self.assertEqual(int(rows[row]["count"]), 1)
            self.assertEqual(str(rows[row]["timeseries"]), "/acquisition/ts")

        # The exported file reads back and each stored path resolves to the TimeSeries it names.
        with NWBZarrIO(self.export_path, mode="r") as io:
            exported_nwbfile = io.read()
            ts = exported_nwbfile.acquisition["ts"]
            for row in range(2):
                entry = exported_nwbfile.epochs["timeseries"][row][0]
                self.assertEqual(entry.idx_start, row)
                self.assertEqual(entry.count, 1)
                self.assertIs(entry.timeseries, ts)

    def test_validate_file_with_compound_reference_column(self):
        from pynwb import validate

        self.write_test_file()
        with NWBZarrIO(self.filepath, mode="r") as io:
            errors = validate(io=io)
        self.assertEqual(errors, [])
