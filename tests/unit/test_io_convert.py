"""
Module for testing conversion of data between different I/O backends
To reduce the amount of code needed, the tests use a series of mixin classes to
construct a test case:

- ``MixinTestCaseConvert`` is the base mixin class for conversion tests and
  requires that the ``setUpContainer`` and ``roundtripExportContainer`` functions
  are defined. The setUpContainer defines the container (and hence the problem case)
  to be written to file. And the roundtripExportContainer defined the process
  for writing, exporting, and then reading the container again.
- ``TestXYZContainerMixin`` classes define the ``setUpContainer`` function
- ``TestX1toX2Mixin`` defines the ``roundtripExportContainer`` process
- ``TestCase`` is the base test class for HDMF

A test case is then constructed by defining a class that inherits from the
corresponding (usually 4) base classes:

1. a mixin that define ``setUpContainer``,
2. a mixin that define ``roundtripExportContainer``,
3. ``MixinTestCaseConvert``, and
4. TestCase.

I.e., even though a particular test class may look empty, it is the combination
of the mixin classes that creates the particular test problem. Many of the Mixin
classes also define additional class variables to allow child classes to further
customize the behavior of the mixin.

.. note::

    The mixin classes should not be instantiated or class variables be modified
    directly as the individual mixin classes only define partial behavior and
    modifying the behavior in the mixin will affect all downstream tests.
    Mixin classes should always be used through inheritance.
"""
import os
import shutil
import numpy as np
from abc import ABCMeta, abstractmethod

from hdmf_zarr.backend import (ZarrIO,
                               ROOT_NAME)

from hdmf.backends.hdf5 import HDF5IO
from hdmf.common import get_manager as get_hdmfcommon_manager
from hdmf.testing import TestCase
from hdmf.common import DynamicTable
from hdmf.common import CSRMatrix
from tests.unit.utils import (Foo,
                              FooBucket,
                              FooFile,
                              get_foo_buildmanager)

from zarr.storage import (DirectoryStore,
                          TempStore,
                          NestedDirectoryStore)


class MixinTestCaseConvert(metaclass=ABCMeta):
    """
    Mixin class used to define the basic structure for a conversion test.

    To implement a test case using this mixin we need to implement the abstract methods
    ``setUpContainer`` and ``roundtripExportContainer``. The behavior of the mixin can
    then be further customized via the class variables: IGNORE_NAME, IGNORE_HDMF_ATTRS,
    IGNORE_STRING_TO_BYTE, WRITE_PATHS, EXPORT_PATHS.

    """
    IGNORE_NAME = False
    """
    Bool parameter passed to assertContainerEqual (False)
    """

    IGNORE_HDMF_ATTRS = False
    """
    Bool parameter passed to assertContainerEqual (False)
    """

    IGNORE_STRING_TO_BYTE = False
    """
    Bool parameter passed to assertContainerEqual (False)
    """

    WRITE_PATHS = [None, ]
    """
    List of paths to which to write files to as part of ``test_export_roundtrip``,
    which passes the values to ``roundtripContainer``. The specific definition
    of the individual paths depends on the backend used for writing in ``roundtripContainer``.
    E.g., if :py:class:`~hdmf.backends.h5tools.HDF5IO` is used then the paths must be strings,
    and when :py:class:`~hdmf_zarr.backend.ZarrIO` is used then paths may be strings or
    supported ``zarr.storage`` backend objects, e.g., a ``zarr.storage.DirectoryStore``.
    A value of None as part of list means to use the default filename for write.
    (Default=[None, ])
    """

    EXPORT_PATHS = [None, ]
    """
    List of paths to which to export files to as part of ``test_export_roundtrip``,
    which passes the values to ``roundtripContainer``. The specific definition
    of the individual paths depends on the backend used for writing in ``roundtripContainer``.
    E.g., if :py:class:`~hdmf.backends.h5tools.HDF5IO` is used then the paths must be strings,
    and when :py:class:`~hdmf_zarr.backend.ZarrIO` is used then paths may be strings or
    supported ``zarr.storage`` backend objects, e.g., a ``zarr.storage.DirectoryStore``.
    A value of None as part of list means to use the default filename for export.
    (Default=[None, ])
    """

    def get_manager(self):
        raise NotImplementedError('Cannot run test unless get_manger  is implemented')

    def setUp(self):
        self.__manager = self.get_manager()
        self.filenames = []
        self.ios = []

    def tearDown(self):
        self.close_files_and_ios()

    def close_files_and_ios(self):
        for io in self.ios:
            if io is not None:
                io.close()
        for fn in self.filenames:
            if fn is not None and os.path.exists(fn):
                if os.path.isdir(fn):
                    shutil.rmtree(fn)
                else:
                    os.remove(fn)
        self.filenames = []
        self.ios = []

    @abstractmethod
    def setUpContainer(self):
        """Return the Container to read/write."""
        raise NotImplementedError('Cannot run test unless setUpContainer is implemented')

    @abstractmethod
    def roundtripExportContainer(self, container, write_path, export_path):
        """
        1. Write the container to write_path
        2. Export the file from write_path to export_path using a new backend
        3. Read the exported container export_path from disk
        4. Return the container read in 3 so that it can be compared with the original
        Any HDMFIO backends that should remain open MUST be added to the self.io list
        so that they can be closed by close_files_and_ios (e.g., on tearDown),
        """
        raise NotImplementedError('Cannot run test unless roundtripExportContainer  is implemented')

    def test_export_roundtrip(self):
        """Test that roundtripping the container works"""
        # determine and save the write and export paths
        for write_path in self.WRITE_PATHS:
            for export_path in self.EXPORT_PATHS:
                container = self.setUpContainer()
                container_type = container.__class__.__name__
                if write_path is None:
                    write_path = 'test_%s.hdmf' % container_type
                if export_path is None:
                    export_path = 'test_export_%s.hdmf' % container_type
                self.filenames.append(write_path if isinstance(write_path, str) else write_path.path)
                self.filenames.append(export_path if isinstance(export_path, str) else export_path.path)
                # roundtrip the container
                exported_container = self.roundtripExportContainer(
                    container=container,
                    write_path=write_path,
                    export_path=export_path)
                # assert that the roundtrip worked correctly
                message = "Using: write_path=%s, export_path=%s" % (str(write_path), str(export_path))
                self.assertIsNotNone(str(container), message)  # added as a test to make sure printing works
                self.assertIsNotNone(str(exported_container), message)
                # make sure we get a completely new object
                self.assertNotEqual(id(container), id(exported_container), message)
                # the name of the root container of a file is always 'root' (see h5tools.py ROOT_NAME)
                # thus, ignore the name of the container when comparing original container vs read container
                self.assertContainerEqual(container,
                                          exported_container,
                                          ignore_name=self.IGNORE_NAME,
                                          ignore_hdmf_attrs=self.IGNORE_HDMF_ATTRS,
                                          ignore_string_to_byte=self.IGNORE_STRING_TO_BYTE,
                                          message=message)
                self.close_files_and_ios()
                # TODO: May need to add further asserts here


