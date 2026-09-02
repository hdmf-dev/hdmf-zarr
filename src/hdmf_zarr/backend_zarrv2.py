"""Read-only backend for NWB / HDMF ZarrV2 files written with hdmf-zarr<0.14 + zarr<3.

Zarr-python v3 cannot fully parse some constructs produced by zarr v2 (object
dtype arrays with ``pickle`` / ``json2`` / ``vlen-utf8`` codecs, fill_values
incompatible with the encoded dtype, etc.). :class:`ZarrV2IO` extends
:class:`ZarrIO` with the fallbacks needed to read those files. Writing is not
supported — files written by this codebase are always zarr v3.
"""

import json
import os
import warnings

import numpy as np
import zarr
from zarr.storage import LocalStore

from hdmf.build import DatasetBuilder
from hdmf.utils import docval, get_docval, popargs

from .backend import ZarrIO, SPEC_LOC_ATTR
from .utils import ZarrSpecReader
from .zarr_utils import BuilderZarrReferenceDataset, BuilderZarrTableDataset

_V2_READ_MODES = ("r", "r-")


class UnsafePickleCodecError(ValueError):
    """Raised when an untrusted v2 file requests unsafe pickle decoding."""


def _v2_codec(codec_config, allow_pickle):
    """Build a declared v2 codec after enforcing the pickle trust policy."""
    if codec_config and codec_config.get("id") == "pickle" and not allow_pickle:
        raise UnsafePickleCodecError(
            "Refusing to decode the unsafe pickle codec in a Zarr v2 file. "
            "Reopen with allow_pickle=True only if this file is trusted."
        )
    import numcodecs

    return numcodecs.get_codec(codec_config)


def _read_store_bytes(store, key):
    """Read raw bytes for *key* from a Zarr store, returning ``None`` if absent.

    Works for both local stores and remote (fsspec) stores.
    """
    if isinstance(store, LocalStore):
        full_path = os.path.join(str(store.root), key)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "rb") as f:
            return f.read()
    from zarr.core.sync import sync as zarr_sync
    from zarr.core.buffer import default_buffer_prototype

    async def _get():
        return await store.get(key, prototype=default_buffer_prototype())

    buf = zarr_sync(_get())
    return buf.to_bytes() if buf is not None else None


def _store_key_exists(store, key):
    """Check whether *key* exists in a Zarr store (local or remote)."""
    if isinstance(store, LocalStore):
        return os.path.exists(os.path.join(str(store.root), key))
    from zarr.core.sync import sync as zarr_sync

    async def _exists():
        return await store.exists(key)

    return zarr_sync(_exists())


def is_zarr_v2_file(path, storage_options=None):
    """Return ``True`` if *path* looks like a zarr v2 hierarchy.

    Checks the zarr format reported by the opened hierarchy (zarr v2 sets
    ``zarr_format=2`` in ``.zgroup``; zarr v3 uses ``zarr.json``).  Works for
    local paths, opened Zarr stores, and protocol URLs (including chained
    fsspec URLs such as ``simplecache::s3://``).
    """
    if isinstance(path, (str, os.PathLike)) and not isinstance(path, LocalStore):
        path_str = str(path)
        is_remote = "://" in path_str
        if not is_remote and storage_options is None:
            return any(os.path.exists(os.path.join(path_str, m)) for m in (".zgroup", ".zarray"))
        # For remote URLs use zarr.open so that it creates the appropriate store
        # internally (FsspecStore via s3fs, https, gcs, …).  FsspecStore.from_url
        # with an empty storage_options dict can behave differently from how zarr
        # itself opens the URL, leading to false-negatives for HTTPS-accessed S3
        # buckets (e.g. https://dandiarchive.s3.amazonaws.com/…).
        try:
            f = zarr.open(path_str, mode="r", storage_options=storage_options or {})
            return f.metadata.zarr_format == 2
        except Exception:
            # zarr v3 may fail to parse the consolidated metadata of a v2 file
            # (e.g. an object-dtype array with an int fill_value), raising before
            # it can report the format. Retry without consolidated metadata so the
            # root .zgroup is read directly — these are exactly the v2 files that
            # ZarrV2IO exists to handle, so a parse failure must not be a v2 miss.
            try:
                f = zarr.open(path_str, mode="r", storage_options=storage_options or {}, use_consolidated=False)
                return f.metadata.zarr_format == 2
            except Exception:
                return False
    else:
        store = path
    try:
        return _store_key_exists(store, ".zgroup") or _store_key_exists(store, ".zarray")
    except Exception:
        return False


