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

from unittest import TestCase
from tests.unit.base_tests_zarrio import (
    BaseTestZarrWriter,
    ZarrStoreTestCase,
    BaseTestZarrWriteUnit,
    BaseTestExportZarrToZarr,
)
from zarr.storage import DirectoryStore, NestedDirectoryStore
from tests.unit.helpers.utils import Baz, BazData, BazBucket, get_baz_buildmanager, get_foo_buildmanager

import zarr
import numpy as np
from hdmf_zarr.backend import ZarrIO, ROOT_NAME
from .helpers.utils import BuildDatasetShapeMixin, BarData, BarDataHolder
from hdmf.spec import DatasetSpec
import os
import shutil
import warnings
import pathlib


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


#####################################################################
#  Default storage backend using just a string path to a subdirectory
#####################################################################
class TestZarrWriterSubdirectory(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a custom DirectoryStore"""

    def setUp(self):
        os.makedirs("test_dir")
        self.store_path = "test_dir/test_io.zarr"
        self.manager = get_foo_buildmanager()

    def tearDown(self):
        if os.path.exists("test_dir"):
            shutil.rmtree("test_dir")


class TestZarrWriteUnitSubdirectory(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a custom DirectoryStore"""

    def setUp(self):
        os.makedirs("test_dir")
        self.store_path = "test_dir/test_io.zarr"
        self.manager = get_foo_buildmanager()

    def tearDown(self):
        if os.path.exists("test_dir"):
            shutil.rmtree("test_dir")


class TestExportZarrToZarrSubdirectory(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using DirectoryStore"""

    def setUp(self):
        os.makedirs("test_dir")
        self.store_path = [os.path.join("test_dir", f"file{i}.zarr") for i in range(3)]
        self.manager = get_foo_buildmanager()

    def tearDown(self):
        if os.path.exists("test_dir"):
            shutil.rmtree("test_dir")


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
            self.assertIsInstance(read_io._file.store, zarr.storage.ConsolidatedMetadataStore)
        # Confirm that opening the file IN 'r-' mode indeed forces a regular open without consolidated metadata
        with ZarrIO(self.store_path, mode="r-") as read_io:
            read_io.open()
            self.assertIsInstance(read_io._file.store, zarr.storage.DirectoryStore)

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

    def test_is_remote_local_with_consolidated(self):
        """Test that is_remote() returns False for local stores with consolidated metadata."""
        self.create_zarr(consolidate_metadata=True)
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            self.assertFalse(read_io.is_remote())

    def test_is_remote_local_without_consolidated(self):
        """Test that is_remote() returns False for local stores without consolidated metadata."""
        self.create_zarr()
        with ZarrIO(self.store_path, mode="r-") as read_io:
            read_io.open()
            self.assertFalse(read_io.is_remote())


class TestResolveRef(ZarrStoreTestCase):
    """
    Tests for ``ZarrIO.resolve_ref``, focusing on the ``source == "."`` self-reference
    short-circuit that reuses the already-open file instead of re-opening the store.
    """

    def test_resolve_self_reference_to_object(self):
        """A self-reference to an object returns that object and its name."""
        self.create_zarr()
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            target_name, target_obj = read_io.resolve_ref({"source": ".", "path": "/dataset_1"})
            self.assertEqual(target_name, "dataset_1")
            self.assertEqual(target_obj.name, "/dataset_1")
            np.testing.assert_array_equal(target_obj[:], read_io._file["/dataset_1"][:])

    def test_resolve_self_reference_to_root(self):
        """A self-reference with no path returns the root group named ROOT_NAME."""
        self.create_zarr()
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            target_name, target_obj = read_io.resolve_ref({"source": ".", "path": None})
            self.assertEqual(target_name, ROOT_NAME)
            self.assertIs(target_obj, read_io._file)

    def test_resolve_self_reference_bad_path(self):
        """A self-reference to a nonexistent path raises a descriptive ValueError."""
        self.create_zarr()
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            with self.assertRaisesRegex(ValueError, "Found bad link to object /does_not_exist"):
                read_io.resolve_ref({"source": ".", "path": "/does_not_exist"})


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


class TestDatasetOfReferences(TestCase):
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


class TestGenerateDatasetHtml(TestCase):
    """Test the generate_dataset_html static method"""

    def test_generate_dataset_html_basic(self):
        """Test basic HTML generation for a Zarr array"""
        # Create a test zarr array
        store = zarr.MemoryStore()
        z = zarr.open_array(store, mode="w", shape=(100, 100), chunks=(10, 10), dtype="f4", compressor=zarr.Blosc())
        z[:] = np.random.random((100, 100))

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify that HTML is generated and contains expected content
        self.assertIsInstance(html, str)
        self.assertIn("Zarr Array", html)
        self.assertIn("float32", html)
        self.assertIn("(100, 100)", html)
        self.assertIn("(10, 10)", html)  # chunk shape
        self.assertIn("table", html)  # Should contain HTML table

    def test_generate_dataset_html_with_compression(self):
        """Test HTML generation includes compression information"""
        # Create a zarr array with specific compression
        store = zarr.MemoryStore()
        compressor = zarr.Blosc(cname="zstd", clevel=9)
        z = zarr.open_array(store, mode="w", shape=(50, 50), chunks=(25, 25), dtype="i4", compressor=compressor)
        z[:] = np.arange(2500).reshape(50, 50)

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify compression info is included
        self.assertIn("Compressor", html)
        self.assertIn("zstd", html)
        self.assertIn("int32", html)

    def test_generate_dataset_html_no_compression(self):
        """Test HTML generation for uncompressed array"""
        # Create an uncompressed zarr array
        store = zarr.MemoryStore()
        z = zarr.open_array(store, mode="w", shape=(10, 10), chunks=(5, 5), dtype="f8", compressor=None)
        z[:] = np.random.random((10, 10))

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify basic info is present
        self.assertIn("Zarr Array", html)
        self.assertIn("float64", html)
        self.assertIn("(10, 10)", html)
