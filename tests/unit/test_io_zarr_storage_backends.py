"""
Module for testing different Zarr storage backends
"""
from tests.unit.test_io_zarr import (TestZarrWriter,
                                     TestZarrWriteUnit,
                                     TestExportZarrToZarr)
from zarr.storage import (DirectoryStore,
                          TempStore,
                          NestedDirectoryStore)
from hdmf_zarr.backend import ZarrIO


#########################################
#  DirectoryStore tests
#########################################
class TestZarrWriterDirectoryStore(TestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.path = DirectoryStore(self.source_path)


class TestZarrWriteUnitDirectoryStore(TestZarrWriteUnit):
    """Unit test for individual write functions using a custom DirectoryStore"""
    def setUp(self):
        self.path = "test_io.zarr"
        self.io = ZarrIO(DirectoryStore(self.path), mode='w')
        self.f = self.io._ZarrIO__file
        self.store_cls = None


class TestExportZarrToZarrDirectoryStore(TestExportZarrToZarr):
    """Test exporting Zarr to Zarr using DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.paths = [DirectoryStore(p) for p in self.source_paths]


#########################################
#  TempStore tests
#########################################
class TestZarrWriterTempStore(TestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""
    def setUp(self):
        super().setUp()
        self.path = TempStore()
        self.source_path = self.path.path


class TestZarrWriteUnitTempStore(TestZarrWriteUnit):
    """Unit test for individual write functions using a custom DirectoryStore"""
    def setUp(self):
        store = TempStore()
        self.io = ZarrIO(store, mode='w')
        self.path = store.path
        self.f = self.io._ZarrIO__file
        self.store_cls = None


class TestExportZarrToZarrTempStore(TestExportZarrToZarr):
    """Test exporting Zarr to Zarr using TempStore."""
    def setUp(self):
        super().setUp()
        self.paths = [TempStore() for i in range(len(self.source_paths))]
        self.source_paths = [s.path for s in self.paths]


#########################################
#  NestedDirectoryStore tests
#########################################
class TestZarrWriterNestedDirectoryStore(TestZarrWriter):
    """Test writing of builder with Zarr using a custom NestedDirectoryStore"""
    def setUp(self):
        super().setUp()
        self.path = NestedDirectoryStore(self.source_path)


class TestZarrWriteUnitNestedDirectoryStore(TestZarrWriteUnit):
    """Unit test for individual write functions using a custom NestedDirectoryStore"""
    def setUp(self):
        self.path = "test_io.zarr"
        self.io = ZarrIO(NestedDirectoryStore(self.path), mode='w')
        self.f = self.io._ZarrIO__file
        self.store_cls = None


class TestExportZarrToZarrNestedDirectoryStore(TestExportZarrToZarr):
    """Test exporting Zarr to Zarr using NestedDirectoryStore"""
    def setUp(self):
        super().setUp()
        self.paths = [NestedDirectoryStore(p) for p in self.source_paths]


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
# class TestZarrWriteUnitSQLiteStore(TestZarrWriteUnit):
#     """Unit test for individual write functions using a custom DirectoryStore"""
#     def setUp(self):
#         self.path = "test_io.zarr.sqldb"
#         self.io = ZarrIO(SQLiteStore(self.path), mode='w')
#         self.f = self.io._ZarrIO__file
#         self.store_cls = SQLiteStore
#
#     def tearDown(self):
#         if os.path.exists(self.path):
#             os.remove(self.path)
#
#
# class TestExportZarrToZarrSQLiteStore(TestExportZarrToZarr):
#     """Test exporting Zarr to Zarr using SQLiteStore"""
#     def setUp(self):
#         super().setUp()
#         self.paths = [SQLiteStore(p) for p in self.source_paths]
