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

from tests.unit.base_tests_zarrio import (
    BaseTestZarrWriter,
    ZarrStoreTestCase,
    BaseTestZarrWriteUnit,
    BaseTestExportZarrToZarr,
)
from zarr.storage import DirectoryStore, NestedDirectoryStore
from tests.unit.utils import Baz, BazData, BazBucket, get_baz_buildmanager

import zarr
from hdmf_zarr.backend import ZarrIO
from .utils import BuildDatasetShapeMixin, BarData, BarDataHolder
from hdmf.spec import DatasetSpec
import os
import shutil
import warnings
import pathlib


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
#  Pathlib Tests
#########################################
class TestPathlib(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""

    def setUp(self):
        super().setUp()
        self.store = pathlib.Path(self.store_path)


#########################################
#  Consolidate Metadata tests
#########################################
class TestConsolidateMetadata(ZarrStoreTestCase):
    """
    Tests for consolidated metadata and corresponding helper methods.
    """

    def test_get_store_path_shallow(self):
        self.create_zarr(consolidate_metadata=False)
        store = DirectoryStore(self.store_path)
        path = ZarrIO._ZarrIO__get_store_path(store)
        expected_path = os.path.abspath("test_io.zarr")
        self.assertEqual(path, expected_path)

    def test_get_store_path_deep(self):
        self.create_zarr()
        zarr_obj = zarr.open_consolidated(self.store_path, mode="r")
        store = zarr_obj.store
        path = ZarrIO._ZarrIO__get_store_path(store)
        expected_path = os.path.abspath("test_io.zarr")
        self.assertEqual(path, expected_path)

    def test_force_open_without_consolidated(self):
        """Test that read-mode -r forces a regular read with mode r"""
        self.create_zarr(consolidate_metadata=True)
        # Confirm that opening the file 'r' mode indeed uses the consolidated metadata
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.ConsolidatedMetadataStore)
        # Confirm that opening the file IN 'r-' mode indeed forces a regular open without consolidated metadata
        with ZarrIO(self.store_path, mode="r-") as read_io:
            read_io.open()
            self.assertIsInstance(read_io.file.store, zarr.storage.DirectoryStore)

    def test_force_open_without_consolidated_fails(self):
        """
        Test that we indeed can't use '_ZarrIO__open_file_consolidated' function in r- read mode, which
        is used to force read without consolidated metadata.
        """
        self.create_zarr(consolidate_metadata=True)
        with ZarrIO(self.store_path, mode="r") as read_io:
            # Check that using 'r-' fails
            msg = "Mode r- not allowed for reading with consolidated metadata"
            with self.assertRaisesWith(ValueError, msg):
                read_io._ZarrIO__open_file_consolidated(store=self.store_path, mode="r-")
            # Check that using 'r' does not fail
            try:
                read_io._ZarrIO__open_file_consolidated(store=self.store_path, mode="r")
            except ValueError as e:
                self.fail("ZarrIO.__open_file_consolidated raised an unexpected ValueError: {}".format(e))


class TestOverwriteExistingFile(ZarrStoreTestCase):
    def test_force_overwrite_when_file_exists(self):
        """
        Test that we can overwrite a file when opening with `w` mode even if there is
        an existing file. Zarr can write into a directory but not a file.
        """
        # create a dummy text file
        with open(self.store_path, "w") as file:
            file.write("Just a test file used in  TestOverwriteExistingFile")
        # try to create a Zarr file at the same location (i.e., self.store) as the
        # test text file to force overwriting the existing file.
        self.create_zarr(force_overwrite=True, mode="w")

    def test_force_overwrite_when_dir_exists(self):
        """
        Test that we can overwrite a directory when opening with `w` mode even if there is
        an existing directory.
        """
        # create a Zarr file
        self.create_zarr()
        # try to overwrite the existing Zarr file
        self.create_zarr(force_overwrite=True, mode="w")


class TestDimensionLabels(BuildDatasetShapeMixin):
    """
    This is to test setting the dimension_labels as a zarr attribute '_ARRAY_DIMENSIONS'.

    Workflow:
    i) We need to define a `get_dataset_inc_spec` to set the dim in the spec (via BuildDatasetShapeMixin)
    ii) Create and write a BarDataHolder with a BarData.
    iii) Read and check that the _ARRAY_DIMENSIONS attribute is set.
    """

    def tearDown(self):
        shutil.rmtree(self.store)

    def get_base_shape_dims(self):
        return [None, None], ["a", "b"]

    def get_dataset_inc_spec(self):
        dataset_inc_spec = DatasetSpec(
            doc="A BarData",
            data_type_inc="BarData",
            quantity="*",
        )
        return dataset_inc_spec

    def test_build(self):
        bar_data_inst = BarData(name="my_bar", data=[[1, 2, 3], [4, 5, 6]], attr1="a string")
        bar_data_holder_inst = BarDataHolder(
            name="my_bar_holder",
            bar_datas=[bar_data_inst],
        )

        with ZarrIO(self.store, manager=self.manager, mode="w") as io:
            io.write(bar_data_holder_inst)

        with ZarrIO(self.store, manager=self.manager, mode="r") as io:
            file = io.read()
            self.assertEqual(file.bar_datas[0].data.attrs["_ARRAY_DIMENSIONS"], ["a", "b"])


class TestDatasetofReferences(ZarrStoreTestCase):
    def setUp(self):
        self.store_path = "test_io.zarr"
        self.store = DirectoryStore(self.store_path)

    def tearDown(self):
        """
        Remove all files and folders defined by self.store_path
        """
        paths = self.store_path if isinstance(self.store_path, list) else [self.store_path]
        for path in paths:
            if os.path.exists(path):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
                else:
                    warnings.warn("Could not remove: %s" % path)

    def test_append_references(self):
        # Setup a file container with references
        num_bazs = 10
        bazs = []  # set up dataset of references
        for i in range(num_bazs):
            bazs.append(Baz(name="baz%d" % i))
        baz_data = BazData(name="baz_data", data=bazs)
        container = BazBucket(bazs=bazs, baz_data=baz_data)
        manager = get_baz_buildmanager()

        with ZarrIO(self.store, manager=manager, mode="w") as writer:
            writer.write(container=container)

        with ZarrIO(self.store, manager=manager, mode="a") as append_io:
            read_container = append_io.read()
            new_baz = Baz(name="new")
            read_container.add_baz(new_baz)

            DoR = read_container.baz_data.data
            DoR.append(new_baz)

            append_io.write(read_container)

        with ZarrIO(self.store, manager=manager, mode="r") as append_io:
            read_container = append_io.read()
            self.assertEqual(len(read_container.baz_data.data), 11)
            self.assertIs(read_container.baz_data.data[10], read_container.bazs["new"])
