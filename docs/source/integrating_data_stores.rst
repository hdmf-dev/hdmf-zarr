.. _sec-integrating-zarr-data-stores:

================================
Integrating New Zarr Data Stores
================================

:py:class:`~hdmf_zarr.backend.ZarrIO` by default uses the Zarr
:zarr-docs:`DirectoryStore <api/storage.html#zarr.storage.DirectoryStore>` via
the :py:meth:`zarr.convenience.open` method. :py:class:`~hdmf_zarr.backend.ZarrIO` further
supports all stores listed in :py:class:`~hdmf_zarr.backend.SUPPORTED_ZARR_STORES`.
Users can specify a particular store using the ``path`` parameter when creating a new
:py:class:`~hdmf_zarr.backend.ZarrIO` instance. This document discusses key steps towards
integrating other data stores available for Zarr with :py:class:`~hdmf_zarr.backend.ZarrIO`.


Updating ZarrIO
===============

1. Import and add the new storage class to the :py:class:`~hdmf_zarr.backend.SUPPORTED_ZARR_STORES`.
   This will in turn allow instances of your new storage class to be passed as a ``path`` parameter
   to :py:meth:`~hdmf_zarr.backend.ZarrIO.__init__`
   and :py:meth:`~hdmf_zarr.backend.ZarrIO.load_namespaces` and pass
   :py:meth:`~hdmf.utils.docval` validation for these functions.

   * If your store has a ``.path`` property then the :py:attr:`~hdmf.backends.io.HDMFIO.source` property
     will be set accordingly in ``__init__`` in :py:class:`~hdmf_zarr.backend.ZarrIO`, otherwise
     ``__init__`` may need to be updated to set a correct ``source`` (used, e.g., to define links).

2. Update :py:meth:`~hdmf_zarr.backend.ZarrIO.open` and :py:meth:`~hdmf_zarr.backend.ZarrIO.close`
   as necessary.

3. Depending on the type of data store, it may also be necessary to update the handling of links
   and references in :py:class:`~hdmf_zarr.backend.ZarrIO`. In principle, reading and writing of
   links should not need to change, however, in particular the
   :py:meth:`~hdmf_zarr.backend.ZarrIO.__resolve_ref` and
   :py:meth:`~hdmf_zarr.backend.ZarrIO.get_builder_exists_on_disk`
   method may need to be updated to ensure
   references are opened correctly on read for files stored with your new store. The
   :py:meth:`~hdmf_zarr.backend.ZarrIO._create_ref` function may also need to be updated, in
   particular in case the links to your store also modify the storage schema for links
   (e.g., if you need to store additional metadata in order to resolve links to your store).

Updating NWBZarrIO
==================

In most cases we should not need to update :py:class:`~hdmf_zarr.nwb.NWBZarrIO` as it inherits
directly from :py:class:`~hdmf_zarr.backend.ZarrIO`. However, in particular if the interface for
``__init__`` has changed for :py:class:`~hdmf_zarr.backend.ZarrIO`,
then we may also need to modify :py:class:`~hdmf_zarr.nwb.NWBZarrIO` accordingly.

Updating Unit Tests
===================

Much of the core test harness of ``hdmf_zarr`` is modularized to simplify running existing
tests with new storage backends. In this way, we can quickly create a collection of common tests
for new backends, and new test cases added to the test suite can be run with all backends.
The relevant test class are located in the `/tests/unit <https://github.com/hdmf-dev/hdmf-zarr/tree/dev/tests/unit>`_
directory of the hdmf_zarr repository.

test_zarrio.py
--------------
`base_tests_zarrio.py <https://github.com/hdmf-dev/hdmf-zarr/blob/dev/tests/unit/base_tests_zarrio.py>`_
provides a collection of base classes that define common
test cases to test basic functionality of :py:class:`~hdmf_zarr.backend.ZarrIO`. Using these base classes, the
`test_zarrio.py <https://github.com/hdmf-dev/hdmf-zarr/blob/dev/tests/unit/test_zarrio.py>`_ module
then implements concrete tests for various backends. To create tests for a new data store, we need to
add the following main classes (while ``<MyStore>`` in the code below would need to be replaced with the
class name of the new data store):

1. **Create tests for new data store:** Add the following main classes (while ``<MyStore>`` in the code below would need to be replaces with the class name of the new data store):

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

.. note:

    In the case of ``BaseTestZarrWriter`` and ``BaseTestZarrWriteUnit`` the ``self.store`` variable defines
    the data store to use with :py:class:`~hdmf_zarr.backend.ZarrIO` while running tests.
    ``self.store_path`` is used during ``tearDown`` to clean up files as well as in some cases
    to setup links in test ``Builders`` or if a test case requires opening a file with Zarr directly.

    ``BaseTestExportZarrToZarr`` tests exporting between Zarr data stores but requires 4 stores and
    paths to be specified via the ``self.store`` and ``self.store_path`` variable. To test export
    between your new backend, you can simply set up all 4 instances to the new store while using different
    storage paths for the different instances (which are saved in  ``self.store_paths``).

2. **Update ``base_tests_zarrio.reopen_store``** If our new data store cannot be reused after
   it has been closed via :py:meth:`~hdmf_zarr.backend.ZarrIO.close`, then update the method
   to either reopen or create a new equivalent data store that can be used for read.
   The function is used in tests that write data, then close the ZarrIO, and
   create a new ZarrIO to read and validate the data.

3. **Run and update tests** Depending on your data store, some test cases in  ``BaseTestZarrWriter``, ``BaseTestZarrWriteUnit``
   or ``BaseTestExportZarrToZarr`` may need to be updated to correctly work with our data store.
   Simply run the test suite to see if any cases are failing to see whether the ``setUp`` in your
   test classes or any specific test cases may need to be updated.

test_io_convert.py
------------------
`test_io_convert.py <https://github.com/hdmf-dev/hdmf-zarr/blob/dev/tests/unit/test_io_convert.py>`_
uses a collection of mixin classes to define custom test classes to test export from one IO backend
to another. As such, the test cases here typically first write to one target and then export to
another target and then compare that the data between the two files is consistent.

1. **Update ``MixinTestHDF5ToZarr``, ``MixinTestZarrToZarr``, and ``MixinTestZarrToZarr``**
   mixin classes to add the new backend to the ``WRITE_PATHS`` (if Zarr is the initial write
   target) and/or ``EXPORT_PATHS`` (if Zarr is the export target) variables to define our
   store as a write or export store for :py:class:`~hdmf_zarr.backend.ZarrIO`, respectively.
   Once we have added our new store as write/export targets to these mixins, all test cases
   defined in the module will be run with our new backend. Specifically, we here commonly
   need to add an instance of our new data store to:

    * ``MixinTestHDF5ToZarr.EXPORT_PATHS``
    * ``MixinTestZarrToHDF5.WRITE_PATHS``
    * ``MixinTestZarrToZarr.WRITE_PATHS`` and ``MixinTestZarrToZarr.EXPORT_PATHS``

2. **Update tests and ZarrIO as necessary** Run the test suite and fix any identified issues.