##########################################################
# Mixins for tesing export between different backend IO
#########################################################
class MixinTestHDF5ToZarr():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests from HDF5 to Zarr.
    This class only defines the roundtripExportContainer and get_manager functions for the test.
    The setUpContainer function required for the test needs to be defined separately
    (e.g., by another mixin or the test class itself).
    """
    WRITE_PATHS = [None, ]
    EXPORT_PATHS = [None,
                    DirectoryStore('test_export_DirectoryStore.zarr'),
                    TempStore(),
                    NestedDirectoryStore('test_export_NestedDirectoryStore.zarr')]

    def get_manager(self):
        return get_hdmfcommon_manager()

    def roundtripExportContainer(self, container, write_path, export_path):
        with HDF5IO(write_path, manager=self.get_manager(), mode='w') as write_io:
            write_io.write(container, cache_spec=True)

        with HDF5IO(write_path, manager=self.get_manager(), mode='r') as read_io:
            with ZarrIO(export_path, mode='w') as export_io:
                export_io.export(src_io=read_io, write_args={'link_data': False})

        read_io = ZarrIO(export_path, manager=self.get_manager(), mode='r')
        self.ios.append(read_io)
        exportContainer = read_io.read()
        return exportContainer


class MixinTestZarrToHDF5():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests from Zarr to HDF5.
    This class only defines the roundtripExportContainer and get_manager functions for the test.
    The setUpContainer function required for the test needs to be defined separately
    (e.g., by another mixin or the test class itself)
    """
    WRITE_PATHS = [None,
                   DirectoryStore('test_export_DirectoryStore.zarr'),
                   TempStore(),
                   NestedDirectoryStore('test_export_NestedDirectoryStore.zarr')]
    EXPORT_PATHS = [None, ]

    def get_manager(self):
        return get_hdmfcommon_manager()

    def roundtripExportContainer(self, container,  write_path, export_path):
        with ZarrIO(write_path, manager=self.get_manager(), mode='w') as write_io:
            write_io.write(container, cache_spec=True)

        with ZarrIO(write_path, manager=self.get_manager(), mode='r') as read_io:
            with HDF5IO(export_path,  mode='w') as export_io:
                export_io.export(src_io=read_io, write_args={'link_data': False})

        read_io = HDF5IO(export_path, manager=self.get_manager(), mode='r')
        self.ios.append(read_io)
        exportContainer = read_io.read()
        return exportContainer


