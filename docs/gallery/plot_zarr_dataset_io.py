"""
Zarr Dataset I/O
================

The :py:class:`~hdmf_zarr.backend.ZarrDataIO` class is used to wrap datasets
to be able to customize I/O settings on a per-dataset basis.

Create an example DynamicTable Container
----------------------------------------

As a simple example, we here create a single :py:class:`~hdmf.common.table.VectorData` container
to store an arbitrary example array.

.. note::

   When writing a :py:class:`~hdmf.common.table.DynamicTable` (or any Container that is
   normally not intended to be the root of a file) we need to use :py:attr:`hdmf_zarr.backend.ROOT_NAME`
   as the name for the Container to ensure that link paths are created correctly by
   :py:class:`~hdmf_zarr.backend.ZarrIO`. This is due to the fact that the top-level Container
   used during I/O is written as the root of the file. As such, the name of the root Container
   of a file does not appear in the path to locate it.
"""
# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_zarr_dataset_io.png'
# Ignore warnings about the development of the ZarrIO backend
import warnings
warnings.filterwarnings('ignore', '.*The ZarrIO backend is experimental*', )

# Import DynamicTable and get the ROOT_NAME
from hdmf.common.table import DynamicTable, VectorData
from hdmf_zarr.backend import ROOT_NAME
import numpy as np

# Setup a DynamicTable for managing data about users
data = np.arange(50).reshape(10, 5)
column = VectorData(
    name='test_data',
    description='Some 2D test data',
    data=data)
test_table = DynamicTable(
    name=ROOT_NAME,
    description='a table containing data/metadata about users, one user per row',
    columns=(column, ),
    colnames=(column.name, )
)

###############################################################################
# Defining Data I/O settings
# --------------------------
#
#

from hdmf_zarr import ZarrDataIO
from numcodecs import Blosc

data_with_data_io = ZarrDataIO(
    data=data * 3,
    chunks=(10,10),
    fillvalue=0,
    compressor=Blosc(cname='zstd', clevel=1, shuffle=Blosc.SHUFFLE)
)

###############################################################################
# Adding the data to our table

test_table.add_column(
    name='test_data2',
    description='Some 2D test data',
    data=data_with_data_io)

###############################################################################
# .. note::
#
#    To control linking to other datasets see the ``link_data`` parameter of :py:class:`~hdmf_zarr.utils.ZarrDataIO`
#


###############################################################################
# Writing and Reading
# -------------------
# Reading and writing data with filters works as usual. See :ref:`zarrio_tutorial` tutorial for details.
#

from hdmf.common import get_manager
from hdmf_zarr.backend import ZarrIO

zarr_dir = "example_data.zarr"
with ZarrIO(path=zarr_dir,  manager=get_manager(), mode='w') as zarr_io:
    zarr_io.write(test_table)

###############################################################################
# reading the table from Zarr

zarr_io = ZarrIO(path=zarr_dir,  manager=get_manager(), mode='r')
intable = zarr_io.read()
intable.to_dataframe()

###############################################################################
# Check dataset settings used. Our first column uses the Zarr defaults and
# the second column uses our customized settings
for c in intable.columns:
    print("Name=%s, Chunks=% s, Compressor=%s" %
          (c.name,
           str(c.data.chunks),
           str(c.data.compressor)))
