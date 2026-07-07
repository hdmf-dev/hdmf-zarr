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
from zarr.storage import LocalStore
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
#  LocalStore tests
#########################################
class TestZarrWriterLocalStore(BaseTestZarrWriter):
    """Test writing of builder with Zarr using a LocalStore"""

    def setUp(self):
        super().setUp()
        self.store = LocalStore(self.store_path)


class TestZarrWriteUnitLocalStore(BaseTestZarrWriteUnit):
    """Unit test for individual write functions using a LocalStore"""

    def setUp(self):
        self.store_path = "test_io.zarr"
        self.store = LocalStore(self.store_path)


class TestExportZarrToZarrLocalStore(BaseTestExportZarrToZarr):
    """Test exporting Zarr to Zarr using LocalStore"""

    def setUp(self):
        super().setUp()
        self.store = [LocalStore(p) for p in self.store_path]


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
        store = LocalStore(self.store_path)
        path = ZarrIO._ZarrIO__get_store_path(store)
        # In zarr v3, __get_store_path returns str(store) which is the LocalStore repr
        self.assertIsInstance(path, str)

    def test_get_store_path_deep(self):
        self.create_zarr()
        zarr_obj = zarr.open_consolidated(self.store_path, mode="r")
        store = zarr_obj.store
        path = ZarrIO._ZarrIO__get_store_path(store)
        self.assertIsInstance(path, str)

    def test_force_open_without_consolidated(self):
        """Test that read-mode -r forces a regular read with mode r"""
        self.create_zarr(consolidate_metadata=True)
        # Confirm that opening the file 'r' mode works
        with ZarrIO(self.store_path, mode="r") as read_io:
            read_io.open()
            self.assertIsNotNone(read_io._file)
        # Confirm that opening the file IN 'r-' mode also works
        with ZarrIO(self.store_path, mode="r-") as read_io:
            read_io.open()
            self.assertIsNotNone(read_io._file)

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

        with ZarrIO(self.store_path, manager=manager, mode="w") as writer:
            writer.write(container=container)

        with ZarrIO(self.store_path, manager=manager, mode="a") as append_io:
            read_container = append_io.read()
            new_baz = Baz(name="new")
            read_container.add_baz(new_baz)

            DoR = read_container.baz_data.data
            DoR.append(new_baz)

            append_io.write(read_container)

        with ZarrIO(self.store_path, manager=manager, mode="r") as append_io:
            read_container = append_io.read()
            self.assertEqual(len(read_container.baz_data.data), 11)
            self.assertIs(read_container.baz_data.data[10], read_container.bazs["new"])


class TestGenerateDatasetHtml(TestCase):
    """Test the generate_dataset_html static method"""

    def test_generate_dataset_html_basic(self):
        """Test basic HTML generation for a Zarr array"""
        from zarr.codecs import BloscCodec
        # Create a test zarr array
        store = zarr.storage.MemoryStore()
        z = zarr.create_array(store, shape=(100, 100), chunks=(10, 10), dtype="f4",
                              compressors=[BloscCodec()])
        z[:] = np.random.random((100, 100))

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify that HTML is generated and contains expected content
        self.assertIsInstance(html, str)
        self.assertIn("Zarr Array", html)
        self.assertIn("Float32", html)
        self.assertIn("table", html)  # Should contain HTML table

    def test_generate_dataset_html_with_compression(self):
        """Test HTML generation includes compression information"""
        from zarr.codecs import BloscCodec
        # Create a zarr array with specific compression
        store = zarr.storage.MemoryStore()
        z = zarr.create_array(store, shape=(50, 50), chunks=(25, 25), dtype="i4",
                              compressors=[BloscCodec(cname="zstd", clevel=9)])
        z[:] = np.arange(2500).reshape(50, 50)

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify compression info is included
        self.assertIn("Int32", html)

    def test_generate_dataset_html_no_compression(self):
        """Test HTML generation for uncompressed array"""
        # Create an uncompressed zarr array
        store = zarr.storage.MemoryStore()
        z = zarr.create_array(store, shape=(10, 10), chunks=(5, 5), dtype="f8", compressors=None)
        z[:] = np.random.random((10, 10))

        # Generate HTML representation
        html = ZarrIO.generate_dataset_html(z)

        # Verify basic info is present
        self.assertIn("Zarr Array", html)
        self.assertIn("Float64", html)
        self.assertIn("(10, 10)", html)

    def test_generate_dataset_html_non_zarr_object(self):
        """Test that passing a non-Zarr object returns an empty info dict in HTML"""
        non_zarr_array = np.float64(5)  # Just a float, not a Zarr array
        html = ZarrIO.generate_dataset_html(non_zarr_array)

        # Verify that HTML is generated and contains expected content
        self.assertIsInstance(html, str)
        self.assertIn("Array Read from ZarrIO (not a Zarr Array)", html)