class MixinTestZarrToZarr():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests from Zarr to Zarr.
    This class only defines the roundtripExportContainer and get_manager functions for the test.
    The setUpContainer function required for the test needs to be defined separately
    (e.g., by another mixin or the test class itself)
    """
    WRITE_PATHS = [None,
                   DirectoryStore('test_export_DirectoryStore_Source.zarr'),
                   TempStore(dir=os.path.dirname(__file__)),  # set dir to avoid switching drives on Windows
                   NestedDirectoryStore('test_export_NestedDirectoryStore_Source.zarr')]
    EXPORT_PATHS = [None,
                    DirectoryStore('test_export_DirectoryStore_Export.zarr'),
                    TempStore(dir=os.path.dirname(__file__)),   # set dir to avoid switching drives on Windows
                    NestedDirectoryStore('test_export_NestedDirectoryStore_Export.zarr')]

    def get_manager(self):
        return get_hdmfcommon_manager()

    def roundtripExportContainer(self, container,  write_path, export_path):
        with ZarrIO(write_path, manager=self.get_manager(), mode='w') as write_io:
            write_io.write(container, cache_spec=True)

        with ZarrIO(write_path, manager=self.get_manager(), mode='r') as read_io:
            with ZarrIO(export_path,  mode='w') as export_io:
                export_io.export(src_io=read_io, write_args={'link_data': False})

        read_io = ZarrIO(export_path, manager=self.get_manager(), mode='r')
        self.ios.append(read_io)
        exportContainer = read_io.read()
        return exportContainer


############################################
# HDMF Common test container mixins
###########################################
class MixinTestDynamicTableContainer():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests that
    test export of DynamicTable container classes. This class only defines the setUpContainer function for the test.
    The roundtripExportContainer function required for the test needs to be defined separately
    (e.g., by another mixin or the test class itself)
    This mixin adds the class variable, ``TABLE_TYPE``  which is an int to select between different
    container types for testing:

    * ``TABLE_TYPE=0`` : Table of int, float, bool, Enum
    * ``TABLE_TYPE=1`` : Table of int, float, str, bool, Enum
    """
    TABLE_TYPE = 0

    def setUpContainer(self):
        # TODO: The tables are named "root" because otherwise the Zarr backend does not determine the path correctly
        if self.TABLE_TYPE == 0:
            table = DynamicTable(name=ROOT_NAME,
                                 description='an example table')
            table.add_column('foo', 'an int column')
            table.add_column('bar', 'a float column')
            table.add_column('qux', 'a boolean column')
            table.add_column('quux', 'a enum column', enum=True, index=False)
            table.add_row(foo=27, bar=28.0, qux=True, quux='a')
            table.add_row(foo=37, bar=38.0, qux=False, quux='b')
            return table
        elif self.TABLE_TYPE == 1:
            table = DynamicTable(name=ROOT_NAME,
                                 description='an example table')
            table.add_column('foo', 'an int column')
            table.add_column('bar', 'a float column')
            table.add_column('baz', 'a string column')
            table.add_column('qux', 'a boolean column')
            table.add_column('quux', 'a enum column', enum=True, index=False)
            table.add_row(foo=27, bar=28.0, baz="cat", qux=True, quux='a')
            table.add_row(foo=37, bar=38.0, baz="dog", qux=False, quux='b')
            return table
        else:
            raise NotImplementedError("TABLE_TYPE %i not implemented in test" % self.TABLE_TYPE)


