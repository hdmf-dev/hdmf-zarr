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