class TestZarrStringDataset(TestCase):
    """Tests for the lazy StringDType wrapper used when reading string datasets."""

    def _make_dataset(self, shape, values):
        from hdmf_zarr.zarr_utils import ZarrStringDataset

        store = zarr.storage.MemoryStore()
        z = zarr.create_array(store, shape=shape, dtype=np.dtypes.StringDType())
        z[:] = np.array(values, dtype=np.dtypes.StringDType())
        # io is only stored on the wrapper; bypass ZarrIO.__init__ for the unit test
        io = object.__new__(ZarrIO)
        return ZarrStringDataset(z, io)

    def test_lazy_no_materialization_on_open(self):
        """Wrapping a dataset must not read the underlying array."""
        reads = []
        orig = zarr.Array.__getitem__
        zarr.Array.__getitem__ = lambda self, key: (reads.append(key) or orig(self, key))
        try:
            wrapper = self._make_dataset((3,), ["alpha", "beta", "gamma"])
            self.assertEqual(reads, [])  # nothing read just by wrapping
            self.assertEqual(wrapper[0], "alpha")  # single-element access reads one element
            self.assertEqual(reads, [0])
        finally:
            zarr.Array.__getitem__ = orig

    def test_shape_dtype_len_preserved(self):
        wrapper = self._make_dataset((2, 2), [["a", "b"], ["c", "d"]])
        self.assertEqual(wrapper.shape, (2, 2))
        self.assertEqual(wrapper.dtype, np.dtype(object))
        self.assertEqual(len(wrapper), 2)

    def test_scalar_and_slice_decoding(self):
        wrapper = self._make_dataset((3,), ["alpha", "beta", "gamma"])
        self.assertEqual(wrapper[0], "alpha")
        self.assertIsInstance(wrapper[0], str)
        self.assertEqual(list(wrapper[:]), ["alpha", "beta", "gamma"])

    def test_multidimensional_indexing(self):
        """A 2-D string dataset must support data[i, j] indexing."""
        wrapper = self._make_dataset((2, 2), [["a", "b"], ["c", "d"]])
        self.assertEqual(wrapper[1, 1], "d")
        self.assertEqual(wrapper[0, 1], "b")
        self.assertEqual(np.asarray(wrapper).shape, (2, 2))


class TestPathNormalization(TestCase):
    """Local paths are made absolute, but protocol URLs must be left untouched."""

    def _init_path(self, path, storage_options=None):
        """Construct a ZarrIO with open() stubbed out and return the normalized path."""
        from unittest.mock import patch

        with patch.object(ZarrIO, "open", lambda self: None):
            io = ZarrIO(path, mode="r", storage_options=storage_options)
        return io.path

    def test_local_paths_made_absolute(self):
        for path in ["relative/local.zarr", "./x.zarr", "/abs/local.zarr"]:
            self.assertEqual(self._init_path(path), os.path.abspath(path))

    def test_protocol_urls_unchanged(self):
        """Non-s3 fsspec protocols must not be rewritten into a local absolute path."""
        for path in [
            "s3://bucket/f.zarr",
            "gcs://bucket/f.zarr",
            "gs://bucket/f.zarr",
            "abfs://container/f.zarr",
            "az://container/f.zarr",
            "http://host/f.zarr",
            "https://host/f.zarr",
            "simplecache::s3://bucket/f.zarr",
        ]:
            self.assertEqual(
                self._init_path(path, storage_options={"anon": True}),
                path,
                f"protocol URL {path!r} was corrupted",
            )


class TestCopyArray(TestCase):
    """Tests for ZarrIO._copy_array, used when copying arrays during export."""

    @staticmethod
    def _dest_group():
        return zarr.open_group(zarr.storage.MemoryStore(), mode="w")

    def test_copy_multichunk_numeric(self):
        """Data spanning multiple chunks is copied correctly (chunk-wise)."""
        source = zarr.create_array(
            zarr.storage.MemoryStore(), shape=(5, 4), chunks=(2, 3), dtype="i4"
        )
        source[:] = np.arange(20).reshape(5, 4)
        source.attrs["zarr_dtype"] = "int32"
        dest = ZarrIO._copy_array(source, self._dest_group(), "x")
        np.testing.assert_array_equal(dest[:], source[:])
        self.assertEqual(dest.chunks, source.chunks)
        self.assertEqual(dest.attrs["zarr_dtype"], "int32")

    def test_copy_object_becomes_stringdtype(self):
        source = zarr.create_array(
            zarr.storage.MemoryStore(), shape=(3,), chunks=(2,), dtype=np.dtypes.StringDType()
        )
        source[:] = np.array(["aa", "bb", "cc"], dtype=np.dtypes.StringDType())
        dest = ZarrIO._copy_array(source, self._dest_group(), "y")
        self.assertEqual(list(dest[:]), ["aa", "bb", "cc"])

    def test_copy_scalar(self):
        source = zarr.create_array(zarr.storage.MemoryStore(), shape=(), dtype="f8")
        source[...] = 3.14
        dest = ZarrIO._copy_array(source, self._dest_group(), "z")
        self.assertEqual(dest[()], 3.14)
        self.assertEqual(dest.shape, ())
