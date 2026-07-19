"""Backward compatibility test: read a zarr v2 NWB file with the current (zarr v3) code.

This test reads a NWB zarr file that was generated with hdmf-zarr<1.0 + zarr<3
(see ``helpers/generate_nwb_zarrv2.py``) and validates that key metadata and
data can be read correctly.

The test file (``helpers/nwb_zarrv2_test.nwb.zarr``) and its expected metadata
(``helpers/nwb_zarrv2_expected.json``) are checked into the repository, so the
test runs without any generation step. To regenerate them (e.g. after changing
the generation script), run the script in a temporary venv with zarr v2::

    # Step 1 — regenerate the v2 fixture in a temporary venv
    python -m venv /tmp/zarr_v2_env
    /tmp/zarr_v2_env/bin/pip install "hdmf-zarr<1.0" "zarr>=2.18,<3" pynwb
    /tmp/zarr_v2_env/bin/python tests/unit/helpers/generate_nwb_zarrv2.py \
        --nwb-output-path tests/unit/helpers/nwb_zarrv2_test.nwb.zarr \
        --expectations-output-path tests/unit/helpers/nwb_zarrv2_expected.json

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

from hdmf_zarr import ZarrIO, NWBZarrIO, NWBZarrV2IO, is_zarr_v2_file

# Paths relative to the repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
_HELPERS = os.path.join(_HERE, "helpers")
_V2_FILE = os.path.join(_HELPERS, "nwb_zarrv2_test.nwb.zarr")
_V2_EXPECTATIONS = os.path.join(_HELPERS, "nwb_zarrv2_expected.json")

_HAS_V2_FILE = os.path.exists(_V2_FILE) and os.path.exists(_V2_EXPECTATIONS)


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_nwb_zarrv2.py first")
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
        t = self.nwbfile.session_start_time
        self.assertIsNotNone(t)
        self.assertEqual(t.year, self.expected["session_start_time_year"])
        self.assertEqual(t.month, self.expected["session_start_time_month"])
        self.assertEqual(t.day, self.expected["session_start_time_day"])

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

    def test_ephys_data_values(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        np.testing.assert_array_almost_equal(np.asarray(series.data), np.array(self.expected["ephys_data"]))

    def test_ephys_timestamps(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        np.testing.assert_array_almost_equal(np.asarray(series.timestamps), np.array(self.expected["ephys_timestamps"]))

    # ---- units table (ragged spike_times — VectorIndex / object-dtype) ----

    def test_units_exists(self):
        self.assertIsNotNone(self.nwbfile.units)

    def test_n_units(self):
        self.assertEqual(len(self.nwbfile.units), self.expected["n_units"])

    def test_units_spike_times(self):
        for i, expected_spikes in enumerate(self.expected["unit_spike_times"]):
            spikes = self.nwbfile.units["spike_times"][i]
            np.testing.assert_array_almost_equal(np.asarray(spikes), np.array(expected_spikes))

    def test_units_quality_column(self):
        labels = list(self.nwbfile.units["quality"][:])
        self.assertEqual(labels, self.expected["unit_quality_labels"])

    def test_is_zarr_v2_file(self):
        self.assertTrue(is_zarr_v2_file(_V2_FILE))


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_nwb_zarrv2.py first")
class TestV2ReadWithV3Backend(unittest.TestCase):
    """Reading a v2 file with the v3 backend must raise a message pointing at the v2 backend."""

    def _assert_helpful_v2_error(self, cm):
        msg = str(cm.exception)
        self.assertIn("Zarr v2 file", msg)
        self.assertIn("NWBZarrV2IO", msg)

    def test_nwbzarrio_default_raises_hint(self):
        """The default read path (load_namespaces=True) fails while opening for namespaces."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(ValueError) as cm:
                with NWBZarrIO(_V2_FILE, mode="r") as io:
                    io.read()
        self._assert_helpful_v2_error(cm)

    def test_nwbzarrio_no_namespaces_raises_hint(self):
        """With load_namespaces=False the failure surfaces later, still with the hint."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(ValueError) as cm:
                with NWBZarrIO(_V2_FILE, mode="r", load_namespaces=False) as io:
                    io.read()
        self._assert_helpful_v2_error(cm)

    def test_plain_zarrio_message_stays_in_hdmf_layer(self):
        """The base ZarrIO must point at ZarrV2IO and not reference the NWB-layer classes."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(ValueError) as cm:
                ZarrIO(_V2_FILE, mode="r")
        msg = str(cm.exception)
        self.assertIn("Zarr v2 file", msg)
        self.assertIn("ZarrV2IO", msg)
        self.assertNotIn("NWBZarrV2IO", msg)
        self.assertNotIn("NWBZarrIO", msg)


@unittest.skipIf(not _HAS_V2_FILE, "v2 test file not generated — run generate_nwb_zarrv2.py first")
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
            NWBZarrV2IO.convert_to_v3(source_path=_V2_FILE, dest_path=cls.v3_path)

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

    def test_read_nwb_from_to_v3(self):
        """NWBZarrIO.read_nwb should read the exported zarrv3 file directly."""
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
        t = self.nwbfile.session_start_time
        self.assertIsNotNone(t)
        self.assertEqual(t.year, self.expected["session_start_time_year"])
        self.assertEqual(t.month, self.expected["session_start_time_month"])
        self.assertEqual(t.day, self.expected["session_start_time_day"])

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

    def test_ephys_data_values(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        np.testing.assert_array_almost_equal(np.asarray(series.data), np.array(self.expected["ephys_data"]))

    def test_ephys_timestamps(self):
        series = self.nwbfile.acquisition[self.expected["ephys_name"]]
        np.testing.assert_array_almost_equal(np.asarray(series.timestamps), np.array(self.expected["ephys_timestamps"]))

    def test_ephys_data_values_match_v2(self):
        """Exported data values must match the original v2 file exactly."""
        with NWBZarrV2IO(_V2_FILE, mode="r") as v2_io:
            v2_nwbfile = v2_io.read()
            v2_data = np.asarray(v2_nwbfile.acquisition[self.expected["ephys_name"]].data)
        v3_data = np.asarray(self.nwbfile.acquisition[self.expected["ephys_name"]].data)
        np.testing.assert_array_equal(v3_data, v2_data)

    # ---- units table ----

    def test_units_exists(self):
        self.assertIsNotNone(self.nwbfile.units)

    def test_n_units(self):
        self.assertEqual(len(self.nwbfile.units), self.expected["n_units"])

    def test_units_spike_times(self):
        for i, expected_spikes in enumerate(self.expected["unit_spike_times"]):
            spikes = self.nwbfile.units["spike_times"][i]
            np.testing.assert_array_almost_equal(np.asarray(spikes), np.array(expected_spikes))

    def test_units_quality_column(self):
        labels = list(self.nwbfile.units["quality"][:])
        self.assertEqual(labels, self.expected["unit_quality_labels"])

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
