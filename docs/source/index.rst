.. hdmf-zarr documentation master file, created by
   sphinx-quickstart on Tue Apr 12 03:32:29 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to hdmf-zarr's documentation!
=====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorials/index
   hdmf_zarr


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



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
