.. _sec-integrating-zarr-data-stores:

================================
Integrating New Zarr Data Stores
================================

:py:class:`~hdmf_zarr.backend.ZarrIO` by default uses the Zarr
:zarr-docs:`DirectoryStory <api/storage.html#zarr.storage.DirectoryStore>` via
the :py:meth:`zarr.convenience.open`. :py:class:`~hdmf_zarr.backend.ZarrIO` further
supports all stores listed :py:class:`~hdmf_zarr.backend.SUPPORTED_ZARR_STORES`,
which users can specify via the ``path`` parameter when creating a new
:py:class:`~hdmf_zarr.backend.ZarrIO` instance. This document discusses key steps towards
integrating other data stores available for Zarr with :py:class:`~hdmf_zarr.backend.ZarrIO`.


Updating ZarrIO
===============

1. Import and add the new storage class to :py:class:`~hdmf_zarr.backend.SUPPORTED_ZARR_STORES`.
   This will in turn allow instances of your new storage class to pass as ``path`` parameters during
   :py:meth:`~hdmf.utils.docval` validation for py:meth:`~hdmf_zarr.backend.ZarrIO.__init__`
   and py:meth:`~hdmf_zarr.backend.ZarrIO.load_namespaces`

   * If your store has a ``.path`` property then the :py:attr:`~hdmf.backends.io.HDMFIO.source` property
     will be set accordingly in ``__init__`` in :py:class:`~hdmf_zarr.backend.ZarrIO`, otherwise
     ``__init__`` may need to be updated to set a correct ``source`` (used, e.g., to define links).

2. Depending on the type of data store, it may also be necessary to update the handling of links
   and references in :py:class:`~hdmf_zarr.backend.ZarrIO`. In principle, reading and writing of
   links should not need to change, however, in particular the
   :py:meth:`~hdmf_zarr.backend.ZarrIO.__resolve_ref` method may need to be updated to ensure
   references are opened correctly on read for files stored with your new store. The
   :py:meth:`~hdmf_zarr.backend.ZarrIO.__get_ref` function may also need to be updated, in
   particular in case the links to your store also modify the storage schema for links
   (e.g., if you need to store additional metadata in order to resolve links to your store).

Updating NWBZarrIO
==================

In post cases we should not need to update :py:class:`~hdmf_zarr.nwb.NWBZarrIO` as it inherits
directly from :py:class:`~hdmf_zarr.backend.ZarrIO`. However, in particular if the interface for
``__init__`` has changed for :py:class:`~hdmf_zarr.backend.ZarrIO`,
then we may also need to modify :py:class:`~hdmf_zarr.nwb.NWBZarrIO` accordingly.

Updating Unit Tests
===================

Many of the core test harness of ``hdmf_zarr`` is modularized to simplify running existing
tests with new storage backends. In this way, we can quickly create a collection of common tests
for new backends, and new test cases added to the test suite can be run with all backends.

test_zarrio.py
--------------
``base_tests_zarrio.py`` provides a collection of bases classes that define common
test cases to test basic functionality of :py:class:`~hdmf_zarr.backend.ZarrIO`. Using these base classes
`test_zarrio.py <https://github.com/hdmf-dev/hdmf-zarr/blob/dev/tests/unit/test_io_zarr.py>`_
then implements concrete tests for various backends. To create tests for a new data store we need to
add the following main classes:

.. code-block:: python

    #########################################
    #  <MyStore> tests
    #########################################
    class TestZarrWriter<MyStore>(BaseTestZarrWriter):
        """Test writing of builder with Zarr using a custom <MyStore>"""
        def setUp(self):
            super().setUp()
            self.store = <MyStore>()
            self.store_path = self.store.path


    class TestZarrWriteUnit<MyStore>(BaseTestZarrWriteUnit):
        """Unit test for individual write functions using a custom <MyStore>"""
        def setUp(self):
            super().setUp()
            self.store = <MyStore>()
            self.store_path = self.store.path


    class TestExportZarrToZarr<MyStore>(BaseTestExportZarrToZarr):
        """Test exporting Zarr to Zarr using <MyStore>."""
        def setUp(self):
            super().setUp()
            self.stores = [<MyStore>() for i in range(len(self.store_path))]
            self.store_paths = [s.path for s in self.stores]


In the case of ``BaseTestZarrWriter`` and ``BaseTestZarrWriteUnit`` the ``self.store`` defines the
data store to use with :py:class:`~hdmf_zarr.backend.ZarrIO`` while running tests and
``self.store_path`` is uses during ``tearDown`` to clean up files as well as in some cases
to setup links in test ``Builders`` or if a test case requires opening a file with zarr directly.

``BaseTestExportZarrToZarr`` tests exporting between Zarr data stores but requires 4 stores and
paths to be specified via the ``self.stores`` and ``self.store_paths`` variable. To test export
between your new backend, you can simply set up all 4 instances the same way with different
storage paths.

Depending on your data store, some test cases in  ``BaseTestZarrWriter``, ``BaseTestZarrWriteUnit``
or ``BaseTestExportZarrToZarr`` may need to be updated to correctly work with our data store.
Simply run the test suite to see if any cases are failing to see whether the ``setUp`` in your
test classes or any specific test cases may need to updated.


test_io_convert.py
------------------
`test_io_convert.py <https://github.com/hdmf-dev/hdmf-zarr/blob/dev/tests/unit/test_io_convert.py>`_
uses a collection of mixin classes to define custom test classes to test export from one IO backend
to another. As such, the test cases here typically first write to one target and then export to another
target and then compare that the data between the two files is consistent.

To run the tests defined here with your new storage backend we typically mainly need to update the
``MixinTestHDF5ToZarr``, ``MixinTestZarrToZarr``, and ``MixinTestZarrToZarr`` mixin classes to
add our new backend to the ``WRITE_PATHS`` (if Zarr is the initial write target) and/or ``EXPORT_PATHS``
(if Zarr is the export target) variables to define our store as a write or export store for
:py:class:`~hdmf_zarr.backend.ZarrIO`, respectively. Specifially, we here commonly need to add an instance
of our new data store to:

* ``MixinTestHDF5ToZarr.EXPORT_PATHS``
* ``MixinTestZarrToHDF5.WRITE_PATHS``
* ``MixinTestZarrToZarr.WRITE_PATHS`` and ``MixinTestZarrToZarr.EXPORT_PATHS``

Once we have added our new store as write/export targets to these mixins, all test cases
defined in the module should be run with our new backend.
