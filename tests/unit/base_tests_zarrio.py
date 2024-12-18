"""
Module defining the base unit test cases for ZarrIO.

The actual tests are then instantiated with various different backends in the
test_zarrio.py module."""

import unittest
import os
import numpy as np
import shutil
import warnings

# Try to import Zarr and disable tests if Zarr is not available
import zarr
from hdmf_zarr.backend import ZarrIO
from hdmf_zarr.utils import ZarrDataIO, ZarrReference
from tests.unit.utils import Baz, BazData, BazBucket, get_baz_buildmanager

# Try to import numcodecs and disable compression tests if it is not available
try:
    from numcodecs import Blosc, Delta, JSON

    DISABLE_ZARR_COMPRESSION_TESTS = False
except ImportError:
    DISABLE_ZARR_COMPRESSION_TESTS = True

from hdmf.spec.namespace import NamespaceCatalog
from hdmf.build import GroupBuilder, DatasetBuilder, LinkBuilder, ReferenceBuilder, OrphanContainerBuildError
from hdmf.data_utils import DataChunkIterator
from hdmf.testing import TestCase
from hdmf.backends.io import HDMFIO, UnsupportedOperation

from tests.unit.utils import Foo, FooBucket, FooFile, get_foo_buildmanager, CacheSpecTestHelper

from abc import ABCMeta, abstractmethod


def total_size(source):
    """Helper function used to compute the size of a directory or file"""
    dsize = os.path.getsize(source)
    if os.path.isdir(source):
        for item in os.listdir(source):
            itempath = os.path.join(source, item)
            if os.path.isfile(itempath):
                dsize += os.path.getsize(itempath)
            elif os.path.isdir(itempath):
                dsize += total_size(itempath)
    return dsize


class BaseZarrWriterTestCase(TestCase, metaclass=ABCMeta):
    """
    Base class for unit tests for ZarrIO with support to configure the data store used.

    Child classes must implement the ``setUp`` function of the test and define the following
    main instance variables to define the data store to use for the tests defined here:

    :ivar store: The Zarr data store(s) to use.
    :type store: Same as the `path`` parameter of :py:class:`~hdmf_zarr.backend.ZarrIO.__init__ `
    :ivar store_path: The path(s) to the Zarr file defined by the store
    """

    @abstractmethod
    def setUp(self):
        raise NotImplementedError

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


