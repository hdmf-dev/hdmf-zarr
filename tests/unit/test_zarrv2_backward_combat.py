"""Backward compatibility test: read a zarr v2 NWB file with the current (zarr v3) code.

This test reads a NWB zarr file that was generated with hdmf-zarr<1.0 + zarr<3
(see ``helpers/generate_nwb_zarrv2.py``) and validates that key metadata and
data can be read correctly.

The test file and its expected metadata are produced by the companion generation
script and placed at a known location by CI (see
``.github/workflows/test_backward_compat.yml``).

To run locally::

    # Step 1 — generate the v2 file in a temporary venv
    python -m venv /tmp/zarr_v2_env
    /tmp/zarr_v2_env/bin/pip install "hdmf-zarr<1.0" "zarr>=2.18,<3" pynwb
    /tmp/zarr_v2_env/bin/python tests/unit/helpers/generate_nwb_zarrv2.py \
        tests/unit/helpers/v2_test_file.nwb.zarr \
        > tests/unit/helpers/v2_expected.json

    # Step 2 — run this test with the current code
    pytest tests/unit/test_zarrv2_backward_compat.py -v
"""

import json
import os
import shutil
import tempfile
import unittest
import warnings

import numpy as np

from hdmf_zarr import NWBZarrIO, NWBZarrV2IO, is_zarr_v2_file

# Paths relative to the repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
_HELPERS = os.path.join(_HERE, "helpers")
_V2_FILE = os.path.join(_HELPERS, "v2_test_file.nwb.zarr")
_V2_EXPECTATIONS = os.path.join(_HELPERS, "v2_expected.json")

