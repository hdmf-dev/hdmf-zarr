"""Tests for storing NaN and infinite attributes with the Non-Finite Attributes Zarr convention."""

import json
import math
import os
import shutil
import unittest
from datetime import datetime, timezone

import numpy as np
import zarr
from hdmf.build import DatasetBuilder, GroupBuilder
from hdmf.testing import TestCase

from hdmf_zarr import ZarrIO
from hdmf_zarr.non_finite_attributes import (
    CONVENTIONS_ATTR,
    NON_FINITE_ATTRIBUTES_CONVENTION,
    NON_FINITE_ATTRIBUTES_UUID,
    decode,
    encode,
    has_non_finite,
    is_registered,
)

try:
    from pynwb import NWBFile, TimeSeries, validate

    from hdmf_zarr import NWBZarrIO

    PYNWB_AVAILABLE = True
except ImportError:
    PYNWB_AVAILABLE = False


def _refuse_constant(name):
    raise ValueError(f"{name} is not valid JSON")


def _load_strict(path):
    """Read a JSON file, refusing the bare tokens NaN, Infinity, and -Infinity."""
    with open(path) as f:
        return json.load(f, parse_constant=_refuse_constant)


class TestEncoding(TestCase):
    """The encoding rules, checked against the convention's test vectors."""

    # (decoded value, encoded value)
    VECTORS = [
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
        ("NaN", "_str_NaN"),
        ("Infinity", "_str_Infinity"),
        ("-Infinity", "_str_-Infinity"),
        ("_str_NaN", "_str__str_NaN"),
        ("_str__str_NaN", "_str__str__str_NaN"),
        ("_str_hello", "_str_hello"),
        ("_str_", "_str_"),
        ("nan", "nan"),
        ("inf", "inf"),
        ("+Infinity", "+Infinity"),
        ("NaN ", "NaN "),
        ("NaNNaN", "NaNNaN"),
        ("_STR_NaN", "_STR_NaN"),
        ("0x7fc00000", "0x7fc00000"),
        ("", ""),
        (1.5, 1.5),
        (0, 0),
        (None, None),
        (True, True),
    ]

    @staticmethod
    def _same(a, b):
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a):
            return math.isnan(b)
        return type(a) is type(b) and a == b

    def test_vectors(self):
        for decoded, encoded in self.VECTORS:
            with self.subTest(decoded=decoded):
                self.assertTrue(self._same(encode(decoded), encoded))
                self.assertTrue(self._same(decode(encoded), decoded))

    def test_nested_values(self):
        value = {"a": [1.0, float("inf"), "NaN"], "b": {"c": "_str_NaN", "d": (float("-inf"),)}}
        expected = {"a": [1.0, "Infinity", "_str_NaN"], "b": {"c": "_str__str_NaN", "d": ("-Infinity",)}}
        self.assertEqual(encode(value), expected)
        self.assertEqual(decode(expected), value)

    def test_numpy_values(self):
        self.assertEqual(encode(np.float32("nan")), "NaN")
        self.assertEqual(encode(np.float64("-inf")), "-Infinity")
        self.assertEqual(encode(np.array([1.0, np.inf])), [1.0, "Infinity"])
        self.assertEqual(encode(np.float32(1.5)), np.float32(1.5))

    def test_has_non_finite(self):
        for value in (float("nan"), np.float32("inf"), [1, [2.0, float("-inf")]], np.array([np.nan]), {"a": (np.nan,)}):
            self.assertTrue(has_non_finite(value), value)
        for value in (1.5, "NaN", [1, "Infinity"], np.array([1.0, 2.0]), np.array(["NaN"]), None, {"a": 1}):
            self.assertFalse(has_non_finite(value), value)


