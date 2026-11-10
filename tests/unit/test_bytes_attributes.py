"""Tests for storing bytes attributes with the Bytes Attributes Zarr convention."""

import json
import math
import os
import shutil

import numpy as np
from hdmf.build import DatasetBuilder, GroupBuilder
from hdmf.testing import TestCase

from hdmf_zarr import ZarrIO
from hdmf_zarr.bytes_attributes import (
    BYTES_ATTRIBUTES_CONVENTION,
    decode,
    encode,
    has_bytes,
    is_registered,
    text_or_bytes,
)
from hdmf_zarr.non_finite_attributes import CONVENTIONS_ATTR, NON_FINITE_ATTRIBUTES_CONVENTION

LATIN1 = "Müller".encode("latin-1")


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
        (b"", "base64:"),
        (b"\x00\xff", "base64:AP8="),
        (b"abc", "base64:YWJj"),
        ("base64:AP8=", "_str_base64:AP8="),
        ("base64:", "_str_base64:"),
        ("_str_base64:AP8=", "_str__str_base64:AP8="),
        ("base64", "base64"),
        ("Base64:AP8=", "Base64:AP8="),
        ("_str_hello", "_str_hello"),
        ("NaN", "NaN"),
        ("", ""),
        (1.5, 1.5),
        (None, None),
    ]

    def test_vectors(self):
        for decoded, encoded in self.VECTORS:
            with self.subTest(decoded=decoded):
                self.assertEqual(encode(decoded), encoded)
                result = decode(encoded)
                self.assertIs(type(result), type(decoded))
                self.assertEqual(result, decoded)

    def test_invalid_payloads_are_rejected(self):
        for encoded in ("base64:AP8", "base64:AP9=", "base64:-_8=", "base64:AP8= ", "base64:A"):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                decode(encoded)

    def test_has_bytes(self):
        for value in (LATIN1, np.bytes_(LATIN1), [b"ok", LATIN1], np.array([b"ok", LATIN1]), {"a": (LATIN1,)}):
            self.assertTrue(has_bytes(value), value)
        for value in (b"ascii", np.bytes_(b"ascii"), "Müller", np.array([b"ok"]), [1, "x"], None, 1.5):
            self.assertFalse(has_bytes(value), value)

    def test_text_or_bytes(self):
        self.assertEqual(text_or_bytes(np.array([b"ok", LATIN1])), ["ok", LATIN1])
        self.assertEqual(text_or_bytes((np.bytes_(b"a"), 1)), ("a", 1))


class TestZarrIOBytesAttributes(TestCase):
    """Attributes written and read through ZarrIO."""

    def setUp(self):
        self.store_path = "test_bytes_attributes.zarr"

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

    def test_roundtrip(self):
        """Bytes that are not valid UTF-8 come back as bytes, and everything else as before."""
        builder = GroupBuilder(
            name="root",
            attributes={
                "operator": np.bytes_(LATIN1),
                "labels": np.array([b"ok", LATIN1]),
                "ascii": np.bytes_(b"plain text"),
                "looks_encoded": "base64:AP8=",
                "number": 2.5,
            },
            datasets={"data": DatasetBuilder(name="data", data=np.arange(4), attributes={"digest": LATIN1})},
        )
        self._write(builder)

        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertEqual(stored[CONVENTIONS_ATTR], [BYTES_ATTRIBUTES_CONVENTION])
        self.assertEqual(stored["operator"], "base64:TfxsbGVy")
        self.assertEqual(stored["labels"], ["ok", "base64:TfxsbGVy"])
        self.assertEqual(stored["ascii"], "plain text")
        self.assertEqual(stored["looks_encoded"], "_str_base64:AP8=")
        data = _load_strict(os.path.join(self.store_path, "data/zarr.json"))["attributes"]
        self.assertEqual(data["digest"], "base64:TfxsbGVy")

        read = self._read()
        self.assertNotIn(CONVENTIONS_ATTR, read.attributes)
        self.assertEqual(read.attributes["operator"], LATIN1)
        self.assertEqual(list(read.attributes["labels"]), ["ok", LATIN1])
        self.assertEqual(read.attributes["ascii"], "plain text")
        self.assertEqual(read.attributes["looks_encoded"], "base64:AP8=")
        self.assertEqual(read.attributes["number"], 2.5)
        self.assertEqual(read.datasets["data"].attributes["digest"], LATIN1)

    def test_node_without_bytes_is_unchanged(self):
        """A node that holds only text does not register the convention, and its strings are not escaped."""
        self._write(GroupBuilder(name="root", attributes={"note": "base64:AP8=", "ascii": np.bytes_(b"x")}))
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertNotIn(CONVENTIONS_ATTR, stored)
        self.assertEqual(stored["note"], "base64:AP8=")
        self.assertFalse(is_registered(stored))
        self.assertEqual(self._read().attributes["note"], "base64:AP8=")

    def test_with_non_finite_attributes(self):
        """A node with both NaN and bytes registers both conventions, and both decode."""
        other = {"uuid": "00000000-0000-0000-0000-000000000000", "name": "other"}
        self._write(
            GroupBuilder(
                name="root",
                attributes={
                    CONVENTIONS_ATTR: [other],
                    "resolution": float("nan"),
                    "digest": b"\x10\xff",
                    "a": "NaN",
                    "b": "base64:Q",
                },
            )
        )
        stored = _load_strict(os.path.join(self.store_path, "zarr.json"))["attributes"]
        self.assertEqual(
            stored[CONVENTIONS_ATTR], [other, NON_FINITE_ATTRIBUTES_CONVENTION, BYTES_ATTRIBUTES_CONVENTION]
        )
        self.assertEqual(stored["resolution"], "NaN")
        self.assertEqual(stored["digest"], "base64:EP8=")
        self.assertEqual(stored["a"], "_str_NaN")
        self.assertEqual(stored["b"], "_str_base64:Q")

        read = self._read()
        self.assertEqual(read.attributes[CONVENTIONS_ATTR], [other])
        self.assertTrue(math.isnan(read.attributes["resolution"]))
        self.assertEqual(read.attributes["digest"], b"\x10\xff")
        self.assertEqual(read.attributes["a"], "NaN")
        self.assertEqual(read.attributes["b"], "base64:Q")