_HAS_V2_FILE = os.path.exists(_V2_FILE) and os.path.exists(_V2_EXPECTATIONS)


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_v2_nwb_zarr.py first")
class TestV2BackwardCompat(unittest.TestCase):
    """Read a zarr v2 NWB file and verify metadata and data integrity."""

    @classmethod
    def setUpClass(cls):
        with open(_V2_EXPECTATIONS, "r") as f:
            cls.expected = json.load(f)

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            cls.io = NWBZarrV2IO(_V2_FILE, mode="r")
            cls.nwbfile = cls.io.read()

    @classmethod
    def tearDownClass(cls):
        cls.io.close()

    # ---- scalar / string metadata ----

    def test_identifier(self):
        self.assertEqual(self.nwbfile.identifier, self.expected["identifier"])

    def test_session_description(self):
        self.assertEqual(self.nwbfile.session_description, self.expected["session_description"])

    def test_session_id(self):
        self.assertEqual(self.nwbfile.session_id, self.expected["session_id"])

    def test_lab(self):
        self.assertEqual(self.nwbfile.lab, self.expected["lab"])

    def test_institution(self):
        self.assertEqual(self.nwbfile.institution, self.expected["institution"])

    def test_experiment_description(self):
        self.assertEqual(self.nwbfile.experiment_description, self.expected["experiment_description"])

    # ---- datetime fields (fill_value=0 issue) ----

    def test_session_start_time(self):
        self.assertIsNotNone(self.nwbfile.session_start_time)

    def test_timestamps_reference_time(self):
        self.assertIsNotNone(self.nwbfile.timestamps_reference_time)

    # ---- subject (object-dtype date_of_birth) ----

    def test_subject_exists(self):
        self.assertIsNotNone(self.nwbfile.subject)

    def test_subject_id(self):
        self.assertEqual(self.nwbfile.subject.subject_id, self.expected["subject_id"])

    def test_subject_species(self):
        self.assertEqual(self.nwbfile.subject.species, self.expected["subject_species"])

    def test_subject_sex(self):
        self.assertEqual(self.nwbfile.subject.sex, self.expected["subject_sex"])

    def test_subject_age(self):
        self.assertEqual(self.nwbfile.subject.age, self.expected["subject_age"])

    def test_subject_date_of_birth(self):
        self.assertIsNotNone(self.nwbfile.subject.date_of_birth)

    # ---- devices / electrode groups (object references) ----

    def test_n_devices(self):
        self.assertEqual(len(self.nwbfile.devices), self.expected["n_devices"])

    def test_device_name(self):
        self.assertIn(self.expected["device_name"], self.nwbfile.devices)

    def test_n_electrode_groups(self):
        self.assertEqual(len(self.nwbfile.electrode_groups), self.expected["n_electrode_groups"])

    def test_electrode_group_name(self):
        self.assertIn(self.expected["electrode_group_name"], self.nwbfile.electrode_groups)

    # ---- electrodes table (object-dtype 'group' column) ----

    def test_n_electrodes(self):
        self.assertEqual(len(self.nwbfile.electrodes), self.expected["n_electrodes"])

    def test_electrodes_columns(self):
        col_names = self.nwbfile.electrodes.colnames
        for expected_col in ("x", "y", "z", "location", "group", "filtering"):
            self.assertIn(expected_col, col_names)

    def test_electrodes_group_column(self):
        """The 'group' column has |O dtype with pickle codec — verify it reads."""
        groups = self.nwbfile.electrodes["group"]
        self.assertEqual(len(groups), self.expected["n_electrodes"])

    # ---- acquisition data (numerical, normal zarr path) ----

    def test_ephys_exists(self):
        self.assertIn(self.expected["ephys_name"], self.nwbfile.acquisition)

    def test_ephys_data_shape(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        expected_shape = tuple(self.expected["ephys_data_shape"])
        self.assertEqual(series.data.shape, expected_shape)

    def test_ephys_data_dtype(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        self.assertTrue(np.issubdtype(series.data.dtype, np.floating))

    def test_ephys_timestamps(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        n_samples = self.expected["ephys_data_shape"][0]
        # timestamps could be lazy (zarr Array) or eagerly loaded
        ts = np.asarray(series.timestamps)
        self.assertEqual(len(ts), n_samples)


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_v2_nwb_zarr.py first")
class TestV2SnifferAndAutoDispatch(unittest.TestCase):
    """The sniffer must identify v2 files, and NWBZarrIO.read_nwb must auto-dispatch."""

    def test_sniffer_detects_v2(self):
        self.assertTrue(is_zarr_v2_file(_V2_FILE))

    def test_read_nwb_auto_dispatches_to_v2(self):
        # Calling the v3 entry point on a v2 file should still succeed via the
        # sniffer-based dispatch in NWBZarrIO.read_nwb.
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            nwbfile = NWBZarrIO.read_nwb(_V2_FILE)
        self.assertIsNotNone(nwbfile)
        with open(_V2_EXPECTATIONS, "r") as f:
            expected = json.load(f)
        self.assertEqual(nwbfile.identifier, expected["identifier"])


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_v2_nwb_zarr.py first")
class TestV2ExportToV3(unittest.TestCase):
    """Export a zarr v2 NWB file to zarr v3 and verify it round-trips via the v3 reader."""

    @classmethod
    def setUpClass(cls):
        with open(_V2_EXPECTATIONS, "r") as f:
            cls.expected = json.load(f)

        cls.tmpdir = tempfile.mkdtemp()
        cls.v3_path = os.path.join(cls.tmpdir, "exported_v3.nwb.zarr")

        # Convert the v2 file to a new zarr v3 file using the one-shot static helper.
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            NWBZarrV2IO.convert_to_v3(_V2_FILE, cls.v3_path)

        # Read the exported file back with the v3 reader.
        cls.io = NWBZarrIO(cls.v3_path, mode="r")
        cls.nwbfile = cls.io.read()

    @classmethod
    def tearDownClass(cls):
        cls.io.close()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_exported_file_is_zarr_v3(self):
        """The exported file must be a zarr v3 hierarchy, not v2."""
        self.assertFalse(is_zarr_v2_file(self.v3_path))

    def test_read_nwb_dispatches_to_v3(self):
        """NWBZarrIO.read_nwb should read the exported file directly (no v2 dispatch)."""
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            nwbfile = NWBZarrIO.read_nwb(self.v3_path)
        self.assertEqual(nwbfile.identifier, self.expected["identifier"])

    # ---- scalar / string metadata ----

    def test_identifier(self):
        self.assertEqual(self.nwbfile.identifier, self.expected["identifier"])

    def test_session_description(self):
        self.assertEqual(self.nwbfile.session_description, self.expected["session_description"])

    def test_session_id(self):
        self.assertEqual(self.nwbfile.session_id, self.expected["session_id"])

    def test_lab(self):
        self.assertEqual(self.nwbfile.lab, self.expected["lab"])

    def test_institution(self):
        self.assertEqual(self.nwbfile.institution, self.expected["institution"])

    def test_experiment_description(self):
        self.assertEqual(self.nwbfile.experiment_description, self.expected["experiment_description"])

    # ---- datetime fields ----

    def test_session_start_time(self):
        self.assertIsNotNone(self.nwbfile.session_start_time)

    def test_timestamps_reference_time(self):
        self.assertIsNotNone(self.nwbfile.timestamps_reference_time)

    # ---- subject ----

    def test_subject_id(self):
        self.assertEqual(self.nwbfile.subject.subject_id, self.expected["subject_id"])

    def test_subject_species(self):
        self.assertEqual(self.nwbfile.subject.species, self.expected["subject_species"])

    def test_subject_date_of_birth(self):
        self.assertIsNotNone(self.nwbfile.subject.date_of_birth)

    # ---- devices / electrode groups ----

    def test_n_devices(self):
        self.assertEqual(len(self.nwbfile.devices), self.expected["n_devices"])

    def test_n_electrode_groups(self):
        self.assertEqual(len(self.nwbfile.electrode_groups), self.expected["n_electrode_groups"])

    # ---- electrodes table (object-dtype 'group' column) ----

    def test_n_electrodes(self):
        self.assertEqual(len(self.nwbfile.electrodes), self.expected["n_electrodes"])

    def test_electrodes_columns(self):
        col_names = self.nwbfile.electrodes.colnames
        for expected_col in ("x", "y", "z", "location", "group", "filtering"):
            self.assertIn(expected_col, col_names)

    def test_electrodes_group_column(self):
        groups = self.nwbfile.electrodes["group"]
        self.assertEqual(len(groups), self.expected["n_electrodes"])

    # ---- acquisition data ----

    def test_ephys_exists(self):
        self.assertIn(self.expected["ephys_name"], self.nwbfile.acquisition)

    def test_ephys_data_shape(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        self.assertEqual(series.data.shape, tuple(self.expected["ephys_data_shape"]))

    def test_ephys_data_dtype(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        self.assertTrue(np.issubdtype(series.data.dtype, np.floating))

    def test_ephys_timestamps(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        n_samples = self.expected["ephys_data_shape"][0]
        ts = np.asarray(series.timestamps)
        self.assertEqual(len(ts), n_samples)

    def test_ephys_data_values_match_v2(self):
        """Exported data values must match the original v2 file exactly."""
        with NWBZarrV2IO(_V2_FILE, mode="r") as v2_io:
            v2_nwbfile = v2_io.read()
            v2_data = np.asarray(v2_nwbfile.acquisition[self.expected["ephys_name"]].data)
        v3_data = np.asarray(self.nwbfile.acquisition[self.expected["ephys_name"]].data)
        np.testing.assert_array_equal(v3_data, v2_data)

    def test_instance_export_to_v3(self):
        """The instance method export_to_v3 should also produce a readable v3 file."""
        dest = os.path.join(self.tmpdir, "instance_export_v3.nwb.zarr")
        with warnings.catch_warnings():
            warnings.simplefilter("always")
            with NWBZarrV2IO(_V2_FILE, mode="r") as v2_io:
                v2_io.export_to_v3(path=dest)
        self.assertFalse(is_zarr_v2_file(dest))
        with NWBZarrIO(dest, mode="r") as io:
            nwbfile = io.read()
            self.assertEqual(nwbfile.identifier, self.expected["identifier"])


if __name__ == "__main__":
    unittest.main()
