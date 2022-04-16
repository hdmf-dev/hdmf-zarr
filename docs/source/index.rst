.. hdmf-zarr documentation master file, created by
   sphinx-quickstart on Tue Apr 12 03:32:29 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to hdmf-zarr's documentation!
=====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   tutorials/index
   hdmf_zarr

**Citation:** If you use HDMF or hdmf_zarr in your research, please use the following citation:

* A. J. Tritt, O. Ruebel, B. Dichter, R. Ly, D. Kang, E. F. Chang, L. M. Frank, K. Bouchard,
  *"HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards,"*
  2019 IEEE International Conference on Big Data (Big Data),
  Los Angeles, CA, USA, 2019, pp. 165-179, doi: 10.1109/BigData47090.2019.9005648.


Zarr backend
------------

The :py:class:`~hdmf_zarr.backend.ZarrIO` backend is an alternative storage backend to store data using HDMF via the Zarr library.

Supported features:
^^^^^^^^^^^^^^^^^^^

- Write/Read of basic datatypes, strings and compound data types
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
- Links and reference are not natively supported by Zarr. Links and references are implemented in the Zarr backend in hdmf_zarr in an OS independent fashion. The backend reserves attributes to store the paths of the target objects in the two functions.
- Attributes are stored as JSON documents in Zarr (using the DirectoryStore). As such, all attributes must be JSON serializable. The Zarr backend attempts to cast types to JSON serializable types as much as possible.
- Currently the Zarr backend uses Zarr's DirectoryStore only. Other stores could be added but will require proper treatement of links and references for those backends.
- For specific TODO items relate to the Zarr backend see ``src/backend.py``
- Exporting of HDF5 files with external links is not yet fully implemented/tested

TODO
^^^^
-
- Resolve reference stored in datasets to the containers
- Add support for RegionReferences
- HDF5IO uses export_source argument on export. Need to check with if we need it here as well.
- Handling of  external links on export is not yet fully implemented and is missing a few corner cases
- Here we update the PyNWB test harness to add ZarrIO to the rountrip tests, which in turn runs all HDF5 roundtrip tests also for Zarr. This requires changing the test harness in PyNWB, instead it would be useful to be able to "inject" new I/O backends in the test harness so that we can specify those tests here, rather than implementing this in PyNWB and making PyNWB dependent on hdmf-zarr (see https://github.com/NeurodataWithoutBorders/pynwb/pull/1018/files#diff-ebaf216d6ea84b72ee9ac17ab17b6e5d5ed8a5f3bbd09ee11d9ee6969c2fc294 )


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