class TestZarrIONonFiniteAttributes(TestCase):
    """Attributes written and read through ZarrIO."""

    def setUp(self):
        self.store_path = "test_non_finite.zarr"

    def tearDown(self):
        if os.path.exists(self.store_path):
            shutil.rmtree(self.store_path)

    def _write(self, builder):
        # ZarrIO sets up its queue of data iterators when it writes the first dataset
        if not builder.datasets:
            builder.set_dataset(DatasetBuilder(name="values", data=np.arange(3)))
        with ZarrIO(self.store_path, mode="w") as io:
            io.write_builder(builder)

    def _read(self):
        io = ZarrIO(self.store_path, mode="r")
        io.open()
        self.addCleanup(io.close)
        return io.read_builder()

    def test_roundtrip_of_groups_and_datasets(self):
        """Numbers and strings come back as written, from valid JSON, on groups and datasets alike."""
        attributes = {
            "float_nan": float("nan"),
            "float_inf": float("inf"),
            "np_ninf": np.float32("-inf"),
            "scalar_array": np.array(np.nan),
            "list_nan": [1.0, float("nan")],
            "array_inf": np.array([1.0, -np.inf]),
            "text_nan": "NaN",
            "text_escaped": "_str_NaN",
            "text": "hello",
            "number": 2.5,
        }
        builder = GroupBuilder(
            name="root",
            attributes=dict(attributes),
            groups={"child": GroupBuilder(name="child", attributes={"gain": float("inf")})},
            datasets={
                "data": DatasetBuilder(name="data", data=np.arange(4), attributes={"resolution": float("nan")}),
            },
        )
        self._write(builder)

        for path in ("zarr.json", "child/zarr.json", "data/zarr.json"):
            stored = _load_strict(os.path.join(self.store_path, path))["attributes"]
            self.assertEqual(stored[CONVENTIONS_ATTR], [NON_FINITE_ATTRIBUTES_CONVENTION])
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertEqual(stored["float_nan"], "NaN")
        self.assertEqual(stored["np_ninf"], "-Infinity")
        self.assertEqual(stored["array_inf"], [1.0, "-Infinity"])
        self.assertEqual(stored["text_nan"], "_str_NaN")
        self.assertEqual(stored["text_escaped"], "_str__str_NaN")
        self.assertEqual(stored["text"], "hello")

        read = self._read()
        self.assertNotIn(CONVENTIONS_ATTR, read.attributes)
        self.assertTrue(math.isnan(read.attributes["float_nan"]))
        self.assertEqual(read.attributes["float_inf"], float("inf"))
        self.assertEqual(read.attributes["np_ninf"], float("-inf"))
        self.assertTrue(math.isnan(read.attributes["scalar_array"]))
        self.assertEqual(read.attributes["list_nan"][0], 1.0)
        self.assertTrue(math.isnan(read.attributes["list_nan"][1]))
        self.assertEqual(list(read.attributes["array_inf"]), [1.0, float("-inf")])
        self.assertEqual(read.attributes["text_nan"], "NaN")
        self.assertEqual(read.attributes["text_escaped"], "_str_NaN")
        self.assertEqual(read.attributes["text"], "hello")
        self.assertEqual(read.attributes["number"], 2.5)
        self.assertEqual(read.groups["child"].attributes["gain"], float("inf"))
        self.assertTrue(math.isnan(read.datasets["data"].attributes["resolution"]))

    def test_node_without_non_finite_numbers_is_unchanged(self):
        """A node that holds no such number does not register the convention, and its strings are not escaped."""
        self._write(GroupBuilder(name="root", attributes={"text_nan": "NaN", "number": 2.5}))
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertNotIn(CONVENTIONS_ATTR, stored)
        self.assertEqual(stored["text_nan"], "NaN")
        read = self._read()
        self.assertEqual(read.attributes["text_nan"], "NaN")
        self.assertIsInstance(read.attributes["text_nan"], str)

    def test_bare_tokens_written_by_earlier_versions_are_read(self):
        """hdmf-zarr 0.14.0 wrote the bare tokens, which are still read as numbers."""
        self._write(GroupBuilder(name="root", attributes={"number": 2.5}))
        root = zarr.open_group(self.store_path, mode="r+")
        root.attrs["resolution"] = float("nan")
        root.attrs["text_nan"] = "NaN"
        with open(os.path.join(self.store_path, "zarr.json")) as f:
            self.assertIn('"resolution": NaN', f.read())
        read = self._read()
        self.assertTrue(math.isnan(read.attributes["resolution"]))
        self.assertEqual(read.attributes["text_nan"], "NaN")

    def test_other_conventions_are_kept(self):
        """Conventions that a node names besides this one stay registered and are read back."""
        other = {"uuid": "00000000-0000-0000-0000-000000000000", "name": "other"}
        self._write(GroupBuilder(name="root", attributes={CONVENTIONS_ATTR: [other], "gain": float("inf")}))
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertEqual(stored[CONVENTIONS_ATTR], [other, NON_FINITE_ATTRIBUTES_CONVENTION])
        read = self._read()
        self.assertEqual(read.attributes[CONVENTIONS_ATTR], [other])
        self.assertEqual(read.attributes["gain"], float("inf"))

    def test_attributes_added_to_a_registered_node_are_encoded(self):
        """Once a node registers the convention, a string written to it later is escaped as well."""
        with ZarrIO(self.store_path, mode="w") as io:
            io.open()
            io.write_attributes(io._file, {"gain": float("inf")})
            io.write_attributes(io._file, {"text_nan": "NaN"})
            self.assertTrue(is_registered(io._file.attrs))
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertEqual(stored["text_nan"], "_str_NaN")
        self.assertEqual([entry["uuid"] for entry in stored[CONVENTIONS_ATTR]], [NON_FINITE_ATTRIBUTES_UUID])


