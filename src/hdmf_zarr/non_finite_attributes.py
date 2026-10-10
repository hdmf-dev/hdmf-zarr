"""Encoding of attributes that are not finite numbers.

JSON has no representation for NaN or the infinities. ZarrIO follows the Non-Finite Attributes
Zarr convention (https://github.com/catalystneuro/zarr-non-finite-attributes) to store them:

- A number that is not finite is written as the string ``"NaN"``, ``"Infinity"``, or ``"-Infinity"``,
  the forms the Zarr v3 specification defines for fill values.
- A string with the same characters as one of these is written with the prefix ``_str_``, and a
  reader removes one prefix, so every value is read back as it was written.
- Only a Group or Array that registers the convention in its ``zarr_conventions`` attribute is
  decoded.
"""

import math
import re

import numpy as np

CONVENTIONS_ATTR = "zarr_conventions"
"""Name of the attribute in which a Zarr Group or Array registers the conventions it follows."""

NON_FINITE_ATTRIBUTES_UUID = "2adc9aac-d676-4e93-8feb-903b6ae9e08a"
"""UUID that identifies the Non-Finite Attributes convention."""

NON_FINITE_ATTRIBUTES_CONVENTION = {
    "uuid": NON_FINITE_ATTRIBUTES_UUID,
    "schema_url": "https://raw.githubusercontent.com/catalystneuro/zarr-non-finite-attributes/refs/tags/v1/schema.json",
    "spec_url": "https://github.com/catalystneuro/zarr-non-finite-attributes/blob/v1/README.md",
    "name": "non-finite-attributes",
    "description": "Non-finite numbers in attributes are written as strings",
}
"""Convention metadata object that registers the Non-Finite Attributes convention."""

_ESCAPE_PREFIX = "_str_"
# Zero or more escape prefixes followed by exactly one of the strings that denote a number
_AFFECTED = re.compile(r"(?:_str_)*(?:NaN|Infinity|-Infinity)")


def has_non_finite(value) -> bool:
    """Whether a value, or any value nested in it, is a number that is not finite."""
    if isinstance(value, (float, np.floating)):
        return not math.isfinite(value)
    if isinstance(value, np.ndarray):
        return value.dtype.kind == "f" and not bool(np.all(np.isfinite(value)))
    if isinstance(value, (list, tuple, set)):
        return any(has_non_finite(item) for item in value)
    if isinstance(value, dict):
        return any(has_non_finite(item) for item in value.values())
    return False


def encode(value):
    """Return a value as it is written in the attributes of a node that registers the convention."""
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, str):
        return _ESCAPE_PREFIX + value if _AFFECTED.fullmatch(value) else value
    if isinstance(value, np.ndarray) and value.ndim > 0:
        return encode(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return type(value)(encode(item) for item in value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def decode(value):
    """Return the value that an attribute of a node that registers the convention stands for."""
    if isinstance(value, str) and _AFFECTED.fullmatch(value):
        return value[len(_ESCAPE_PREFIX) :] if value.startswith(_ESCAPE_PREFIX) else float(value)
    if isinstance(value, (list, tuple)):
        return type(value)(decode(item) for item in value)
    if isinstance(value, dict):
        return {key: decode(item) for key, item in value.items()}
    return value


def is_registered(attributes) -> bool:
    """Whether the attributes of a Zarr Group or Array register the convention."""
    conventions = attributes.get(CONVENTIONS_ATTR)
    if not isinstance(conventions, (list, tuple)):
        return False
    return any(isinstance(entry, dict) and entry.get("uuid") == NON_FINITE_ATTRIBUTES_UUID for entry in conventions)


def without_registration(conventions):
    """Return the entries of a ``zarr_conventions`` attribute other than the one for this convention."""
    return [
        entry
        for entry in conventions
        if not (isinstance(entry, dict) and entry.get("uuid") == NON_FINITE_ATTRIBUTES_UUID)
    ]
