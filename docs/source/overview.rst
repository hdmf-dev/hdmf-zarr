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
- Links.
- Object references
- Writing/loading namespaces/specifications
- Iterative data write using :py:class:`~hdmf.data_utils.AbstractDataChunkIterator`

Known Limitations
-----------------

- Support for region references is not yet implemented. See also :ref:`sec-zarr-storage-references-region` for details.
- The Zarr backend is currently experimental and may still change.
- Attributes are stored as JSON documents in Zarr (using the DirectoryStore). As such, all attributes must be JSON serializable. The :py:class:`~hdmf_zarr.backend.ZarrIO` backend attempts to cast types to JSON serializable types as much as possible.
- Currently the :py:class:`~hdmf_zarr.backend.ZarrIO` backend uses Zarr's :py:class:`~zarr.storage.DirectoryStore` only. Other `Zarr stores <https://zarr.readthedocs.io/en/stable/api/storage.html>`_ could be added but will require proper treatment of links and references for those backends as links are not supported in Zarr (see `zarr-python issues #389 <https://github.com/zarr-developers/zarr-python/issues/389>`_.
- Exporting of HDF5 files with external links is not yet fully implemented/tested. (see `hdmf-zarr issue #49 <https://github.com/hdmf-dev/hdmf-zarr/issues/49>`_.
- Object references are currently always resolved on read (as are links) rather than being loaded lazily (see `hdmf-zarr issue #50 <https://github.com/hdmf-dev/hdmf-zarr/issues/50>`_.