@unittest.skipIf(not PYNWB_AVAILABLE, "PyNWB not installed")
class TestNWBNonFiniteAttributes(TestCase):
    """An NWB file whose TimeSeries has attributes that are not finite."""

    def setUp(self):
        self.store_path = "test_non_finite_nwb.zarr"

    def tearDown(self):
        if os.path.exists(self.store_path):
            shutil.rmtree(self.store_path)

    def _nwbfile(self):
        nwbfile = NWBFile(
            session_description="NaN",  # text that has the characters of a reserved string
            identifier="non-finite",
            session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        nwbfile.add_acquisition(
            TimeSeries(name="signal", data=np.arange(10.0), unit="V", rate=10.0, resolution=float("nan"))
        )
        return nwbfile

    def test_timeseries_resolution(self):
        with NWBZarrIO(self.store_path, mode="w") as io:
            io.write(self._nwbfile())

        # Every metadata document of the file is valid JSON
        for directory, _, files in os.walk(self.store_path):
            if "zarr.json" in files:
                _load_strict(os.path.join(directory, "zarr.json"))
        stored = _load_strict(os.path.join(self.store_path, "acquisition", "signal", "data", "zarr.json"))
        self.assertEqual(stored["attributes"]["resolution"], "NaN")

        with NWBZarrIO(self.store_path, mode="r") as io:
            read = io.read()
            self.assertTrue(math.isnan(read.acquisition["signal"].resolution))
            self.assertEqual(read.session_description, "NaN")
            self.assertEqual(validate(io=io), [])

    def test_export(self):
        """Values survive an export to a second file, which registers the convention where it needs it."""
        with NWBZarrIO(self.store_path, mode="w") as io:
            io.write(self._nwbfile())
        export_path = "test_non_finite_nwb_export.zarr"
        self.addCleanup(shutil.rmtree, export_path, True)
        with NWBZarrIO(self.store_path, mode="r") as read_io:
            with NWBZarrIO(export_path, mode="w") as export_io:
                export_io.export(src_io=read_io, write_args={"link_data": False})

        stored = _load_strict(os.path.join(export_path, "acquisition", "signal", "data", "zarr.json"))["attributes"]
        self.assertEqual(stored["resolution"], "NaN")
        self.assertEqual(stored[CONVENTIONS_ATTR], [NON_FINITE_ATTRIBUTES_CONVENTION])
        with NWBZarrIO(export_path, mode="r") as io:
            read = io.read()
            self.assertTrue(math.isnan(read.acquisition["signal"].resolution))
            self.assertEqual(read.session_description, "NaN")
