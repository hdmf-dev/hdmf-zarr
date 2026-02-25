.. _sec-overview:

Overview
========

Zarr Backend and Utilities
--------------------------

**hdmf_zarr** implements a Zarr backend for HDMF. Some of the key classes relevant for end-users are:

* :py:class:`~hdmf_zarr.backend.ZarrIO` implements an alternative storage backend to store data using HDMF via the Zarr library.
* :py:class:`~hdmf_zarr.nwb.NWBZarrIO` uses :py:class:`~hdmf_zarr.backend.ZarrIO` to define a Zarr backend store for integration with PyNWB to simplify the use of `hdmf_zarr` with NWB (similar to :py:class:`~pynwb.NWBHDF5IO` in PyNWB)
* :py:mod:`~hdmf_zarr.utils` implements utility classes for the :py:class:`~hdmf_zarr.backend.ZarrIO` backend. For end-users the :py:class:`~hdmf_zarr.utils.ZarrDataIO` class is relevant for defining advanced I/O options for datasets.

Supported features
------------------

- Write/Read of basic data types, strings and compound data types
- Chunking
- Compression and I/O filters
- Links
- Object references
- Writing/loading namespaces/specifications
- Iterative data write using :py:class:`~hdmf.data_utils.AbstractDataChunkIterator` 
- Parallel write with :py:class:`~hdmf.data_utils.GenericDataChunkIterator` (since v0.4)
- Lazy load of datasets
- Lazy load of datasets containing object references (since v0.4)

Known Limitations
-----------------

- The Zarr backend is currently experimental and may still change.
- **Zarr v3 only:** This version of hdmf-zarr writes zarr v3 format only and cannot read files written in zarr v2 format. To read zarr v2 files, use hdmf-zarr 0.x with zarr-python v2. The `zarr CLI migration tool <https://zarr.readthedocs.io/en/stable/user-guide/cli/>`_ may also be used to convert v2 files to v3 format.
- Attributes are stored as JSON documents in Zarr (using the :py:class:`~zarr.storage.LocalStore`). As such, all attributes must be JSON serializable. The :py:class:`~hdmf_zarr.backend.ZarrIO` backend attempts to cast types to JSON serializable types as much as possible.
- Currently the :py:class:`~hdmf_zarr.backend.ZarrIO` backend supports Zarr's :py:class:`~zarr.storage.LocalStore` for local storage and :py:class:`~zarr.storage.FsspecStore` for remote read-only access. Other `Zarr stores <https://zarr.readthedocs.io/en/stable/api/zarr/storage.html>`_ could be added but will require proper treatment of links and references for those backends as links are not supported in Zarr (see `zarr-python issues #389 <https://github.com/zarr-developers/zarr-python/issues/389>`_).
- **Compound dtypes with strings:** String and reference fields in compound data types are stored as fixed-length Unicode strings (``FixedLengthUTF32``) in zarr v3. The ``FixedLengthUTF32`` data type is currently not part of the Zarr V3 specification and may not be supported by other zarr implementations.
- Exporting of HDF5 files with external links is not yet fully implemented/tested (see `hdmf-zarr issue #49 <https://github.com/hdmf-dev/hdmf-zarr/issues/49>`_).
- Special characters (e.g., ``:``, ``<``, ``>``, ``"``, ``/``, ``\``, ``|``, ``?``, or ``*``) may not be supported by all file systems (e.g., on Windows) and as such should not be used as part of the names of Datasets or Groups as Zarr needs to create folders on the filesystem for these objects.