class MixinTestCSRMatrix():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests that
    test export of CSRMatrix container classes. This class only defines the setUpContainer function for the test.
    The roundtripExportContainer function required for the test needs to be defined separately
    (e.g., by another mixin or the test class itself)
    """

    def setUpContainer(self):
        data = np.array([1, 2, 3, 4, 5, 6])
        indices = np.array([0, 2, 2, 0, 1, 2])
        indptr = np.array([0, 2, 3, 6])
        return CSRMatrix(data=data,
                         indices=indices,
                         indptr=indptr,
                         shape=(3, 3))


#########################################
# HDMF Foo test container test harness
#########################################
class MixinTestFoo():
    """
    Mixin class used in conjunction with MixinTestCaseConvert to create conversion tests that
    test export of a variety of Foo container classes. This class only defines the setUpContainer
    and get_manager functions. The roundtripExportContainer function required for
    the test needs to be defined separately, e.g., by another mixin for Foo test cases, e.g.,
    MixinTestZarrToHDF5,  MixinTestHDF5ToZarr, or MixinTestZarrToZarr
    This mixin adds the class variable, FOO_TYPE  which is an int to select between different
    container types for testing:

    * ``FOO_TYPE=0`` : File with two Foo buckets storing integer datasets
    * ``FOO_TYPE=1`` : File with one Foo buckets storing integer dataset and a SoftLink to it
    """
    FOO_TYPE = 0
    FOO_TYPES = {'int_data': 0,
                 'link_data': 1,
                 'str_data': 2}

    def get_manager(self):
        return get_foo_buildmanager()

    def setUpContainer(self):
        if self.FOO_TYPE == 0:
            foo1 = Foo('foo1', [0, 1, 2, 3, 4], "I am foo1", 17, 3.14)
            foo2 = Foo('foo2', [5, 6, 7, 8, 9], "I am foo2", 34, 6.28)
            foobucket = FooBucket('bucket1', [foo1, foo2])
            foofile = FooFile(buckets=[foobucket])
            return foofile
        elif self.FOO_TYPE == 1:
            foo1 = Foo('foo1', [1, 2, 3, 4, 5], "I am foo1", 17, 3.14)
            foobucket = FooBucket('bucket1', [foo1])
            foofile = FooFile(buckets=[foobucket], foo_link=foo1)  # create soft link
            return foofile
        else:
            raise NotImplementedError("FOO_TYPE %i not implemented in test" % self.FOO_TYPE)


########################################
# Actual test cases for conversion
########################################
class TestHDF5ToZarrDynamicTableC0(MixinTestDynamicTableContainer,
                                   MixinTestHDF5ToZarr,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from HDF5 to Zarr.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    TABLE_TYPE = 0

    def test_simple(self, write_path=None, export_path=None):
        print(write_path, export_path)


class TestZarrToHDF5DynamicTableC0(MixinTestDynamicTableContainer,
                                   MixinTestZarrToHDF5,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from Zarr to HDF5.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    TABLE_TYPE = 0


class TestZarrToZarrDynamicTableC0(MixinTestDynamicTableContainer,
                                   MixinTestZarrToZarr,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from Zarr to HDF5.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    TABLE_TYPE = 0


class TestHDF5ToZarrDynamicTableC1(MixinTestDynamicTableContainer,
                                   MixinTestHDF5ToZarr,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from HDF5 to Zarr.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    TABLE_TYPE = 1


class TestZarrToHDF5DynamicTableC1(MixinTestDynamicTableContainer,
                                   MixinTestZarrToHDF5,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from Zarr to HDF5.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True   # Need to ignore conversion of strings to bytes
    TABLE_TYPE = 1


class TestZarrToZarrDynamicTableC1(MixinTestDynamicTableContainer,
                                   MixinTestZarrToZarr,
                                   MixinTestCaseConvert,
                                   TestCase):
    """
    Test the conversion of DynamicTable containers from Zarr to HDF5.
    See MixinTestDynamicTableContainer.setUpContainer for the container spec.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True   # Need to ignore conversion of strings to bytes
    TABLE_TYPE = 1


class TestHDF5ToZarrCSRMatrix(MixinTestCSRMatrix,
                              MixinTestHDF5ToZarr,
                              MixinTestCaseConvert,
                              TestCase):
    """
    Test the conversion of CSRMatrix containers from HDF5 to Zarr.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False


class TestZarrToHDF5CSRMatrix(MixinTestCSRMatrix,
                              MixinTestZarrToHDF5,
                              MixinTestCaseConvert,
                              TestCase):
    """
    Test the conversion of CSRMatrix containers from Zarr to HDF5.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False


