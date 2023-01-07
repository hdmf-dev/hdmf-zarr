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
                                          BaseTestZarrWriteUnit,
                                          BaseTestExportZarrToZarr)
from zarr.storage import (DirectoryStore,
                          TempStore,
                          NestedDirectoryStore)


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
        super().setUp()
        self.store = DirectoryStore(self.store_path)


class TestExportZarrToZarrDirectoryStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.stores = [DirectoryStore(p) for p in self.store_path]


#########################################
#  TempStore tests
#########################################
class TestZarrWriterTempStore(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.store = TempStore()
        self.store_path = self.store.path


class TestZarrWriteUnitTempStore(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a custom DirectoryStore"""
    def setUp(self):
        self.store = TempStore()
        self.store_path = self.store.path


class TestExportZarrToZarrTempStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using TempStore."""
    def setUp(self):
        super().setUp()
        self.stores = [TempStore() for i in range(len(self.store_path))]
        self.store_paths = [s.path for s in self.stores]


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
        super().setUp()
        self.store = NestedDirectoryStore(self.store_path)


class TestExportZarrToZarrNestedDirectoryStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using NestedDirectoryStore"""
    def setUp(self):
        super().setUp()
        self.stores = [NestedDirectoryStore(p) for p in self.store_path]


#########################################
#  SQLiteStore tests
#########################################
# class TestZarrWriterSQLiteStore (TestZarrWriter):
#     """Test writing of builder with Zarr using a custom SQLiteStore """
#     def setUp(self):
#         super().setUp()
#         self.source_path += ".sqldb"
#         self.path = SQLiteStore(self.source_path)
#         self.store_cls = SQLiteStore
#
#     def tearDown(self):
#         if os.path.exists(self.source_path):
#             os.remove(self.source_path)
#
#
# class TestZarrWriteUnitSQLiteStore(BaseTestZarrWriteUnit):
#     """Unit test for individual write functions using a custom DirectoryStore"""
#     def setUp(self):
#         self.path = "test_io.zarr.sqldb"
#         self.io = ZarrIO(SQLiteStore(self.path), mode='w')
#         self.store_cls = SQLiteStore
#
#     def tearDown(self):
#         if os.path.exists(self.path):
#             os.remove(self.path)
#
#
# class TestExportZarrToZarrSQLiteStore(BaseTestExportZarrToZarr):
#     """Test exporting Zarr to Zarr using SQLiteStore"""
#     def setUp(self):
#         super().setUp()
#         self.paths = [SQLiteStore(p) for p in self.source_paths]