class ZarrV2SpecReader(ZarrSpecReader):
    """Spec reader that can fall back to raw-chunk decoding for v2 object arrays."""

    @docval(
        *get_docval(ZarrSpecReader.__init__),
        {
            "name": "allow_pickle",
            "type": bool,
            "doc": "whether to decode unsafe pickle codecs from a trusted v2 file",
            "default": False,
        },
    )
    def __init__(self, **kwargs):
        self.__allow_pickle = popargs("allow_pickle", kwargs)
        super().__init__(**kwargs)

    def _read(self, path):
        try:
            return super()._read(path)
        except (ValueError, TypeError) as e:
            warnings.warn(
                f"Could not read spec dataset '{path}' via zarr API ({e}). "
                f"Falling back to raw chunk read for zarr v2 object-dtype array."
            )
            s = self.__read_v2_object_array(path)
            s = str(s) if not isinstance(s, str) else s
            return json.loads(s)

    def __read_v2_object_array(self, path):
        store = self._group.store
        dataset_key = f"{self._group.path}/{path}" if self._group.path else path

        zarray_bytes = _read_store_bytes(store, f"{dataset_key}/.zarray")
        if zarray_bytes is None:
            raise FileNotFoundError(f"No .zarray found for '{dataset_key}'")
        zarray_meta = json.loads(zarray_bytes)

        raw = _read_store_bytes(store, f"{dataset_key}/0")
        if raw is None:
            raise FileNotFoundError(f"No chunk data found for '{dataset_key}'")

        compressor_config = zarray_meta.get("compressor")
        if compressor_config is not None:
            raw = _v2_codec(compressor_config, self.__allow_pickle).decode(raw)

        filters = zarray_meta.get("filters") or []
        if filters:
            for filt_config in reversed(filters):
                raw = _v2_codec(filt_config, self.__allow_pickle).decode(raw)

        if isinstance(raw, np.ndarray):
            return raw.flat[0]
        if isinstance(raw, (list, tuple)):
            return raw[0]
        return raw