class TestZarrToZarrCSRMatrix(MixinTestCSRMatrix,
                              MixinTestZarrToZarr,
                              MixinTestCaseConvert,
                              TestCase):
    """
    Test the conversion of CSRMatrix containers from Zarr to HDF5.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False


class TestZarrToHDF5FooCase1(MixinTestFoo,
                             MixinTestZarrToHDF5,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['int_data']


class TestZarrToZarrFooCase1(MixinTestFoo,
                             MixinTestZarrToZarr,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['int_data']


class TestHDF5toZarrFooCase1(MixinTestFoo,
                             MixinTestHDF5ToZarr,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['int_data']


class TestZarrToHDF5FooCase2(MixinTestFoo,
                             MixinTestZarrToHDF5,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['link_data']


class TestZarrToZarrFooCase2(MixinTestFoo,
                             MixinTestZarrToZarr,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['link_data']


class TestHDF5toZarrFooCase2(MixinTestFoo,
                             MixinTestHDF5ToZarr,
                             MixinTestCaseConvert,
                             TestCase):
    """
    Test the conversion of a simple Foo container with two buckets of datasets from Zarr to HDF5
    See MixinTestFoo.setUpContainer for the container spec used.
    """
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = True
    FOO_TYPE = MixinTestFoo.FOO_TYPES['link_data']


# TODO: Fails because we need to copy the data from the ExternalLink as it points to a non-Zarr source
"""
class TestFooExternalLinkHDF5ToZarr(MixinTestCaseConvert, TestCase):
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    def get_manager(self):
        return get_foo_buildmanager()
    def setUpContainer(self):
        # Create the first file container. We will overwrite this later with the external link container
        foo1 = Foo('foo1', [0, 1, 2, 3, 4], "I am foo1", 17, 3.14)
        bucket1 = FooBucket('bucket1', [foo1])
        foofile1 = FooFile(buckets=[bucket1])
        return foofile1
    def roundtripExportContainer(self):
        # Write the HDF5 file
        first_filename = 'test_firstfile_%s.hdmf' % self.container_type
        self.filenames.append(first_filename)
        with HDF5IO(first_filename, manager=self.get_manager(), mode='w') as write_io:
            write_io.write(self.container, cache_spec=True)
        # Create the second file with an external link added (which is the file we use as reference_
        with HDF5IO(first_filename, manager=self.get_manager(), mode='r') as read_io:
            read_foo = read_io.read()
            foo2 = Foo('foo2', read_foo.buckets['bucket1'].foos['foo1'].my_data, "I am foo2", 34, 6.28)
            bucket2 = FooBucket('bucket2', [foo2])
            foofile2 = FooFile(buckets=[bucket2])
            self.container = foofile2  # This is what we need to compare against
            with HDF5IO(self.filename, manager=self.get_manager(), mode='w') as write_io:
                write_io.write(foofile2, cache_spec=True)
        # Export the file with the external link to Zarr
        with HDF5IO(self.filename, manager=self.get_manager(), mode='r') as read_io:
            with ZarrIO(self.export_filename, mode='w') as export_io:
                export_io.export(src_io=read_io, write_args={'link_data': False})
        read_io = ZarrIO(self.export_filename, manager=self.get_manager(), mode='r')
        self.ios.append(read_io)
        exportContainer = read_io.read()
        return exportContainer
"""

# TODO: Fails because ZarrIO fails to properly create the external link
"""
class TestFooExternalLinkZarrToHDF5(MixinTestCaseConvert, TestCase):
    IGNORE_NAME = True
    IGNORE_HDMF_ATTRS = True
    IGNORE_STRING_TO_BYTE = False
    def get_manager(self):
        return get_foo_buildmanager()
    def setUpContainer(self):
        # Create the first file container. We will overwrite this later with the external link container
        foo1 = Foo('foo1', [0, 1, 2, 3, 4], "I am foo1", 17, 3.14)
        bucket1 = FooBucket('bucket1', [foo1])
        foofile1 = FooFile(buckets=[bucket1])
        return foofile1
    def roundtripExportContainer(self):
        # Write the HDF5 file
        first_filename = 'test_firstfile_%s.hdmf' % self.container_type
        self.filenames.append(first_filename)
        with ZarrIO(first_filename, manager=self.get_manager(), mode='w') as write_io:
            write_io.write(self.container, cache_spec=True)
        # Create the second file with an external link added (which is the file we use as reference_
        with ZarrIO(first_filename, manager=self.get_manager(), mode='r') as read_io:
            read_foo = read_io.read()
            foo2 = Foo('foo2', read_foo.buckets['bucket1'].foos['foo1'].my_data, "I am foo2", 34, 6.28)
            bucket2 = FooBucket('bucket2', [foo2])
            foofile2 = FooFile(buckets=[bucket2])
            self.container = foofile2  # This is what we need to compare against
            with ZarrIO(self.filename, manager=self.get_manager(), mode='w') as write_io:
                write_io.write(foofile2, cache_spec=True)
        # Export the file with the external link to Zarr
        with ZarrIO(self.filename, manager=self.get_manager(), mode='r') as read_io:
            with HDF5IO(self.export_filename, mode='w') as export_io:
                export_io.export(src_io=read_io, write_args={'link_data': False})
        read_io = HDF5IO(self.export_filename, manager=self.get_manager(), mode='r')
        self.ios.append(read_io)
        exportContainer = read_io.read()
        return exportContainer
"""
