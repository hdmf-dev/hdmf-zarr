"""Tests for reading attributes stored with the Non-Finite Attributes Zarr convention."""

import math

from hdmf.testing import TestCase

from hdmf_zarr.non_finite_attributes import (
    NON_FINITE_ATTRIBUTES_UUID,
    decode,
    is_registered,
    without_registration,
)


class TestDecoding(TestCase):
    """The decoding rules, checked against the convention's test vectors."""

    # (encoded value, decoded value)
    VECTORS = [
        ("NaN", float("nan")),
        ("Infinity", float("inf")),
        ("-Infinity", float("-inf")),
        ("_str_NaN", "NaN"),
        ("_str_Infinity", "Infinity"),
        ("_str_-Infinity", "-Infinity"),
        ("_str__str_NaN", "_str_NaN"),
        ("_str__str__str_NaN", "_str__str_NaN"),
        ("_str_hello", "_str_hello"),
        ("_str_", "_str_"),
        ("nan", "nan"),
        ("inf", "inf"),
        ("+Infinity", "+Infinity"),
        ("NaN ", "NaN "),
        ("NaNNaN", "NaNNaN"),
        ("_STR_NaN", "_STR_NaN"),
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
        for encoded, decoded in self.VECTORS:
            with self.subTest(encoded=encoded):
                self.assertTrue(self._same(decode(encoded), decoded))

    def test_nested_values(self):
        encoded = {"a": [1.0, "Infinity", "_str_NaN"], "b": {"c": "_str__str_NaN", "d": ("-Infinity",)}}
        expected = {"a": [1.0, float("inf"), "NaN"], "b": {"c": "_str_NaN", "d": (float("-inf"),)}}
        self.assertEqual(decode(encoded), expected)

    def test_registration(self):
        registration = {"uuid": NON_FINITE_ATTRIBUTES_UUID, "name": "non-finite-attributes"}
        other = {"uuid": "d89b30cf-ed8c-43d5-9a16-b492f0cd8786", "name": "ref"}
        self.assertTrue(is_registered({"zarr_conventions": [other, registration]}))
        self.assertFalse(is_registered({"zarr_conventions": [other]}))
        self.assertFalse(is_registered({"zarr_conventions": "not a list"}))
        self.assertFalse(is_registered({}))
        self.assertEqual(without_registration([other, registration]), [other])
