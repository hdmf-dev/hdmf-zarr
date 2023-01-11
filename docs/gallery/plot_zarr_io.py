"""
.. _zarrio_tutorial:

ZarrIO Overview
===============

The :py:class:`~hdmf_zarr.backend.ZarrIO` backend behaves in general much like the
standard :py:class:`~hdmf.backends.hdf5.HDF5IO` available with HDMF and is an
adaptation of that backend to use Zarr instead of HDF5

Create an example DynamicTable Container
----------------------------------------

As a simple example, we here create a basic :py:class:`~hdmf.common.table.DynamicTable` for
describing basic user data.

.. note::

   When writing a :py:class:`~hdmf.common.table.DynamicTable` (or any Container that is
   normally not intended to be the root of a file) we need to use :py:attr:`hdmf_zarr.backend.ROOT_NAME`
   as the name for the Container to ensure that link paths are created correctly by
   :py:class:`~hdmf_zarr.backend.ZarrIO`. This is due to the fact that the top-level Container
   used during I/O is written as the root of the file. As such, the name of the root Container
   of a file does not appear in the path to locate it.
"""
# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_zarr_io.png'

# Import DynamicTable and get the ROOT_NAME
from hdmf.common.table import DynamicTable
from hdmf_zarr.backend import ROOT_NAME

# Setup a DynamicTable for managing data about users
users_table = DynamicTable(
    name=ROOT_NAME,
    description='a table containing data/metadata about users, one user per row',
)
users_table.add_column(
    name='first_name',
    description='the first name of the user',
)
users_table.add_column(
    name='last_name',
    description='the last name of the user',
)

users_table.add_column(
    name='phone_number',
    description='the phone number of the user',
    index=True,
)

# Add some simple example data to our table
users_table.add_row(
    first_name='Grace',
    last_name='Hopper',
    phone_number=['123-456-7890']
)
users_table.add_row(
    first_name='Alan',
    last_name='Turing',
    phone_number=['555-666-7777', '888-111-2222']
)

# Show the table for validation
users_table.to_dataframe()


###############################################################################
# Writing the table to Zarr
# ---------------------------------

from hdmf.common import get_manager
from hdmf_zarr.backend import ZarrIO

zarr_dir = "example.zarr"
with ZarrIO(path=zarr_dir,  manager=get_manager(), mode='w') as zarr_io:
    zarr_io.write(users_table)

###############################################################################
# Reading the table from Zarr
# ----------------------------------
zarr_io = ZarrIO(path=zarr_dir,  manager=get_manager(), mode='r')
intable = zarr_io.read()
intable.to_dataframe()

###############################################################################
#
zarr_io.close()


###############################################################################
# Converting to/from HDF5 using ``export``
# ----------------------------------------
#
# Exporting the Zarr file to HDF5
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# To convert our Zarr file to HDF5 we can now simply read the file with our
# :py:class:`~hdmf_zarr.backend.ZarrIO` backend and the export the file
# using HDMF's :py:class:`~hdmf.backends.hdf5.HDF5IO` backend

from hdmf.backends.hdf5 import HDF5IO

with ZarrIO(path=zarr_dir,  manager=get_manager(), mode='r') as zarr_read_io:
    with HDF5IO(path="example.h5", manager=get_manager(), mode='w') as hdf5_export_io:
        hdf5_export_io.export(src_io=zarr_read_io, write_args=dict(link_data=False))  # use export!

###############################################################################
# .. note::
#
#     When converting between backends we need to set ``link_data=False`` as linking
#     between different storage backends (here from HDF5 to Zarr and vice versa) is
#     not supported.
#
# Check that the HDF5 file is correct
#
with HDF5IO(path="example.h5", manager=get_manager(), mode='r') as hdf5_read_io:
    intable_from_hdf5 = hdf5_read_io.read()
    intable_hdf5_df = intable_from_hdf5.to_dataframe()
intable_hdf5_df  # display the table in the gallery output

###############################################################################
# Exporting the HDF5 file to Zarr
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#
# In the same way as above, we can now also convert our HDF5 file back to Zarr
# simply by reading the HDF5 file using HDMF's :py:class:`~hdmf.backends.hdf5.HDF5IO` backend
# and the exporting the file using the :py:class:`~hdmf_zarr.backend.ZarrIO` backend.

with HDF5IO(path="example.h5", manager=get_manager(), mode='r') as hdf5_read_io:
    with ZarrIO(path="example_exp.zarr",  manager=get_manager(), mode='w') as zarr_export_io:
        zarr_export_io.export(src_io=hdf5_read_io, write_args=dict(link_data=False))  # use export!

###############################################################################
# Check that the Zarr file is correct
#
with ZarrIO(path="example_exp.zarr", manager=get_manager(), mode='r') as zarr_read_io:
    intable_from_zarr = zarr_read_io.read()
    intable_zarr_df = intable_from_zarr.to_dataframe()
intable_zarr_df  # display the table in the gallery output


###############################################################################
# Using custom Zarr storage backends
# -----------------------------------
#
# :py:class:`~hdmf_zarr.backend.ZarrIO` supports a subset of data stores available
# for Zarr, e.g., :py:class`~zarr.storage.DirectoryStore`, :py:class`~zarr.storage.TempStore`,
# and :py:class`~zarr.storage.NestedDirectoryStore`. The supported stores are defined
# in :py:attr:`~hdmf_zarr.backend.SUPPORTED_ZARR_STORES`. A main limitation to supporting
# all possible Zarr stores in :py:class:`~hdmf_zarr.backend.ZarrIO` is due to the fact that
# Zarr does not support links and references.
#
# .. note:
#
#     See :ref:`sec-integrating-zarr-data-store` for details on how to integrate
#     new stores with :py:class:`~hdmf_zarr.backend.ZarrIO`.
#
# To use a store other than the default, we simply need to instantiate the store
# and set pass it to :py:class:`~hdmf_zarr.backend.ZarrIO` via the ``path`` parameter.
# Here we use a :py:class`~zarr.storage.NestedDirectoryStore` to write a simple
# :py:class:`hdmf.common.CSRMatrix` container to disk.
#

from zarr.storage import NestedDirectoryStore
from hdmf.common import CSRMatrix

zarr_nsd_dir = "example_nested_store.zarr"
store = NestedDirectoryStore(zarr_dir)
csr_container = CSRMatrix(
    name=ROOT_NAME,
    data=[1, 2, 3, 4, 5, 6],
    indices=[0, 2, 2, 0, 1, 2],
    indptr=[0, 2, 3, 6],
    shape=(3, 3))

# Write the csr_container to Zarr using a NestedDirectoryStore
with ZarrIO(path=zarr_nsd_dir,  manager=get_manager(), mode='w') as zarr_io:
    zarr_io.write(csr_container)

# Read the CSR matrix to confirm the data was written correctly
with ZarrIO(path=zarr_nsd_dir, manager=get_manager(), mode='r') as zarr_io:
    csr_read = zarr_io.read()
    print(" data=%s\n indices=%s\n indptr=%s\n shape=%s" %
          (str(csr_read.data), str(csr_read.indices), str(csr_read.indptr), str(csr_read.shape)))
