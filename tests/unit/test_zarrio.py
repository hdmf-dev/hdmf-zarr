"""
Module for testing different Zarr storage backends

This module uses the tests defined in base_tests_zarrio.py and runs them for
the different storage backends supported by ZarrIO. Specifically, the
BaseTestZarrWriter, BaseTestZarrWriteUnit, and BaseTestExportZarrToZarr classes
are used as base classes and the setUp and tearDown methods are customized
to use different backends. I.e, any tests that are being added to those
classes will then be run here with all different backends so that we don't
need to implement the tests separately for the different backends.
"""
from tests.unit.base_tests_zarrio import (BaseTestZarrWriter,
                                          ZarrStoreTestCase,
                                          BaseTestZarrWriteUnit,
                                          BaseTestExportZarrToZarr)
from zarr.storage import (DirectoryStore,
                          TempStore,
                          NestedDirectoryStore)
import zarr
from hdmf_zarr.backend import ZarrIO
import os


CUR_DIR = os.path.dirname(os.path.realpath(__file__))


######################################################
#  Default storage backend using just a string path
######################################################
class TestZarrWriterDefaultStore(BaseTestZarrWriter):
    """
    Test writing of builder with Zarr using the default store.

    All settings are already defined in the BaseTestZarrWriter class so we here only
    need to instantiate the class to run the tests.
    """
    pass


class TestZarrWriteUnitDefaultStore(BaseTestZarrWriteUnit):
    """
    Unit test for individual write functions using the default store.

    All settings are already defined in the BaseTestZarrWriter class so we here only
    need to instantiate the class to run the tests.
    """
    pass


class TestExportZarrToZarrDefaultStore(BaseTestExportZarrToZarr):
    """
    Test exporting Zarr to Zarr using the default store.

    All settings are already defined in the BaseTestZarrWriter class so we here only
    need to instantiate the class to run the tests.
    """
    pass


#########################################
#  DirectoryStore tests
#########################################
class TestZarrWriterDirectoryStore(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.store = DirectoryStore(self.store_path)


class TestZarrWriteUnitDirectoryStore(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a custom DirectoryStore"""
    def setUp(self):
        self.store_path = "test_io.zarr"
        self.store = DirectoryStore(self.store_path)


class TestExportZarrToZarrDirectoryStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.store = [DirectoryStore(p) for p in self.store_path]


#########################################
#  TempStore tests
#########################################
class TestZarrWriterTempStore(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom TempStore"""
    def setUp(self):
        super().setUp()
        self.store = TempStore()
        self.store_path = self.store.path


class TestZarrWriteUnitTempStore(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a custom TempStore"""
    def setUp(self):
        self.store = TempStore()
        self.store_path = self.store.path


class TestExportZarrToZarrTempStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using TempStore."""
    def setUp(self):
        super().setUp()
        self.store = [TempStore() for i in range(len(self.store_path))]
        self.store_path = [s.path for s in self.store]


#########################################
#  NestedDirectoryStore tests
#########################################
class TestZarrWriterNestedDirectoryStore(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom NestedDirectoryStore"""
    def setUp(self):
        super().setUp()
        self.store = NestedDirectoryStore(self.store_path)


class TestZarrWriteUnitNestedDirectoryStore(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a custom NestedDirectoryStore"""
    def setUp(self):
        self.store_path = "test_io.zarr"
        self.store = NestedDirectoryStore(self.store_path)


class TestExportZarrToZarrNestedDirectoryStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using NestedDirectoryStore"""
    def setUp(self):
        super().setUp()
        self.store = [NestedDirectoryStore(p) for p in self.store_path]


#########################################
#  Consolidate Metadata tests
#########################################
class TestConsolidateMetadata(ZarrStoreTestCase):
    """
    Tests for consolidated metadata and corresponding helper methods.
    """
    def test_get_store_path_shallow(self):
        self.create_zarr(consolidate_metadata=False)
        store = DirectoryStore(self.store)
        path = ZarrIO._ZarrIO__get_store_path(store)
        expected_path = os.path.normpath(os.path.join(CUR_DIR, 'test_io.zarr'))
        self.assertEqual(path, expected_path)

    def test_get_store_path_deep(self):
        self.create_zarr()
        zarr_obj = zarr.open_consolidated(self.store, mode='r')
        store = zarr_obj.store
        path = ZarrIO._ZarrIO__get_store_path(store)
        expected_path = os.path.normpath(os.path.join(CUR_DIR, 'test_io.zarr'))
        self.assertEqual(path, expected_path)

    def test_force_open_without_consolidated(self):
        """Test that read-mode -r forces a regular read with mode r"""
        self.create_zarr(consolidate_metadata=True)
        # Confirm that opening the file 'r' mode indeed uses the consolidated metadata
        with ZarrIO(self.store, mode='r') as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.ConsolidatedMetadataStore)
        # Confirm that opening the file IN 'r-' mode indeed forces a regular open without consolidated metadata
        with ZarrIO(self.store, mode='r-') as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.DirectoryStore)

    def test_force_open_without_consolidated_fails(self):
        """
        Test that we indeed can't use '_ZarrIO__open_file_consolidated' function in r- read mode, which
        is used to force read without consolidated metadata.
        """
        self.create_zarr(consolidate_metadata=True)
        with ZarrIO(self.store, mode='r') as read_io:
            # Check that using 'r-' fails
            msg = 'Mode r- not allowed for reading with consolidated metadata'
            with self.assertRaisesWith(ValueError, msg):
                read_io._ZarrIO__open_file_consolidated(store=self.store, mode='r-')
            # Check that using 'r' does not fail
            try:
                read_io._ZarrIO__open_file_consolidated(store=self.store, mode='r')
            except ValueError as e:
                self.fail("ZarrIO.__open_file_consolidated raised an unexpected ValueError: {}".format(e))

