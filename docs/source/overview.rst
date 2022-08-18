Overview
========

Zarr Backend and Utilities
--------------------------

**hdmf_zarr** implements a Zarr backend for HDMF. Some of the key classes relevant for end-users are:

* :py:class:`~hdmf_zarr.backend.ZarrIO` implements an alternative storage backend to store data using HDMF via the Zarr library.
* :py:class:`~hdmf_zarr.nwb.NWBZarrIO` uses :py:class:`~hdmf_zarr.backend.ZarrIO` to define a Zarr backend store for integration with PyNWB to simplify the use of `hdmf_zarr` with NWB (similar to :py:class:`~pynwb.NWBHDF5IO` in PyNWB)
* :py:mod:`~hdmf_zarr.utils` implements utility classes for the :py:class:`~hdmf_zarr.backend.ZarrIO` backend. For end-users the :py:class:`~hdmf_zarr.utils.ZarrDataIO` class is relevant for defining advanced I/O options for datasets.

Features and Known Limitations
------------------------------

Supported features
^^^^^^^^^^^^^^^^^^^

- Write/Read of basic data types, strings and compound data types
- Chunking
- Compression and I/O filters
- Links
- Object references
- Writing/loading namespaces/specifications
- Iterative data write using :py:class:`~hdmf.data_utils.AbstractDataChunkIterator`

Limitations
^^^^^^^^^^^

- Support for region references is not yet implemented  (see :py:class:`hdmf_zarr.backend.ZarrIO.__get_ref`)
- The Zarr backend is currently experimental and may still change.
- Links and reference are not natively supported by Zarr. Links and references are implemented in :py:class:`~hdmf_zarr.backend.ZarrIO` in an OS independent fashion. The backend reserves attributes (see :py:attr:`~hdmf_zarr.backend.ZarrIO.__reserve_attribute`) to store the paths of the target objects (see also  :py:meth:`~hdmf_zarr.backend.ZarrIO.__write_link__`, :py:meth:`~hdmf_zarr.backend.ZarrIO.__add_link__`, :py:meth:`~hdmf_zarr.backend.ZarrIO.__read_links`)
- Attributes are stored as JSON documents in Zarr (using the DirectoryStore). As such, all attributes must be JSON serializable. The :py:class:`~hdmf_zarr.backend.ZarrIO` backend attempts to cast types to JSON serializable types as much as possible.
- Currently the :py:class:`~hdmf_zarr.backend.ZarrIO` backend uses Zarr's :py:class:`~zarr.storage.DirectoryStore` only. Other `Zarr stores <https://zarr.readthedocs.io/en/stable/api/storage.html>`_ could be added but will require proper treatment of links and references for those backends as links are not supported in Zarr (see `https://github.com/zarr-developers/zarr-python/issues/389 <https://github.com/zarr-developers/zarr-python/issues/389>`_.
- Exporting of HDF5 files with external links is not yet fully implemented/tested

TODO
^^^^

- Resolve reference stored in datasets to the containers
- Add support for RegionReferences
- :py:class:`~hdmf.backends.hdf5.h5tools.HDF5IO` uses the ``export_source`` argument on export. Need to check with Ryan Ly if we need it here as well.
- Handling of  external links on export is not yet fully implemented and is missing a few corner cases
- Here we update the PyNWB test harness to add ZarrIO to the rountrip tests, which in turn runs all HDF5 roundtrip tests also for Zarr. This requires changing the test harness in PyNWB, instead it would be useful to be able to "inject" new I/O backends in the test harness so that we can specify those tests here, rather than implementing this in PyNWB and making PyNWB dependent on hdmf-zarr. See the files ``tests/integration/ui_write/base.py`` and ``tests/integration/hdf5/test_modular_storage.py`` as part of `PyNWB #1018 <https://github.com/NeurodataWithoutBorders/pynwb/pull/1018/files>`_ for details (the other parts of the this PR have already been ported to *hdmf-zarr*).