class ZarrStoreTestCase(TestCase):
    """
    Class that creates a zarr file containing groups, datasets, and references for
    general purpose testing.
    """

    def setUp(self):
        self.store_path = "test_io.zarr"

    def tearDown(self):
        if os.path.exists(self.store_path):
            if os.path.isdir(self.store_path):
                shutil.rmtree(self.store_path)
            else:  # in case a test created a file instead of a directory
                os.remove(self.store_path)

    def createReferenceBuilder(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        data_2 = np.arange(0, 200, 10).reshape(4, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        dataset_2 = DatasetBuilder("dataset_2", data_2)

        ref_dataset_1 = ReferenceBuilder(dataset_1)
        ref_dataset_2 = ReferenceBuilder(dataset_2)
        ref_data = [ref_dataset_1, ref_dataset_2]
        dataset_ref = DatasetBuilder("ref_dataset", ref_data, dtype="object")

        builder = GroupBuilder(
            name="root",
            source=self.store_path,
            datasets={"dataset_1": dataset_1, "dataset_2": dataset_2, "ref_dataset": dataset_ref},
        )
        return builder

    def create_zarr(self, consolidate_metadata=True, force_overwrite=False, mode="a"):
        builder = self.createReferenceBuilder()
        writer = ZarrIO(self.store_path, mode=mode, force_overwrite=force_overwrite)
        writer.write_builder(builder, consolidate_metadata)
        writer.close()


class BaseTestZarrWriter(BaseZarrWriterTestCase):
    """
    Test writing of builder with ZarrIO

    The following main instance variables need to be set by child classes to
    customize the data store to use for the tests defined here:

    :ivar store: The Zarr data store to use.
    :type store: Same as the `path`` parameter of :py:class:`~hdmf_zarr.backend.ZarrIO.__init__ `
    :ivar store_path: The path(s) to the Zarr file defined by the store

    The builder data for the tests is defined by:

    :ivar manager: The build manager to use for writing the builders

    and the functions ``createGroupBuilder``, ``createReferenceBuilder`` and
    ``createReferenceCompoundBuilder``. Customizing the builder data is in
    principle possible in child classes but has not been tested.
    """

    def setUp(self):
        self.manager = get_foo_buildmanager()
        self.store_path = "test_io.zarr"

    def createGroupBuilder(self):
        self.foo_builder = GroupBuilder(
            "foo1",
            attributes={"data_type": "Foo", "namespace": "test_core", "attr1": 17.5},
            datasets={"my_data": self.__dataset_builder},
        )
        # self.foo = Foo('foo1', self.__dataset_builder.data, attr1="bar", attr2=17, attr3=3.14)
        # self.manager.prebuilt(self.foo, self.foo_builder)
        self.builder = GroupBuilder(
            name="root",
            source=self.store_path,
            groups={
                "test_bucket": GroupBuilder(
                    name="test_bucket",
                    groups={
                        "foo_holder": GroupBuilder(name="foo_holder", groups={"foo1": self.foo_builder}),
                    },
                )
            },
            attributes={"data_type": "FooFile"},
        )

    def createReferenceBuilder(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        data_2 = np.arange(0, 200, 10).reshape(4, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        dataset_2 = DatasetBuilder("dataset_2", data_2)

        ref_dataset_1 = ReferenceBuilder(dataset_1)
        ref_dataset_2 = ReferenceBuilder(dataset_2)
        ref_data = [ref_dataset_1, ref_dataset_2]
        dataset_ref = DatasetBuilder("ref_dataset", ref_data, dtype="object")

        builder = GroupBuilder(
            name="root",
            source=self.store_path,
            datasets={"dataset_1": dataset_1, "dataset_2": dataset_2, "ref_dataset": dataset_ref},
        )
        return builder

    def createReferenceCompoundBuilder(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        data_2 = np.arange(0, 200, 10).reshape(4, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        dataset_2 = DatasetBuilder("dataset_2", data_2)

        ref_dataset_1 = ReferenceBuilder(dataset_1)
        ref_dataset_2 = ReferenceBuilder(dataset_2)
        ref_data = [
            (1, "dataset_1", ref_dataset_1),
            (2, "dataset_2", ref_dataset_2),
        ]
        ref_data_type = [
            {"name": "id", "dtype": "int"},
            {"name": "name", "dtype": str},
            {"name": "reference", "dtype": "object"},
        ]
        dataset_ref = DatasetBuilder("ref_dataset", ref_data, dtype=ref_data_type)
        builder = GroupBuilder(
            name="root",
            source=self.store_path,
            datasets={"dataset_1": dataset_1, "dataset_2": dataset_2, "ref_dataset": dataset_ref},
        )
        return builder

    def test_cannot_read(self):
        assert not ZarrIO.can_read("incorrect_path")

    def read_test_dataset(self):
        reader = ZarrIO(self.store_path, manager=self.manager, mode="r")
        self.root = reader.read_builder()
        dataset = self.root["test_bucket/foo_holder/foo1/my_data"]
        return dataset

    def read(self):
        reader = ZarrIO(self.store_path, manager=self.manager, mode="r")
        self.root = reader.read_builder()

    def test_cache_spec(self):

        tempIO = ZarrIO(self.store_path, manager=self.manager, mode="w")

        # Setup all the data we need
        foo1 = Foo("foo1", [0, 1, 2, 3, 4], "I am foo1", 17, 3.14)
        foo2 = Foo("foo2", [5, 6, 7, 8, 9], "I am foo2", 34, 6.28)
        foobucket = FooBucket("test_bucket", [foo1, foo2])
        foofile = FooFile(buckets=[foobucket])

        # Write the first file
        tempIO.write(foofile, cache_spec=True)
        tempIO.close()

        # Load the spec and assert that it is valid
        ns_catalog = NamespaceCatalog()
        ZarrIO.load_namespaces(ns_catalog, self.store_path)
        self.assertEqual(ns_catalog.namespaces, ("test_core",))
        source_types = CacheSpecTestHelper.get_types(self.manager.namespace_catalog)
        read_types = CacheSpecTestHelper.get_types(ns_catalog)
        self.assertSetEqual(source_types, read_types)

    def test_write_int(self, test_data=None):
        data = np.arange(100, 200, 10).reshape(2, 5) if test_data is None else test_data
        self.__dataset_builder = DatasetBuilder("my_data", data, attributes={"attr2": 17})
        self.createGroupBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        writer.close()
        assert ZarrIO.can_read(self.store_path)

    def test_write_compound(self, test_data=None):
        """
        :param test_data: Optional list of the form [(1, 'STR1'), (2, 'STR2')], i.e., a list of tuples where
                          each tuple consists of an int and a string
        :return:
        """
        if test_data is None:
            test_data = [(1, "Allen"), (2, "Bob"), (3, "Mike"), (4, "Jenny")]
        data_type = [{"name": "id", "dtype": "int"}, {"name": "name", "dtype": str}]
        self.__dataset_builder = DatasetBuilder("my_data", test_data, dtype=data_type)
        self.createGroupBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="w")
        writer.write_builder(self.builder)
        writer.close()

    def test_write_chunk(self, test_data=None):
        if test_data is None:
            test_data = np.arange(100, 200, 10).reshape(2, 5)
        data_io = ZarrDataIO(data=test_data, chunks=(1, 5), fillvalue=-1)
        self.__dataset_builder = DatasetBuilder("my_data", data_io, attributes={"attr2": 17})
        self.createGroupBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        writer.close()

    def test_write_strings(self, test_data=None):
        if test_data is None:
            test_data = [["a", "aa", "aaa", "aaaa", "aaaaa"], ["b", "bb", "bbb", "bbbb", "bbbbb"]]
        self.__dataset_builder = DatasetBuilder("my_data", test_data, attributes={"attr2": 17})
        self.createGroupBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        writer.close()

    def test_write_links(self, test_data=None):
        if test_data is None:
            test_data = np.arange(100, 200, 10).reshape(2, 5)
        self.__dataset_builder = DatasetBuilder("my_data", test_data, attributes={"attr2": 17})
        self.createGroupBuilder()
        link_parent = self.builder["test_bucket"]
        link_parent.set_link(LinkBuilder(self.foo_builder, "my_link"))
        link_parent.set_link(LinkBuilder(self.__dataset_builder, "my_dataset"))
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        writer.close()

    def test_write_link_array(self):
        data = np.arange(100, 200, 10).reshape(2, 5)
        self.__dataset_builder = DatasetBuilder("my_data", data, attributes={"attr2": 17})
        self.createGroupBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        zarr_file = zarr.open(self.store_path, mode="r")
        zarr_array = zarr_file["/test_bucket/foo_holder/foo1/my_data"]
        link_io = ZarrDataIO(data=zarr_array, link_data=True)
        link_dataset = DatasetBuilder("dataset_link", link_io)
        self.builder["test_bucket"].set_dataset(link_dataset)
        writer.write_builder(self.builder)
        writer.close()

        reader = ZarrIO(self.store_path, manager=self.manager, mode="r")
        self.root = reader.read_builder()
        read_link = self.root["test_bucket/dataset_link"]
        read_link_data = read_link["builder"]["data"][:]
        self.assertTrue(np.all(data == read_link_data))
        reader.close()

    def test_write_reference(self):
        builder = self.createReferenceBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(builder)
        writer.close()

    def test_write_references_roundtrip(self):
        # Setup a file container with references
        num_bazs = 1
        bazs = []  # set up dataset of references
        for i in range(num_bazs):
            bazs.append(Baz(name="baz%d" % i))
        baz_data = BazData(name="baz_data", data=bazs)
        container = BazBucket(bazs=bazs, baz_data=baz_data)
        manager = get_baz_buildmanager()
        # write to file
        with ZarrIO(self.store_path, manager=manager, mode="w") as writer:
            writer.write(container=container)
        # read from file and validate references
        with ZarrIO(self.store_path, manager=manager, mode="r") as reader:
            read_container = reader.read()
            for i in range(num_bazs):
                baz_name = "baz%d" % i
                expected_container = read_container.bazs[baz_name]
                expected_value = {
                    "source": "test_io.zarr",
                    "path": "/bazs/" + baz_name,
                    "object_id": expected_container.object_id,
                    "source_object_id": read_container.object_id,
                }
                # Read the dict with the definition of the reference from the raw Zarr file and compare
                # to also check that reference (included object id's) are defined correctly
                self.assertDictEqual(reader.file["baz_data"][i], expected_value)
                # Also test using the low-level reference functions
                zarr_ref = ZarrReference(**expected_value)
                # Check the ZarrReference first
                self.assertEqual(zarr_ref.object_id, expected_value["object_id"])
                self.assertEqual(zarr_ref.source_object_id, expected_value["source_object_id"])

    def test_write_reference_compound(self):
        builder = self.createReferenceCompoundBuilder()
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(builder)
        writer.close()

    def test_read_int(self):
        test_data = np.arange(100, 200, 10).reshape(5, 2)
        self.test_write_int(test_data=test_data)
        dataset = self.read_test_dataset()["data"][:]
        self.assertTrue(np.all(test_data == dataset))

    def test_read_chunk(self):
        test_data = np.arange(100, 200, 10).reshape(5, 2)
        self.test_write_chunk(test_data=test_data)
        dataset = self.read_test_dataset()["data"][:]
        self.assertTrue(np.all(test_data == dataset))

    def test_read_strings(self):
        test_data = [["a1", "aa2", "aaa3", "aaaa4", "aaaaa5"], ["b1", "bb2", "bbb3", "bbbb4", "bbbbb5"]]
        self.test_write_strings(test_data=test_data)
        dataset = self.read_test_dataset()["data"][:]
        self.assertTrue(np.all(np.asarray(test_data) == dataset))

    def test_read_compound(self):
        test_data = [(1, "Allen1"), (2, "Bob1"), (3, "Mike1")]
        self.test_write_compound(test_data=test_data)
        dataset = self.read_test_dataset()["data"]
        self.assertTupleEqual(test_data[0], tuple(dataset[0]))
        self.assertTupleEqual(test_data[1], tuple(dataset[1]))
        self.assertTupleEqual(test_data[2], tuple(dataset[2]))

    def test_read_link(self):
        test_data = np.arange(100, 200, 10).reshape(5, 2)
        self.test_write_links(test_data=test_data)
        self.read()
        link_data = self.root["test_bucket"].links["my_dataset"].builder.data[()]
        self.assertTrue(np.all(np.asarray(test_data) == link_data))
        # print(self.root['test_bucket'].links['my_dataset'].builder.data[()])

    def test_read_link_buf(self):
        data = np.arange(100, 200, 10).reshape(2, 5)
        self.__dataset_builder = DatasetBuilder("my_data", data, attributes={"attr2": 17})
        self.createGroupBuilder()
        link_parent_1 = self.builder["test_bucket"]
        link_parent_2 = self.builder["test_bucket/foo_holder"]
        link_parent_1.set_link(LinkBuilder(self.__dataset_builder, "my_dataset_1"))
        link_parent_2.set_link(LinkBuilder(self.__dataset_builder, "my_dataset_2"))
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(self.builder)
        writer.close()
        self.read()
        self.assertTrue(
            self.root["test_bucket"].links["my_dataset_1"].builder
            == self.root["test_bucket/foo_holder"].links["my_dataset_2"].builder
        )

    def test_read_reference(self):
        self.test_write_reference()
        self.read()
        builder = self.createReferenceBuilder()["ref_dataset"]
        read_builder = self.root["ref_dataset"]
        # Load the linked arrays and confirm we get the same data as we had in the original builder
        for i, v in enumerate(read_builder["data"]):
            self.assertTrue(np.all(builder["data"][i]["builder"]["data"] == v["data"][:]))

    def test_read_reference_compound(self):
        self.test_write_reference_compound()
        self.read()
        builder = self.createReferenceCompoundBuilder()["ref_dataset"]
        read_builder = self.root["ref_dataset"]

        # ensure the array was written as a compound array
        ref_dtype = np.dtype([("id", "<i4"), ("name", "O"), ("reference", "O")])
        self.assertEqual(read_builder.data.dataset.dtype, ref_dtype)

        # Load the elements of each entry in the compound dataset and compar the index, string, and referenced array
        for i, v in enumerate(read_builder["data"]):
            self.assertEqual(v[0], builder["data"][i][0])  # Compare index value from compound tuple
            self.assertEqual(v[1], builder["data"][i][1])  # Compare string value from compound tuple
            self.assertTrue(np.all(v[2]["data"][:] == builder["data"][i][2]["builder"]["data"][:]))  # Compare ref array
        # print(read_builder)

    def test_read_reference_compound_buf(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        data_2 = np.arange(0, 200, 10).reshape(4, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        dataset_2 = DatasetBuilder("dataset_2", data_2)

        # ref_dataset_1 = ReferenceBuilder(dataset_1)
        # ref_dataset_2 = ReferenceBuilder(dataset_2)
        ref_data = [
            (1, "dataset_1", ReferenceBuilder(dataset_1)),
            (2, "dataset_2", ReferenceBuilder(dataset_2)),
            (3, "dataset_3", ReferenceBuilder(dataset_1)),
            (4, "dataset_4", ReferenceBuilder(dataset_2)),
        ]
        ref_data_type = [
            {"name": "id", "dtype": "int"},
            {"name": "name", "dtype": str},
            {"name": "reference", "dtype": "object"},
        ]
        dataset_ref = DatasetBuilder("ref_dataset", ref_data, dtype=ref_data_type)
        builder = GroupBuilder(
            name="root",
            source=self.store_path,
            datasets={
                "dataset_1": dataset_1,
                "dataset_2": dataset_2,
                "ref_dataset": dataset_ref,
            },
        )
        writer = ZarrIO(self.store_path, manager=self.manager, mode="a")
        writer.write_builder(builder)
        writer.close()

        self.read()
        self.assertFalse(self.root["ref_dataset"].data[0][2] == self.root["ref_dataset"].data[1][2])
        self.assertTrue(self.root["ref_dataset"].data[0][2] == self.root["ref_dataset"].data[2][2])


class BaseTestZarrWriteUnit(BaseZarrWriterTestCase):
    """
    Unit test for individual write functions
    """

    def setUp(self):
        self.store_path = "test_io.zarr"

    #############################################
    #  ZarrDataIO general
    #############################################
    def test_set_object_codec(self):
        # Test that the default codec is the Pickle store
        tempIO = ZarrIO(self.store_path, mode="w")
        self.assertEqual(tempIO.object_codec_class.__qualname__, "Pickle")
        del tempIO  # also calls tempIO.close()
        tempIO = ZarrIO(self.store_path, mode="w", object_codec_class=JSON)
        self.assertEqual(tempIO.object_codec_class.__qualname__, "JSON")
        tempIO.close()

    def test_synchronizer_constructor_arg_bool(self):
        """Test that setting the synchronizer argument to True/False works in ZarrIO"""
        tempIO = ZarrIO(self.store_path, mode="w", synchronizer=False)
        self.assertIsNone(tempIO.synchronizer)
        del tempIO  # also calls tempIO.close()
        tempIO = ZarrIO(self.store_path, mode="w", synchronizer=True)
        self.assertTrue(isinstance(tempIO.synchronizer, zarr.ProcessSynchronizer))
        tempIO.close()

    def test_zarrdataio_enable_default_compressor(self):
        """Default compression simply means not specifying any compressor and using Zarr defaults"""
        dataio = ZarrDataIO(np.arange(30).reshape(5, 2, 3), compressor=True)
        self.assertEqual(len(dataio.io_settings), 0)

    def test_zarrdataio_disable_compressor(self):
        """Test that ZarrDataIO.__array__ is working when wrapping an ndarray"""
        test_speed = np.array([10.0, 20.0])
        data = ZarrDataIO((test_speed), compressor=False)
        self.assertIsNone(data.io_settings["compressor"])

    def test_zarrdataio_array_conversion_numpy(self):
        """Test that ZarrDataIO.__array__ is working when wrapping an ndarray"""
        test_speed = np.array([10.0, 20.0])
        data = ZarrDataIO((test_speed))
        self.assertTrue(np.all(np.isfinite(data)))  # Force call of ZarrDataIO.__array__

    def test_zarrdataio_array_conversion_list(self):
        """Test that ZarrDataIO.__array__ is working when wrapping a python list"""
        test_speed = [10.0, 20.0]
        data = ZarrDataIO(test_speed)
        self.assertTrue(np.all(np.isfinite(data)))  # Force call of ZarrDataIO.__array__

    def test_zarrdataio_array_conversion_datachunkiterator(self):
        """Test that ZarrDataIO.__array__ is working when wrapping a python list"""
        test_speed = DataChunkIterator(data=[10.0, 20.0])
        data = ZarrDataIO(test_speed)
        with self.assertRaises(NotImplementedError):
            np.isfinite(data)  # Force call of H5DataIO.__array__

    def test_get_builder_exists_on_disk(self):
        """Test that get_builder_exists_on_disk finds the existing builder"""
        dset_builder = DatasetBuilder("test_dataset", 10, attributes={})
        tempIO = ZarrIO(self.store_path, mode="w")
        self.assertFalse(tempIO.get_builder_exists_on_disk(builder=dset_builder))  # Make sure is False is before write
        tempIO.write_dataset(tempIO.file, dset_builder)
        self.assertTrue(tempIO.get_builder_exists_on_disk(builder=dset_builder))  # Make sure is True after write
        tempIO.close()

    def test_get_written(self):
        """Test that get_builder_exists_on_disk finds the existing builder"""
        tempIO = ZarrIO(self.store_path, mode="w")
        dset_builder = DatasetBuilder("test_dataset", 10, attributes={})
        self.assertFalse(tempIO.get_written(dset_builder))  # Make sure False is returned before write
        tempIO.write_dataset(tempIO.file, dset_builder)
        self.assertTrue(tempIO.get_written(dset_builder))  # Make sure True is returned after write
        self.assertTrue(tempIO.get_written(dset_builder, check_on_disk=True))  # Make sure its also on disk
        # Now delete it from disk and check again.
        builder_path = tempIO.get_builder_disk_path(dset_builder)
        if os.path.isdir(builder_path):  # Skip this check for file-based stores were we can easily delete objects
            shutil.rmtree(builder_path)
            # The written flag should still be true
            self.assertTrue(tempIO.get_written(dset_builder))
            # But with check on disk should fail
            self.assertFalse(tempIO.get_written(dset_builder, check_on_disk=True))
        tempIO.close()

    ##########################################
    #  write_attributes
    ##########################################
    def __write_attribute_test_helper(self, name, value, assert_value=True):
        """
        Helper function to write a single attribute and check its value for correctness

        :param name: Name of the attribute
        :param value: Value of the attribute
        :param assert_value: Boolean indicating whether we should check correctness of the returned value
        :returns: the value read from disk so we can do our own tests if needed
        """
        # write the attribute
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        testgroup = tempIO.file  # For testing we just use our file and create some attributes
        attr = {name: value}
        tempIO.write_attributes(testgroup, attr)
        # read the attribute
        read_val = testgroup.attrs[name]
        # assert that the read value matches the expected value
        if assert_value:
            if isinstance(value, (list, tuple, set)):
                self.assertTupleEqual(read_val, tuple(value))
            elif isinstance(value, np.ndarray):
                self.assertListEqual(list(read_val), value.tolist())
            else:
                self.assertEqual(testgroup.attrs[name], value)
        tempIO.close()
        return read_val

    def test_write_attributes_write_scalar_int(self):
        self.__write_attribute_test_helper("intattr", np.int32(5))
        self.__write_attribute_test_helper("intattr", 10)

    def test_write_attributes_write_scalar_float(self):
        self.__write_attribute_test_helper("floatattr", np.float64(50.0))
        self.__write_attribute_test_helper("floatattr", 50.2)

    def test_write_attributes_write_scalar_str(self):
        self.__write_attribute_test_helper("strattr", "a")
        self.__write_attribute_test_helper("strattr", "Hello World")

    def test_write_attributes_write_unsupported_scalar_type(self):
        with self.assertRaises(TypeError):
            self.__write_attribute_test_helper("strattr", np.int32)

    def test_write_attributes_write_list_of_ints(self):
        self.__write_attribute_test_helper("attr", list(range(10)))
        self.__write_attribute_test_helper("attr", list(range(100)))

    def test_write_attributes_write_list_of_strings(self):
        self.__write_attribute_test_helper("attr", ["a", "b", "c", "d"])
        self.__write_attribute_test_helper("attr", ["e", "f", "g"])

    def test_write_attributes_write_set_of_strings(self):
        self.__write_attribute_test_helper("attr", set(["a", "b", "c", "d"]))
        self.__write_attribute_test_helper("attr", set(["e", "f", "g"]))

    def test_write_attributes_write_tuple_of_strings(self):
        self.__write_attribute_test_helper("attr", tuple(["a", "b", "c", "d"]))
        self.__write_attribute_test_helper("attr", tuple(["e", "f", "g"]))

    def test_write_attribute_write_unsupported_list_of_types(self):
        """Test that writing a list of types fails"""
        with self.assertRaises(TypeError):
            self.__write_attribute_test_helper("attr", [np.int32, np.float64])

    def test_write_attributes_write_list_of_bytes(self):
        """
        Test writing of lists of bytes. Bytes are not JSON serializable and therefore cover a different code path.
        Note, bytes are here encoded as strings to the return value does not match exactly but the data type changes.
        """
        val = self.__write_attribute_test_helper("attr", [b"a", b"b", b"c", b"d"], assert_value=False)
        self.assertTupleEqual(val, tuple(["a", "b", "c", "d"]))
        val = self.__write_attribute_test_helper("attr", [b"e", b"f", b"g"], assert_value=False)
        self.assertTupleEqual(val, tuple(["e", "f", "g"]))

    def test_write_attributes_write_1Darray_of_floats(self):
        self.__write_attribute_test_helper("attr", np.arange(10).astype("float") + 0.1)

    def test_write_attributes_write_3Darray_of_floats(self):
        self.__write_attribute_test_helper("attr", np.arange(18).astype("float").reshape((2, 3, 3)) + 0.1)

    def test_write_attributes_write_reference_to_datasetbuilder(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        attr = {"attr1": dataset_1}
        with self.assertWarnsWith(
            UserWarning, "Could not determine source_object_id for builder with path: /dataset_1"
        ):
            tempIO.write_attributes(obj=tempIO.file, attributes=attr)
        expected_value = {
            "attr1": {
                "zarr_dtype": "object",
                "value": {
                    "source": "test_io.zarr",
                    "path": "/dataset_1",
                    "object_id": None,
                    "source_object_id": None,
                },
            }
        }
        self.assertDictEqual(tempIO.file.attrs.asdict(), expected_value)
        tempIO.close()

    def test_write_attributes_write_reference_to_referencebuilder(self):
        data_1 = np.arange(100, 200, 10).reshape(2, 5)
        dataset_1 = DatasetBuilder("dataset_1", data_1)
        ref1 = ReferenceBuilder(dataset_1)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        attr = {"attr1": ref1}
        with self.assertWarnsWith(
            UserWarning, "Could not determine source_object_id for builder with path: /dataset_1"
        ):
            tempIO.write_attributes(obj=tempIO.file, attributes=attr)
        expected_value = {
            "attr1": {
                "zarr_dtype": "object",
                "value": {
                    "source": "test_io.zarr",
                    "path": "/dataset_1",
                    "source_object_id": None,
                    "object_id": None,
                },
            }
        }
        self.assertDictEqual(tempIO.file.attrs.asdict(), expected_value)
        tempIO.close()

    ##########################################
    #  write_dataset tests: scalars
    ##########################################
    def test_write_dataset_scalar(self):
        a = 10
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTupleEqual(dset.shape, (1,))
        self.assertEqual(dset[()], a)
        tempIO.close()

    def test_write_dataset_string(self):
        a = "test string"
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTupleEqual(dset.shape, (1,))
        self.assertEqual(dset[()], a)
        tempIO.close()

    ##########################################
    #  write_dataset tests: lists
    ##########################################
    def test_write_dataset_list(self):
        a = np.arange(30).reshape(5, 2, 3)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a.tolist(), attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTrue(np.all(dset[:] == a))
        tempIO.close()

    def test_write_dataset_list_chunked(self):
        a = ZarrDataIO(np.arange(30).reshape(5, 2, 3), chunks=(1, 1, 3))
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTrue(np.all(dset[:] == a.data))
        self.assertEqual(dset.chunks, (1, 1, 3))
        tempIO.close()

    def test_write_dataset_list_fillvalue(self):
        a = ZarrDataIO(np.arange(20).reshape(5, 4), fillvalue=-1)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTrue(np.all(dset[:] == a.data))
        self.assertEqual(dset.fill_value, -1)
        tempIO.close()

    @unittest.skipIf(DISABLE_ZARR_COMPRESSION_TESTS, "Skip test due to numcodec compressor not available")
    def test_write_dataset_list_compress(self):
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
        a = ZarrDataIO(np.arange(30).reshape(5, 2, 3), compressor=compressor)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTrue(np.all(dset[:] == a.data))
        self.assertTrue(dset.compressor == compressor)
        tempIO.close()

    @unittest.skipIf(DISABLE_ZARR_COMPRESSION_TESTS, "Skip test due to numcodec compressor not available")
    def test_write_dataset_list_compress_and_filter(self):
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
        filters = [Delta(dtype="i4")]
        a = ZarrDataIO(np.arange(30, dtype="i4").reshape(5, 2, 3), compressor=compressor, filters=filters)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", a, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertTrue(np.all(dset[:] == a.data))
        self.assertTrue(dset.compressor == compressor)
        self.assertListEqual(dset.filters, filters)
        tempIO.close()

    ##########################################
    #  write_dataset tests: Iterable
    ##########################################
    def test_write_dataset_iterable(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", range(10), attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertListEqual(dset[:].tolist(), list(range(10)))
        tempIO.close()

    ##############################################
    #  write_dataset tests: compound data tables
    #############################################
    def test_write_structured_array_table(self):
        cmpd_dt = np.dtype([("a", np.int32), ("b", np.float64)])
        data = np.zeros(10, dtype=cmpd_dt)
        data["a"][1] = 101
        data["b"][1] = 0.1
        dt = [
            {"name": "a", "dtype": "int32", "doc": "a column"},
            {"name": "b", "dtype": "float64", "doc": "b column"},
        ]
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", data, attributes={}, dtype=dt))
        dset = tempIO.file["test_dataset"]
        self.assertEqual(dset["a"].tolist(), data["a"].tolist())
        self.assertEqual(dset["b"].tolist(), data["b"].tolist())
        tempIO.close()

    def test_write_nested_structured_array_table(self):
        b_cmpd_dt = np.dtype([("c", np.int32), ("d", np.float64)])
        cmpd_dt = np.dtype([("a", np.int32), ("b", b_cmpd_dt)])
        data = np.zeros(10, dtype=cmpd_dt)
        data["a"][1] = 101
        data["b"]["c"] = 202
        data["b"]["d"] = 10.1
        b_dt = [
            {"name": "c", "dtype": "int32", "doc": "c column"},
            {"name": "d", "dtype": "float64", "doc": "d column"},
        ]
        dt = [
            {"name": "a", "dtype": "int32", "doc": "a column"},
            {"name": "b", "dtype": b_dt, "doc": "b column"},
        ]
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", data, attributes={}, dtype=dt))
        dset = tempIO.file["test_dataset"]
        # Test that all elements match. dset return np.void types so we just compare strings for simplicity
        for i in range(10):
            self.assertEqual(str(dset[i]), str(data[i]))
        tempIO.close()

    #############################################
    #  write_dataset tests: data chunk iterator
    #############################################
    def test_write_dataset_iterable_multidimensional_array(self):
        a = np.arange(30).reshape(5, 2, 3)
        aiter = iter(a)
        daiter = DataChunkIterator.from_iterable(aiter, buffer_size=2)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(parent=tempIO.file, builder=DatasetBuilder("test_dataset", daiter, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertListEqual(dset[:].tolist(), a.tolist())
        tempIO.close()

    def test_write_dataset_iterable_multidimensional_array_compression(self):
        a = np.arange(30).reshape(5, 2, 3)
        aiter = iter(a)
        daiter = DataChunkIterator.from_iterable(aiter, buffer_size=2)
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
        wrapped_daiter = ZarrDataIO(data=daiter, compressor=compressor)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", wrapped_daiter, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertEqual(dset.shape, a.shape)
        self.assertListEqual(dset[:].tolist(), a.tolist())
        self.assertTrue(dset.compressor == compressor)
        tempIO.close()

    def test_write_dataset_data_chunk_iterator(self):
        dci = DataChunkIterator(data=np.arange(10), buffer_size=2)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", dci, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertListEqual(dset[:].tolist(), list(range(10)))
        tempIO.close()

    def test_write_dataset_data_chunk_iterator_with_compression(self):
        dci = DataChunkIterator(data=np.arange(10), buffer_size=2)
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
        wrapped_dci = ZarrDataIO(data=dci, compressor=compressor, chunks=(2,))
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", wrapped_dci, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertListEqual(dset[:].tolist(), list(range(10)))
        self.assertTrue(dset.compressor == compressor)
        self.assertEqual(dset.chunks, (2,))
        tempIO.close()

    def test_pass_through_of_recommended_chunks(self):

        class DC(DataChunkIterator):
            def recommended_chunk_shape(self):
                return (5, 1, 1)

        dci = DC(data=np.arange(30).reshape(5, 2, 3))
        compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
        wrapped_dci = ZarrDataIO(data=dci, compressor=compressor)
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, DatasetBuilder("test_dataset", wrapped_dci, attributes={}))
        dset = tempIO.file["test_dataset"]
        self.assertEqual(dset.chunks, (5, 1, 1))
        self.assertTrue(dset.compressor == compressor)
        tempIO.close()

    #############################################
    #  Copy/Link h5py.Dataset object
    #############################################
    def test_link_zarr_dataset_input(self):
        dset = DatasetBuilder("test_dataset", np.arange(10), attributes={})
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(tempIO.file, builder=dset)
        softlink = DatasetBuilder("test_softlink", tempIO.file["test_dataset"], attributes={})
        tempIO.write_dataset(tempIO.file, builder=softlink)
        tempf = zarr.open(store=self.store_path, mode="r")
        expected_link = {
            "name": "test_softlink",
            "path": "/test_dataset",
            "source": os.path.abspath(self.store_path),
        }
        self.assertEqual(len(tempf.attrs["zarr_link"]), 1)
        self.assertDictEqual(tempf.attrs["zarr_link"][0], expected_link)
        tempIO.close()

    def test_copy_zarr_dataset_input(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder("test_dataset", np.arange(10), attributes={}),
        )
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder("test_copy", tempIO.file["test_dataset"], attributes={}),
            link_data=False,
        )
        # NOTE: In HDF5 this would be a HardLink. Since Zarr does not support links, this will be a copy instead.
        self.assertListEqual(tempIO.file["test_dataset"][:].tolist(), tempIO.file["test_copy"][:].tolist())
        tempIO.close()

    def test_link_dataset_zarrdataio_input(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder("test_dataset", np.arange(10), attributes={}),
        )
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder(
                "test_softlink",
                ZarrDataIO(data=tempIO.file["test_dataset"], link_data=True),
                attributes={},
            ),
        )
        tempf = zarr.open(self.store_path, mode="r")
        expected_link = {
            "name": "test_softlink",
            "path": "/test_dataset",
            "source": os.path.abspath(self.store_path),
        }
        self.assertEqual(len(tempf.attrs["zarr_link"]), 1)
        self.assertDictEqual(tempf.attrs["zarr_link"][0], expected_link)
        tempIO.close()

    def test_copy_dataset_zarrdataio_input(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder("test_dataset", np.arange(10), attributes={}),
        )
        tempIO.write_dataset(
            tempIO.file,
            DatasetBuilder(
                "test_copy",
                ZarrDataIO(data=tempIO.file["test_dataset"], link_data=False),  # Force dataset copy
                attributes={},
            ),
            link_data=True,
        )  # Make sure the default behavior is set to link the data
        # NOTE: In HDF5 this would be a HardLink. Since Zarr does not support links, this will be a copy instead.
        self.assertListEqual(tempIO.file["test_dataset"][:].tolist(), tempIO.file["test_copy"][:].tolist())
        tempIO.close()

    def test_list_fill_empty(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        dset = tempIO.__list_fill__(tempIO.file, "empty_dataset", [], options={"dtype": int, "io_settings": {}})
        self.assertTupleEqual(dset.shape, (0,))
        tempIO.close()

    def test_list_fill_empty_no_dtype(self):
        tempIO = ZarrIO(self.store_path, mode="w")
        tempIO.open()
        with self.assertRaisesRegex(Exception, r"cannot add empty_dataset to / - could not determine type"):
            tempIO.__list_fill__(tempIO.file, "empty_dataset", [])
        tempIO.close()


class BaseTestExportZarrToZarr(BaseZarrWriterTestCase):
    """
    Test exporting Zarr to Zarr.

    In contrast to the normal BaseZarrWriterTestCase, here the store and store_path
    variable require to be a list of length 4.

    :ivar store: List of 4  Zarr data stores to use.
    :type store: List of 4 store values. Stores are the same as the `path``
                  parameter of :py:class:`~hdmf_zarr.backend.ZarrIO.__init__ `
    :ivar store_path: The paths to the Zarr file defined by the stores
    """

    def setUp(self):
        self.store_path = [f"file{i}.zarr" for i in range(3)]

    def test_basic(self):
        """Test that exporting a written container works between Zarr and Zarr."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io)

        self.assertTrue(os.path.exists(self.store_path[1]))
        self.assertEqual(os.path.relpath(foofile.container_source), self.store_path[0])

        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            self.assertEqual(os.path.relpath(read_foofile.container_source), self.store_path[1])
            self.assertContainerEqual(foofile, read_foofile, ignore_hdmf_attrs=True)

    def test_basic_container(self):
        """Test that exporting a written container, passing in the container arg, works."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile)

        self.assertTrue(os.path.exists(self.store_path[1]))
        self.assertEqual(os.path.relpath(foofile.container_source), self.store_path[0])

        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            self.assertEqual(os.path.relpath(read_foofile.container_source), self.store_path[1])
            self.assertContainerEqual(foofile, read_foofile, ignore_hdmf_attrs=True)

    def test_container_part(self):
        """Test that exporting a part of a written container raises an error."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                msg = (
                    "The provided container must be the root of the hierarchy of the source used to read the "
                    "container."
                )
                with self.assertRaisesWith(ValueError, msg):
                    export_io.export(src_io=read_io, container=read_foofile.buckets["bucket1"])

    def test_container_unknown(self):
        """Test that exporting a container that did not come from the src_io object raises an error."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                dummy_file = FooFile(buckets=[])
                msg = "The provided container must have been read by the provided src_io."
                with self.assertRaisesWith(ValueError, msg):
                    export_io.export(src_io=read_io, container=dummy_file)

    def test_cache_spec_disabled(self):
        """Test that exporting with cache_spec disabled works."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile, cache_spec=False)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile, cache_spec=False)
        self.assertFalse(os.path.exists(os.path.join(self.store_path[1], "specifications")))

    def test_cache_spec_enabled(self):
        """Test that exporting with cache_spec works."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile, cache_spec=True)

        with zarr.open(self.store_path[1], mode="r") as zarr_io:
            self.assertTrue("specifications" in zarr_io.keys())

    def test_soft_link_group(self):
        """
        Test that exporting a written file with soft linked groups keeps links within the file." ,i.e, we have
        a group that links to a group in the same file and the new file after export should then have a link to the
        same group but in the new file"""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket], foo_link=foo1)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io)
        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()
            if isinstance(self.store_path[1], str):
                self.assertEqual(os.path.relpath(read_foofile2.foo_link.container_source), self.store_path[1])
            else:
                self.assertEqual(read_foofile2.foo_link.container_source, self.store_path[1].path)

    def test_external_link_group(self):
        """Test that exporting a written file with external linked groups maintains the links."""
        """External links remain"""

        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])
        # Create File 1 with the full data
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as read_io:
            read_io.write(foofile)
        # Create file 2 with an external link to File 1
        manager = get_foo_buildmanager()
        with ZarrIO(self.store_path[0], manager=manager, mode="r") as read_io:
            read_foofile = read_io.read()
            # make external link to existing group
            foofile2 = FooFile(foo_link=read_foofile.buckets["bucket1"].foos["foo1"])
            with ZarrIO(self.store_path[1], manager=manager, mode="w") as write_io:
                write_io.write(foofile2)
        # Export File 2 to a new File 3 and make sure the external link from File 2 is being preserved
        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            with ZarrIO(self.store_path[2], mode="w") as export_io:
                export_io.export(src_io=read_io)
        with ZarrIO(self.store_path[2], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()
            # make sure the linked group is read from the first file
            if isinstance(self.store_path[0], str):
                self.assertEqual(os.path.relpath(read_foofile2.foo_link.container_source), self.store_path[0])
            else:
                self.assertEqual(read_foofile2.foo_link.container_source, self.store_path[0].path)

    def test_external_link_dataset(self):
        """Test that exporting a written file with external linked datasets maintains the links."""
        ####################
        # Create File1
        ####################
        manager = get_foo_buildmanager()

        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=manager, mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=manager, mode="r") as read_io1:
            read_foofile1 = read_io1.read()

            ####################
            # Create File2
            ####################
            foofile2 = FooFile(buckets=[])

            # create a foo with link to existing dataset my_data (not in same file), add the foo to new foobucket
            # this should make an external link within the exported file
            foo2 = Foo("foo2", read_foofile1.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
            foobucket2 = FooBucket("bucket2", [foo2])
            foofile2.add_bucket(foobucket2)

            # also add link from foofile to new foo2.my_data dataset which is a link to foo1.my_data dataset
            # this should make an external link within the exported file
            foofile2.foofile_data = foo2.my_data

            with ZarrIO(self.store_path[1], manager=manager, mode="w") as write_io:
                write_io.write(foofile2)

        ####################
        # Export with File3
        ####################
        with ZarrIO(self.store_path[1], manager=manager, mode="r") as read_io2:
            read_foofile2 = read_io2.read()

            # create a foo with link to existing dataset my_data (not in same file), add the foo to new foobucket
            # this should make an external link within the exported file
            foo2 = Foo("foo2", read_foofile1.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
            foobucket2 = FooBucket("bucket2", [foo2])
            read_foofile2.add_bucket(foobucket2)

            with ZarrIO(self.store_path[2], mode="w") as export_io:
                export_io.export(src_io=read_io2, container=read_foofile2)

        with ZarrIO(self.store_path[2], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()
            # make sure the linked dataset is read from the first file
            self.assertEqual(os.path.relpath(read_foofile2.foofile_data.store.store.path), self.store_path[0])

    def test_external_link_link(self):
        """Test that exporting a written file with external links to external links maintains the links."""
        pass  # TODO this test currently fails
        """
        foo1 = Foo('foo1', [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket('bucket1', [foo1])
        foofile = FooFile(buckets=[foobucket])
        with ZarrIO(self.store_paths[0], manager=get_foo_buildmanager(), mode='w') as write_io:
            write_io.write(foofile)
        manager = get_foo_buildmanager()
        with ZarrIO(self.store_paths[0], manager=manager, mode='r') as read_io:
            read_foofile = read_io.read()
            # make external link to existing group
            foofile2 = FooFile(foo_link=read_foofile.buckets['bucket1'].foos['foo1'])
            with ZarrIO(self.store_paths[1], manager=manager, mode='w') as write_io:
                write_io.write(foofile2)
        manager = get_foo_buildmanager()
        with ZarrIO(self.store_paths[1], manager=manager, mode='r') as read_io:
            read_foofile2 = read_io.read()
            # make external link to external link
            foofile3 = FooFile(foo_link=read_foofile2.foo_link)
            with ZarrIO(self.store_paths[2], manager=manager, mode='w') as write_io:
                write_io.write(foofile3)
        with ZarrIO(self.store_paths[2], manager=get_foo_buildmanager(), mode='r') as read_io:
            with ZarrIO(self.store_paths[3], mode='w') as export_io:
                export_io.export(src_io=read_io)
        with ZarrIO(self.store_paths[3], manager=get_foo_buildmanager(), mode='r') as read_io:
            read_foofile3 = read_io.read()
            # make sure the linked group is read from the first file
            self.assertEqual(read_foofile3.foo_link.container_source, self.source_paths[0])
        """

    def test_attr_reference(self):
        """Test that exporting a written file with attribute references maintains the references."""
        """Attribute with object reference needs to point to the new object in the new file"""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket], foo_ref_attr=foo1)
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as read_io:
            read_io.write(foofile)
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                # export_io.export(src_io=read_io, container=read_foofile2, write_args={'link_data': False})
                export_io.export(src_io=read_io)
        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()
            expected = ZarrIO.get_zarr_paths(read_foofile2.foo_ref_attr.my_data)
            if isinstance(self.store_path[1], str):
                self.assertTupleEqual(
                    (os.path.normpath(expected[0]), os.path.normpath(expected[1])),
                    (
                        os.path.normpath(os.path.abspath(self.store_path[1])),
                        os.path.normpath("/buckets/bucket1/foo_holder/foo1/my_data"),
                    ),
                )
            else:
                self.assertTupleEqual(
                    (os.path.normpath(expected[0]), os.path.normpath(expected[1])),
                    (
                        os.path.normpath(os.path.abspath(self.store_path[1].path)),
                        os.path.normpath("/buckets/bucket1/foo_holder/foo1/my_data"),
                    ),
                )
            # make sure the attribute reference resolves to the container within the same file
            self.assertIs(read_foofile2.foo_ref_attr, read_foofile2.buckets["bucket1"].foos["foo1"])

    def test_pop_data(self):
        """Test that exporting a written container after removing an element from it works."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            read_foofile.remove_bucket("bucket1")  # remove child group

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile)

        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()

            # make sure the read foofile has no buckets
            self.assertDictEqual(read_foofile2.buckets, {})

        # check that file size of file 2 is smaller
        dirsize1 = total_size(self.store_path[0])
        dirsize2 = total_size(self.store_path[1])
        self.assertTrue(dirsize1 > dirsize2)

    def test_pop_linked_group(self):
        """Test that exporting a written container after removing a linked element from it works."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket], foo_link=foo1)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()
            read_foofile.buckets["bucket1"].remove_foo("foo1")  # remove child group

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                msg = (
                    "links (links): Linked Foo 'foo1' has no parent. Remove the link or ensure the linked "
                    "container is added properly."
                )
                with self.assertRaisesWith(OrphanContainerBuildError, msg):
                    export_io.export(src_io=read_io, container=read_foofile)

    def test_soft_link_data(self):
        """
        Test data soft links.
        """
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()

            # create a foo with link to existing dataset my_data, add the foo to new foobucket
            # this should make a soft link within the exported file
            foo2 = Foo("foo2", read_foofile.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
            foobucket2 = FooBucket("bucket2", [foo2])
            read_foofile.add_bucket(foobucket2)

            read_foofile.foofile_data = foo2.my_data

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile)

        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()

            # test new soft link to dataset in file
            self.assertIs(
                read_foofile2.buckets["bucket1"].foos["foo1"].my_data,
                read_foofile2.buckets["bucket2"].foos["foo2"].my_data,
            )

            # test new soft link to new soft link to dataset in file
            self.assertIs(read_foofile2.buckets["bucket1"].foos["foo1"].my_data, read_foofile2.foofile_data)

    def test_soft_links_group_after_write(self):
        """
        Test that exporting a written container after adding
        groups, links, and references to it works.
        """
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile = read_io.read()

            # create a foo with link to existing dataset my_data, add the foo to new foobucket
            # this should make a soft link within the exported file
            foo2 = Foo("foo2", read_foofile.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
            foobucket2 = FooBucket("bucket2", [foo2])
            read_foofile.add_bucket(foobucket2)

            # also add link from foofile to new foo2 container
            read_foofile.foo_link = foo2

            # also add reference from foofile to new foo2
            read_foofile.foo_ref_attr = foo2

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_foofile)

        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="r") as read_io:
            read_foofile2 = read_io.read()

            # test new soft link to group in file
            self.assertIs(read_foofile2.foo_link, read_foofile2.buckets["bucket2"].foos["foo2"])

            # test new attribute reference to new group in file
            self.assertIs(read_foofile2.foo_ref_attr, read_foofile2.buckets["bucket2"].foos["foo2"])

    def test_append_external_link_data(self):
        """Test that exporting a written container after adding a link with link_data=True creates external links."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)
        foofile2 = FooFile(buckets=[])
        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile2)
        manager = get_foo_buildmanager()
        with ZarrIO(self.store_path[0], manager=manager, mode="r") as read_io1:
            read_foofile1 = read_io1.read()
            with ZarrIO(self.store_path[1], manager=manager, mode="r") as read_io2:
                read_foofile2 = read_io2.read()
                # create a foo with link to existing dataset my_data (not in same file), add the foo to new foobucket
                # this should make an external link within the exported file
                foo2 = Foo("foo2", read_foofile1.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
                foobucket2 = FooBucket("bucket2", [foo2])
                read_foofile2.add_bucket(foobucket2)
                # also add link from foofile to new foo2.my_data dataset which is a link to foo1.my_data dataset
                # this should make an external link within the exported file
                read_foofile2.foofile_data = foo2.my_data
                with ZarrIO(self.store_path[2], mode="w") as export_io:
                    export_io.export(src_io=read_io2, container=read_foofile2)
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io1:
            read_foofile3 = read_io1.read()
            with ZarrIO(self.store_path[2], manager=get_foo_buildmanager(), mode="r") as read_io2:
                read_foofile4 = read_io2.read()
                self.assertEqual(
                    read_foofile4.buckets["bucket2"].foos["foo2"].my_data,
                    read_foofile3.buckets["bucket1"].foos["foo1"].my_data,
                )
                self.assertEqual(read_foofile4.foofile_data, read_foofile3.buckets["bucket1"].foos["foo1"].my_data)

    def test_append_external_link_copy_data(self):
        """Test that exporting a written container after adding a link with link_data=False copies the data."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)
        foofile2 = FooFile(buckets=[])
        with ZarrIO(self.store_path[1], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile2)
        manager = get_foo_buildmanager()
        with ZarrIO(self.store_path[0], manager=manager, mode="r") as read_io1:
            read_foofile1 = read_io1.read()
            with ZarrIO(self.store_path[1], manager=manager, mode="r") as read_io2:
                read_foofile2 = read_io2.read()
                # create a foo with link to existing dataset my_data (not in same file), add the foo to new foobucket
                # this would normally make an external link but because link_data=False, data will be copied
                foo2 = Foo("foo2", read_foofile1.buckets["bucket1"].foos["foo1"].my_data, "I am foo2", 17, 3.14)
                foobucket2 = FooBucket("bucket2", [foo2])
                read_foofile2.add_bucket(foobucket2)
                # also add link from foofile to new foo2.my_data dataset which is a link to foo1.my_data dataset
                # this would normally make an external link but because link_data=False, data will be copied
                read_foofile2.foofile_data = foo2.my_data
                with ZarrIO(self.store_path[2], mode="w") as export_io:
                    export_io.export(src_io=read_io2, container=read_foofile2, write_args={"link_data": False})
        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="r") as read_io1:
            read_foofile3 = read_io1.read()
            with ZarrIO(self.store_path[2], manager=get_foo_buildmanager(), mode="r") as read_io2:
                read_foofile4 = read_io2.read()
                # check that file can be read
                self.assertNotEqual(
                    read_foofile4.buckets["bucket2"].foos["foo2"].my_data,
                    read_foofile3.buckets["bucket1"].foos["foo1"].my_data,
                )
                self.assertNotEqual(read_foofile4.foofile_data, read_foofile3.buckets["bucket1"].foos["foo1"].my_data)
                self.assertNotEqual(read_foofile4.foofile_data, read_foofile4.buckets["bucket2"].foos["foo2"].my_data)

    def test_export_dset_refs(self):
        """Test that exporting a written container with a dataset of references works."""
        num_bazs = 1
        bazs = []  # set up dataset of references
        for i in range(num_bazs):
            bazs.append(Baz(name="baz%d" % i))
        baz_data = BazData(name="baz_data", data=bazs)
        container = BazBucket(bazs=bazs, baz_data=baz_data)
        manager = get_baz_buildmanager()

        with ZarrIO(self.store_path[0], manager=manager, mode="w") as writer:
            writer.write(container=container)

        with ZarrIO(self.store_path[0], manager=manager, mode="r") as read_io:
            read_container = read_io.read()

            with ZarrIO(self.store_path[1], mode="w") as export_io:
                export_io.export(src_io=read_io, container=read_container)

        with ZarrIO(self.store_path[1], manager=manager, mode="r") as read_io2:
            read_container = read_io2.read()
            self.assertEqual(len(read_container.baz_data.data), 1)
            self.assertContainerEqual(container, read_container, ignore_name=True, ignore_hdmf_attrs=True)
            for i in range(num_bazs):
                baz_name = "baz%d" % i
                self.assertIs(read_container.baz_data.data[i], read_container.bazs[baz_name])

    # def test_export_cpd_dset_refs(self):
    #     """Test that exporting a written container with a compound dataset with references works."""
    #     bazs = []
    #     baz_pairs = []
    #     num_bazs = 10
    #     for i in range(num_bazs):
    #         b = Baz(name='baz%d' % i)
    #         bazs.append(b)
    #         baz_pairs.append((i, b))
    #     baz_cpd_data = BazCpdData(name='baz_cpd_data1', data=baz_pairs)
    #     bucket = BazBucket(name='bucket1', bazs=bazs.copy(), baz_cpd_data=baz_cpd_data)
    #     with ZarrIO(self.store_path[0], manager=get_baz_buildmanager(), mode='w') as write_io:
    #         write_io.write(bucket)
    #     with ZarrIO(self.store_path[0], manager=get_baz_buildmanager(), mode='r') as read_io:
    #         read_bucket1 = read_io.read()
    #         # NOTE: reference IDs might be the same between two identical files
    #         # adding a Baz with a smaller name should change the reference IDs on export
    #         with ZarrIO(self.store_path[1], mode='w') as export_io:
    #             export_io.export(src_io=read_io, container=read_bucket1)
    #     with ZarrIO(self.store_paths[1], manager=get_baz_buildmanager(), mode='r') as read_io:
    #         read_bucket2 = read_io.read()
    #         # remove and check the appended child, then compare the read container with the original
    #         read_new_baz = read_bucket2.remove_baz(new_baz.name)
    #         self.assertContainerEqual(new_baz, read_new_baz, ignore_hdmf_attrs=True)
    #         self.assertContainerEqual(bucket, read_bucket2, ignore_name=True, ignore_hdmf_attrs=True)
    #         for i in range(num_bazs):
    #             baz_name = 'baz%d' % i
    #             self.assertEqual(read_bucket2.baz_cpd_data.data[i][0], i)
    #             self.assertIs(read_bucket2.baz_cpd_data.data[i][1], read_bucket2.bazs[baz_name])

    def test_non_manager_container(self):
        """Test that exporting with a src_io without a manager raises an error."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        class OtherIO(HDMFIO):

            @staticmethod
            def can_read(path):
                pass

            def read_builder(self):
                pass

            def write_builder(self, **kwargs):
                pass

            def open(self):
                pass

            def close(self):
                pass

        with OtherIO() as read_io:
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                msg = "When a container is provided, src_io must have a non-None manager (BuildManager) property."
                with self.assertRaisesWith(ValueError, msg):
                    export_io.export(src_io=read_io, container=foofile, write_args={"link_data": False})

    def test_non_Zarr_src_link_data_true(self):
        """Test that exporting with a src_io without a manager raises an error."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        class OtherIO(HDMFIO):

            def __init__(self, manager):
                super().__init__(manager=manager)

            @staticmethod
            def can_read(path):
                pass

            def read_builder(self):
                pass

            def write_builder(self, **kwargs):
                pass

            def open(self):
                pass

            def close(self):
                pass

        with OtherIO(manager=get_foo_buildmanager()) as read_io:
            with ZarrIO(self.store_path[1], mode="w") as export_io:
                msg = (
                    "Cannot export from non-Zarr backend OtherIO to Zarr with write argument link_data=True. "
                    "Set write_args={'link_data': False}"
                )
                with self.assertRaisesWith(UnsupportedOperation, msg):
                    export_io.export(src_io=read_io, container=foofile)

    def test_wrong_mode(self):
        """Test that exporting with a src_io without a manager raises an error."""
        foo1 = Foo("foo1", [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
        foobucket = FooBucket("bucket1", [foo1])
        foofile = FooFile(buckets=[foobucket])

        with ZarrIO(self.store_path[0], manager=get_foo_buildmanager(), mode="w") as write_io:
            write_io.write(foofile)

        with ZarrIO(self.store_path[0], mode="r") as read_io:
            with ZarrIO(self.store_path[1], mode="a") as export_io:
                with self.assertRaises(UnsupportedOperation):
                    export_io.export(src_io=read_io)
