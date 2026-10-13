"""Encoding of attributes that are bytes.

JSON has no representation for bytes. ZarrIO writes a byte string attribute that is valid UTF-8 as
text, as before. One that is not, such as text in another encoding, is stored following the Bytes
Attributes Zarr convention (https://github.com/catalystneuro/zarr-bytes-attributes):

- Bytes are written as the string ``"base64:"`` followed by the bytes in standard base64 with
  padding.
- A string that begins with ``base64:``, after any ``_str_`` prefixes, is written with the prefix
  ``_str_``, and a reader removes one prefix, so every value is read back as it was written.
- Only a Group or Array that registers the convention in its ``zarr_conventions`` attribute is
  decoded.

It is a companion to the Non-Finite Attributes convention (``hdmf_zarr.non_finite_attributes``),
uses the same escape, and can be applied before or after it.
"""

import base64
import binascii
import re

import numpy as np

from .non_finite_attributes import CONVENTIONS_ATTR

BYTES_ATTRIBUTES_UUID = "2de6770a-9c00-4432-9e84-dd9e1dfed441"
"""UUID that identifies the Bytes Attributes convention."""

BYTES_ATTRIBUTES_CONVENTION = {
    "uuid": BYTES_ATTRIBUTES_UUID,
    "schema_url": "https://raw.githubusercontent.com/catalystneuro/zarr-bytes-attributes/refs/tags/v1/schema.json",
    "spec_url": "https://github.com/catalystneuro/zarr-bytes-attributes/blob/v1/README.md",
    "name": "bytes-attributes",
    "description": "Bytes in attributes are written as base64 strings",
}
"""Convention metadata object that registers the Bytes Attributes convention."""

_ESCAPE_PREFIX = "_str_"
_TAG = "base64:"
# Zero or more escape prefixes followed by the tag and anything else
_AFFECTED = re.compile(r"(?:_str_)*base64:.*", re.DOTALL)


def text_or_bytes(value):
    """Return a value with each byte string that is valid UTF-8 decoded to text, and the others as bytes.

    Numpy arrays are returned as lists.
    """
    if isinstance(value, (bytes, np.bytes_)):
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return bytes(value)
    if isinstance(value, np.ndarray):
        return text_or_bytes(value.tolist()) if value.ndim > 0 else text_or_bytes(value.item())
    if isinstance(value, (list, tuple, set)):
        return type(value)(text_or_bytes(item) for item in value)
    if isinstance(value, dict):
        return {key: text_or_bytes(item) for key, item in value.items()}
    return value


def has_bytes(value) -> bool:
    """Whether a value, or any value nested in it, is a byte string that is not valid UTF-8."""
    if isinstance(value, (bytes, np.bytes_)):
        try:
            bytes(value).decode("utf-8")
            return False
        except UnicodeDecodeError:
            return True
    if isinstance(value, np.ndarray):
        return value.dtype.kind in "SO" and has_bytes(value.tolist() if value.ndim > 0 else value.item())
    if isinstance(value, (list, tuple, set)):
        return any(has_bytes(item) for item in value)
    if isinstance(value, dict):
        return any(has_bytes(item) for item in value.values())
    return False


def encode(value):
    """Return a value as it is written in the attributes of a node that registers the convention."""
    if isinstance(value, (bytes, bytearray, np.bytes_)):
        return _TAG + base64.b64encode(bytes(value)).decode("ascii")
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
        if value.startswith(_ESCAPE_PREFIX):
            return value[len(_ESCAPE_PREFIX) :]
        payload = value[len(_TAG) :]
        try:
            data = base64.b64decode(payload, validate=True)
        except binascii.Error as error:
            raise ValueError(f"Attribute value {value!r} is not a valid base64 payload") from error
        if base64.b64encode(data).decode("ascii") != payload:
            raise ValueError(f"Attribute value {value!r} is not a canonical base64 payload")
        return data
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
    return any(isinstance(entry, dict) and entry.get("uuid") == BYTES_ATTRIBUTES_UUID for entry in conventions)


def without_registration(conventions):
    """Return the entries of a ``zarr_conventions`` attribute other than the one for this convention."""
    return [
        entry
        for entry in conventions
        if not (isinstance(entry, dict) and entry.get("uuid") == BYTES_ATTRIBUTES_UUID)
    ]