class ZarrV2IO(ZarrIO):
    """Read-only :class:`ZarrIO` extension that handles zarr-v2 NWB files.

    Compared to :class:`ZarrIO` this class:

    * Falls back to ``use_consolidated=False`` if zarr v3 cannot parse the
      consolidated metadata block (e.g. fill_value incompatibilities).
    * Iterates group children via the store and decodes object-dtype arrays
      directly when zarr v3 refuses them.
    * Resolves reference ``source`` paths against the parent directory (old
      hdmf-zarr convention) in addition to the store itself.
    * Uses :class:`ZarrV2SpecReader` for cached namespaces.

    .. note::

        When zarr v3 cannot parse a v2 array (e.g. object-dtype arrays stored
        via ``pickle`` / ``json2`` / ``vlen-utf8`` filters, or fill_values
        incompatible with the encoded dtype), this backend falls back to
        decoding the raw chunks directly (see :meth:`_read_v2_dataset` /
        :meth:`_decode_v2_dataset`). Unlike the normal zarr-backed read path,
        this fallback **eagerly loads the entire dataset into memory** at read
        time rather than reading it lazily on access. For the small,
        object-dtype arrays this path typically handles (specs, references,
        compound/vlen columns) this is not a concern, but it could matter for
        large datasets that zarr v3 fails to parse. Lazy decoding could be added
        in a follow-up if it becomes a performance issue
        (see https://github.com/hdmf-dev/hdmf-zarr/issues/356).
    """

    #: This backend reads Zarr v2 files, so the v2 read-error hint in
    #: :meth:`ZarrIO.read_builder` is suppressed for it.
    _reads_zarr_v2 = True

    @docval(
        *get_docval(ZarrIO.__init__),
        {
            "name": "allow_pickle",
            "type": bool,
            "doc": "whether to decode unsafe pickle codecs from a trusted v2 file",
            "default": False,
        },
    )
    def __init__(self, **kwargs):
        mode, self.__allow_pickle = popargs("mode", "allow_pickle", kwargs)
        if mode not in _V2_READ_MODES:
            raise ValueError(
                f"ZarrV2IO is read-only; mode must be one of {_V2_READ_MODES}, got '{mode}'. "
                "Use ZarrIO/NWBZarrIO to write zarr v3 files."
            )
        kwargs["mode"] = mode
        super().__init__(**kwargs)

    @property
    def allow_pickle(self):
        """Whether unsafe pickle decoding is enabled for this trusted v2 file."""
        return self.__allow_pickle

    @classmethod
    @docval(
        *get_docval(ZarrIO.load_namespaces),
        {
            "name": "allow_pickle",
            "type": bool,
            "doc": "whether to decode unsafe pickle codecs from a trusted v2 file",
            "default": False,
        },
    )
    def load_namespaces(cls, **kwargs):
        """Load cached namespaces while enforcing the v2 pickle trust policy."""
        namespace_catalog, path, file, storage_options, namespaces, allow_pickle = popargs(
            "namespace_catalog", "path", "file", "storage_options", "namespaces", "allow_pickle", kwargs
        )
        if path is not None and file is not None:
            raise ValueError("Only one of 'path' and 'file' must be provided.")
        if path is not None:
            store = cls._resolve_store(path, storage_options)
            f = cls._open_for_namespaces(store)
        else:
            f = file
        return cls._load_namespaces(namespace_catalog, namespaces, f, allow_pickle=allow_pickle)

    # ----- open / namespace hooks -----

    @staticmethod
    def can_read(path):
        try:
            zarr.open(path, mode="r")
            return True
        except Exception:
            try:
                zarr.open(path, mode="r", use_consolidated=False)
                return True
            except Exception:
                return False

    def _open_file(self, store, mode, storage_options=None):
        store = self._resolve_store(store, storage_options)
        try:
            return zarr.open(store=store, mode=mode)
        except Exception:
            # zarr v3 fails to parse some v2 constructs (e.g. an object-dtype array
            # with an int fill_value in the consolidated block). The failing type is
            # not a stable API, so retry the more permissive non-consolidated open.
            return zarr.open(store=store, mode=mode, use_consolidated=False)

    def _open_file_consolidated(self, store, mode, storage_options=None):
        if mode == "r-":
            raise ValueError("Mode r- not allowed for reading with consolidated metadata")

        cache_key = (str(store), mode, str(storage_options))
        if cache_key in self._consolidated_cache:
            return self._consolidated_cache[cache_key]

        open_store = self._resolve_store(store, storage_options)
        try:
            zarr_obj = zarr.open_consolidated(store=open_store, mode=mode)
        except Exception:
            zarr_obj = zarr.open(store=open_store, mode=mode, use_consolidated=False)

        self._consolidated_cache[cache_key] = zarr_obj
        return zarr_obj

    @classmethod
    def _open_for_namespaces(cls, store):
        try:
            return zarr.open(store, mode="r")
        except Exception:
            # See _open_file: zarr v3 can fail to parse a v2 consolidated block with
            # varying exception types, so retry the non-consolidated open.
            return zarr.open(store, mode="r", use_consolidated=False)

    @classmethod
    def _make_spec_reader(cls, ns_group):
        return ZarrV2SpecReader(ns_group)

    @classmethod
    def _load_namespaces(cls, namespace_catalog, namespaces, f, allow_pickle=False):
        if SPEC_LOC_ATTR not in f.attrs:
            warnings.warn("No cached namespaces found in %s" % cls._get_store_path(f.store))
            return {}

        spec_group = f[f.attrs[SPEC_LOC_ATTR]]
        if namespaces is None:
            namespaces = list(spec_group.keys())

        readers = {}
        for ns in namespaces:
            try:
                ns_group = spec_group[ns]
                latest_version = list(ns_group.keys())[-1]
                readers[ns] = ZarrV2SpecReader(ns_group[latest_version], allow_pickle=allow_pickle)
            except UnsafePickleCodecError:
                raise
            except Exception as e:
                warnings.warn(
                    f"Could not read cached namespace '{ns}' from " f"{cls._get_store_path(f.store)}: {e}. Skipping."
                )

        if not readers:
            return {}

        try:
            return namespace_catalog.load_namespaces("namespace", reader=readers)
        except Exception as e:
            warnings.warn(f"Could not load cached namespaces from " f"{cls._get_store_path(f.store)}: {e}. Skipping.")
            return {}

    # ----- reference resolution -----

    def _resolve_ref_source(self, source_file):
        """Resolve v2-style refs which may be relative to either the store or its parent.

        Only called for local files — see :meth:`ZarrIO._resolve_ref_source` for the
        guard that prevents this from being invoked on remote (S3 / fsspec) stores.
        """
        abs_source = os.path.abspath(self.source)
        resolved_from_store = os.path.abspath(os.path.normpath(os.path.join(abs_source, source_file)))
        if os.path.isdir(resolved_from_store):
            return resolved_from_store
        base_dir = os.path.dirname(abs_source)
        resolved_from_parent = os.path.abspath(os.path.normpath(os.path.join(base_dir, source_file)))
        if os.path.isdir(resolved_from_parent):
            return resolved_from_parent
        return abs_source

    # ----- private store helpers -----

    @staticmethod
    def _store_list_dir(store, prefix):
        """List immediate children of *prefix* in a Zarr store, sorted by name."""
        if isinstance(store, LocalStore):
            dir_path = os.path.join(str(store.root), prefix) if prefix else str(store.root)
            try:
                return sorted(os.listdir(dir_path))
            except OSError:
                return []
        from zarr.core.sync import sync as zarr_sync

        async def _list():
            result = []
            async for item in store.list_dir(prefix):
                result.append(item)
            return result

        entries = sorted(zarr_sync(_list()))
        if entries:
            return entries
        # Remote stores backed by plain HTTP cannot list directories, so
        # ``list_dir`` returns nothing even when the group has children. Fall
        # back to the consolidated ``.zmetadata`` (always present for the v2
        # files this backend targets), which records every member's key.
        return ZarrV2IO._list_dir_from_consolidated(store, prefix)

    @staticmethod
    def _list_dir_from_consolidated(store, prefix):
        """List immediate children of *prefix* using the consolidated ``.zmetadata``.

        Returns an empty list if no consolidated metadata is available.
        """
        zmeta_bytes = _read_store_bytes(store, ".zmetadata")
        if zmeta_bytes is None:
            return []
        metadata = json.loads(zmeta_bytes).get("metadata", {})
        prefix = prefix.strip("/")
        children = set()
        for key in metadata:
            if prefix:
                if not key.startswith(prefix + "/"):
                    continue
                rel = key[len(prefix) + 1 :]
            else:
                rel = key
            first_segment = rel.split("/", 1)[0]
            if first_segment and not first_segment.startswith("."):
                children.add(first_segment)
        return sorted(children)

    @staticmethod
    def _decode_v2_chunk(raw, compressor, filters, dtype, chunk_shape, order, is_object):
        """Decode a single raw chunk of zarr v2 data.

        :param raw: The raw bytes read from the store for this chunk.
        :type raw: bytes or bytearray
        :param compressor: The top-level compressor (e.g. Blosc, Zstd) to decompress *raw* first.
            ``None`` if no compressor was configured.
        :type compressor: numcodecs codec or None
        :param filters: Ordered list of filters applied *after* compression (e.g. Delta, vlen-utf8).
            Applied in reverse order during decode.
        :type filters: list of numcodecs codecs
        :param dtype: The element dtype declared in ``.zarray``.
        :type dtype: numpy.dtype
        :param chunk_shape: Expected shape of this chunk after decoding.
        :type chunk_shape: tuple of int
        :param order: Memory layout order from ``.zarray`` (``'C'`` or ``'F'``).
        :type order: str
        :param is_object: ``True`` when ``dtype == '|O'`` — object arrays are decoded via filters
            only (pickle / json2 / vlen-utf8) and not reinterpreted as a raw buffer.
        :type is_object: bool
        :returns: Decoded chunk with shape *chunk_shape*.
        :rtype: numpy.ndarray
        """
        if compressor is not None:
            raw = compressor.decode(raw)

        if is_object:
            # For object dtype, filters (pickle / json2 / vlen-utf8) produce the array.
            for filt in reversed(filters):
                raw = filt.decode(raw)
            arr = raw if isinstance(raw, np.ndarray) else np.asarray(raw, dtype=object)
            return arr.reshape(chunk_shape, order=order)

        if isinstance(raw, (bytes, bytearray)):
            arr = np.frombuffer(raw, dtype=dtype).copy()
        else:
            arr = np.asarray(raw, dtype=dtype).copy()

        for filt in reversed(filters):
            decoded = filt.decode(arr)
            if isinstance(decoded, (bytes, bytearray)):
                arr = np.frombuffer(decoded, dtype=dtype).copy()
            elif isinstance(decoded, np.ndarray):
                arr = decoded
            else:
                arr = np.asarray(decoded, dtype=dtype)

        return arr.reshape(chunk_shape, order=order)

    @staticmethod
    def _decode_v2_dataset(store, dataset_key, zarray_meta, allow_pickle=False):
        """Decode all chunks of a zarr v2 dataset from a store (local or remote).

        :param store: The zarr store (``LocalStore`` or ``FsspecStore``) backing the file.
        :param dataset_key: Path within the store to the dataset directory (e.g. ``"group/array"``).
        :type dataset_key: str
        :param zarray_meta: Parsed contents of the ``.zarray`` metadata file for this dataset.
        :type zarray_meta: dict
        :returns: The full dataset as an in-memory array with the shape declared in
            *zarray_meta*.  Object-dtype arrays are returned as ``dtype=object``.
        :rtype: numpy.ndarray
        """
        shape = tuple(zarray_meta["shape"])
        chunks = tuple(zarray_meta["chunks"])
        dtype = np.dtype(zarray_meta.get("dtype", "f8"))
        order = zarray_meta.get("order", "C")
        dimension_separator = zarray_meta.get("dimension_separator", ".")

        compressor_config = zarray_meta.get("compressor")
        compressor = _v2_codec(compressor_config, allow_pickle) if compressor_config else None

        filters_config = zarray_meta.get("filters") or []
        filters = [_v2_codec(filter_config, allow_pickle) for filter_config in filters_config]

        is_object = dtype == np.dtype("|O")
        result_dtype = object if is_object else dtype
        fill_value = zarray_meta.get("fill_value", None if is_object else 0)
        ndim = len(shape)
        chunk_grid = tuple((s + c - 1) // c for s, c in zip(shape, chunks))

        if any(s == 0 for s in shape):
            return np.empty(shape, dtype=result_dtype)

        total_chunks = 1
        for g in chunk_grid:
            total_chunks *= g

        if total_chunks == 1:
            chunk_name = dimension_separator.join("0" for _ in range(ndim))
            raw = _read_store_bytes(store, f"{dataset_key}/{chunk_name}")
            if raw is not None:
                data = ZarrV2IO._decode_v2_chunk(raw, compressor, filters, dtype, chunks, order, is_object)
                if chunks != shape:
                    data = data[tuple(slice(0, s) for s in shape)]
                return data
            return np.full(shape, fill_value=fill_value, dtype=result_dtype)

        result = np.full(shape, fill_value=fill_value, dtype=result_dtype)
        for idx in np.ndindex(*chunk_grid):
            chunk_name = dimension_separator.join(str(i) for i in idx)
            raw = _read_store_bytes(store, f"{dataset_key}/{chunk_name}")
            if raw is None:
                continue
            chunk_data = ZarrV2IO._decode_v2_chunk(raw, compressor, filters, dtype, chunks, order, is_object)
            slices = tuple(slice(i * c, min((i + 1) * c, s)) for i, c, s in zip(idx, chunks, shape))
            chunk_slices = tuple(slice(0, sl.stop - sl.start) for sl in slices)
            result[slices] = chunk_data[chunk_slices]
        return result

    @staticmethod
    def _v2_array_metadata_supported_by_zarr(zarray_meta):
        """Return whether zarr-python v3 can parse v2 array metadata."""
        from zarr.core.metadata.v2 import ArrayV2Metadata

        try:
            ArrayV2Metadata.from_dict(zarray_meta)
        except (TypeError, ValueError):
            return False
        return True

    # ----- group iteration with v2 chunk fallback -----

    def _iter_children(self, zarr_obj):
        """Yield ``(name, child)`` pairs for the children of *zarr_obj*.

        This overrides :meth:`ZarrIO._iter_children`. The base implementation
        relies on ``zarr_obj.groups()`` / ``zarr_obj.arrays()``, but those calls
        ask zarr-python v3 to open every child, which raises for zarr v2 arrays
        that v3 cannot parse (most commonly object-dtype arrays stored with
        v2-only codecs such as ``pickle``, ``json2``, or ``vlen-utf8``). A single
        unparsable child would otherwise abort iteration over the whole group.

        Instead, this implementation walks the store keys directly and opens each
        child individually so that a failure on one entry does not prevent the
        others from being read:

        * If zarr v3 opens the child successfully, the ``zarr.Group`` /
          ``zarr.Array`` is yielded as usual.
        * If zarr v3 fails but the entry has a ``.zarray`` (i.e. it is an array,
          not a group), fall back to :meth:`_read_v2_dataset`, which decodes the
          raw chunks manually. That method returns a pre-built
          :class:`~hdmf.build.DatasetBuilder` rather than a ``zarr.Array`` because
          the data has already been decoded in-memory and there is no zarr object
          to hand to ``__read_dataset``. ``__read_group`` detects the builder type
          and adds it directly (see :meth:`ZarrIO._iter_children` and
          ``__read_group``). Groups never need this fallback because zarr v3 can
          always open zarr v2 groups.
        * If both paths fail, the entry is skipped with a warning rather than
          raising, so the rest of the file remains readable.

        :param zarr_obj: The zarr group whose children should be iterated.
        :returns: Generator of ``(name, child)`` where *child* is a
            ``zarr.Group``, ``zarr.Array``, or ``DatasetBuilder``.
        """
        store = zarr_obj.store
        group_prefix = zarr_obj.path or ""
        # List the raw keys under this group rather than calling zarr's
        # groups()/arrays(), which would eagerly open (and choke on) v2 arrays.
        entries = self._store_list_dir(store, group_prefix)

        for entry in entries:
            # Skip zarr metadata keys (.zgroup, .zarray, .zattrs, ...).
            if entry.startswith("."):
                continue
            # On a local store, listing also surfaces chunk files and other
            # non-child paths; only directories correspond to child groups/arrays.
            if isinstance(store, LocalStore):
                entry_full = (
                    os.path.join(str(store.root), group_prefix, entry)
                    if group_prefix
                    else os.path.join(str(store.root), entry)
                )
                if not os.path.isdir(entry_full):
                    continue
            zarray_key = f"{group_prefix}/{entry}/.zarray" if group_prefix else f"{entry}/.zarray"
            try:
                # Avoid asking zarr v3 to open metadata it cannot parse. Its group
                # traversal leaves an unhandled async task behind for those failures.
                zarray_bytes = _read_store_bytes(store, zarray_key)
                if zarray_bytes is not None:
                    zarray_meta = json.loads(zarray_bytes)
                    if not self._v2_array_metadata_supported_by_zarr(zarray_meta):
                        raise ValueError("zarr v3 cannot parse this v2 array's metadata")
                # Happy path: let zarr v3 open the child group/array.
                child = zarr_obj[entry]
                yield entry, child
            except Exception as e:
                # zarr v3 could not open the child. If it is an array (has a
                # .zarray), attempt the manual v2 decode fallback.
                if _store_key_exists(store, zarray_key):
                    try:
                        # Returns a DatasetBuilder with the data already decoded.
                        builder = self._read_v2_dataset(store, group_prefix, entry)
                        warnings.warn(
                            f"Read '{entry}' in '{zarr_obj.name}' via zarr v2 store " f"fallback (zarr v3 error: {e})"
                        )
                        yield entry, builder
                    except UnsafePickleCodecError:
                        raise
                    except Exception as e2:
                        # Neither zarr v3 nor the manual fallback could read it;
                        # skip so the rest of the group still loads.
                        warnings.warn(
                            f"Skipping '{entry}' in '{zarr_obj.name}': "
                            f"zarr v3 could not parse it ({e}) and v2 store fallback "
                            f"also failed ({e2})"
                        )
                else:
                    # No .zarray: nothing to fall back to, so skip this entry.
                    warnings.warn(
                        f"Skipping '{entry}' in '{zarr_obj.name}': zarr v3 could not "
                        f"parse its metadata (likely a zarr v2 object-dtype array): {e}"
                    )

    def _read_v2_dataset(self, store, group_path, name):
        """Read a zarr v2 dataset by decoding raw chunks, returning a DatasetBuilder.

        Zarr-python v3 raises when trying to open certain zarr v2 arrays — most
        commonly those with an object dtype stored via ``pickle``, ``json2``, or
        ``vlen-utf8`` filters, or with a fill-value incompatible with the encoded
        dtype.  When ``zarr_obj[entry]`` fails in :meth:`_iter_children` for such
        an entry, this method is called as a fallback: it reads the raw ``.zarray``
        and ``.zattrs`` metadata directly from the store and decodes every chunk
        manually via :meth:`_decode_v2_dataset`.

        The result is a :class:`~hdmf.build.DatasetBuilder` rather than a
        ``zarr.Array`` because the data has already been decoded in-memory; there
        is no zarr object to pass to ``__read_dataset``.  Groups are never handled
        here because zarr-python v3 can always open zarr v2 groups (``.zgroup`` is
        still understood by zarr v3).

        :param store: The zarr store backing the file (local or remote).
        :param group_path: Path within the store of the parent group (empty string for root).
        :type group_path: str
        :param name: Name of the dataset within *group_path*.
        :type name: str
        :returns: A fully populated builder whose ``data`` field holds the decoded
            in-memory array.
        :rtype: DatasetBuilder
        """
        dataset_key = f"{group_path}/{name}" if group_path else name

        zarray_bytes = _read_store_bytes(store, f"{dataset_key}/.zarray")
        if zarray_bytes is None:
            raise FileNotFoundError(f"No .zarray found for '{dataset_key}'")
        zarray_meta = json.loads(zarray_bytes)

        zattrs_bytes = _read_store_bytes(store, f"{dataset_key}/.zattrs")
        all_attrs = json.loads(zattrs_bytes) if zattrs_bytes is not None else {}

        zarr_dtype = all_attrs.get("zarr_dtype")
        if zarr_dtype is None:
            zarr_dtype = zarray_meta.get("dtype", "")
            warnings.warn(f"Inferred dtype from zarr v2 .zarray for '{name}': {zarr_dtype}")

        reserved = ("zarr_dtype", "zarr_link", SPEC_LOC_ATTR)
        attrs = {k: v for k, v in all_attrs.items() if k not in reserved}

        shape = tuple(zarray_meta["shape"])
        chunks = tuple(zarray_meta["chunks"])
        source = self._get_store_path(store)

        data = self._decode_v2_dataset(store, dataset_key, zarray_meta, allow_pickle=self.allow_pickle)

        if zarr_dtype == "scalar":
            if isinstance(data, np.ndarray) and data.size > 0:
                data = data.flat[0]
            elif isinstance(data, (list, tuple)) and len(data) > 0:
                data = data[0]

        if isinstance(zarr_dtype, str) and self._is_ref(zarr_dtype):
            data = BuilderZarrReferenceDataset(data, self)
        elif isinstance(zarr_dtype, list):
            if any(dts.get("dtype") == "object" for dts in zarr_dtype):
                data = BuilderZarrTableDataset(data, self, [d["dtype"] for d in zarr_dtype])
        elif isinstance(data, np.ndarray) and data.dtype.kind in ("U", "S"):
            data = list(data)
        elif isinstance(data, np.ndarray) and data.dtype == object and data.size > 0 and isinstance(data.flat[0], str):
            data = list(data)

        builder = DatasetBuilder(
            name,
            attributes=attrs,
            dtype=zarr_dtype,
            maxshape=shape,
            chunks=(shape != chunks),
            source=source,
            data=data,
        )
        if group_path:
            builder.location = group_path if group_path.startswith("/") else "/" + group_path.replace("\\", "/")
        else:
            builder.location = "/"
        self._written_builders.set_written(builder)
        return builder

    # ----- write/export are unsupported -----

    def write(self, **kwargs):
        raise NotImplementedError("ZarrV2IO is read-only — use ZarrIO/NWBZarrIO to write zarr v3 files.")

    def export(self, **kwargs):
        raise NotImplementedError("ZarrV2IO is read-only — use ZarrIO/NWBZarrIO to export.")
