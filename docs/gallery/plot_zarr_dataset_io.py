"""
Zarr Dataset I/O
================

To customize data write settings on a per-dataset basis, HDMF supports
wrapping of data arrays using :py:class:`~hdmf.data_utils.DataIO`. To
support defining settings specific to Zarr ``hdmf-zarr`` provides
the corresponding :py:class:`~hdmf_zarr.utils.ZarrDataIO` class.

Create an example DynamicTable Container
----------------------------------------

As a simple example, we first create a ``DynamicTable`` container
to store some arbitrary data columns.
"""
# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_zarr_dataset_io.png'

# Import DynamicTable and get the ROOT_NAME
from hdmf.common.table import DynamicTable, VectorData
from hdmf_zarr.backend import ROOT_NAME
from hdmf_zarr import ZarrDataIO
import numpy as np

# Setup a DynamicTable for managing data about users
data = np.arange(50).reshape(10, 5)
column = VectorData(
    name='test_data_default_settings',
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
# To define custom settings for write (e.g., for chunking and compression) we simply
# wrap our data array using  :py:class:`~hdmf_zarr.utils.ZarrDataIO`.

from numcodecs import Blosc

data_with_data_io = ZarrDataIO(
    data=data * 3,
    chunks=(10, 10),
    fillvalue=0,
    compressor=Blosc(cname='zstd', clevel=1, shuffle=Blosc.SHUFFLE)
)

###############################################################################
# Adding the data to our table

test_table.add_column(
    name='test_data_zstd_compression',
    description='Some 2D test data',
    data=data_with_data_io)

###############################################################################
# Next we add a column where we explicitly disable compression
data_without_compression = ZarrDataIO(
    data=data*5,
    compressor=False)
test_table.add_column(
    name='test_data_nocompression',
    description='Some 2D test data',
    data=data_without_compression)

###############################################################################
# .. note::
#
#    To control linking to other datasets see the ``link_data`` parameter of :py:class:`~hdmf_zarr.utils.ZarrDataIO`
#
# .. note::
#
#    In the case of :py:class:`~hdmf.container.Data` (or here :py:class:`~hdmf.common.table.VectorData`) we
#    can also set the ``DataIO`` object to use via the :py:meth:`~hdmf.container.Data.set_dataio` function.


###############################################################################
# Writing and Reading
# -------------------
# Reading and writing data with filters works as usual. See the :ref:`zarrio_tutorial` tutorial for details.
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
# Check dataset settings used.
#
for c in intable.columns:
    print("Name=%s, Chunks=% s, Compressor=%s" %
          (c.name,
           str(c.data.chunks),
           str(c.data.compressor)))

###############################################################################
#
zarr_io.close()
