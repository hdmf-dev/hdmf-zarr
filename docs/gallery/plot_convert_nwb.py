"""
Converting NWB HDF5 files to/from Zarr
======================================

"""


###############################################################################
# Download a small example file from DANDI
# ----------------------------------------

# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_convert_nwb.png'
import os
import shutil
from dandi.dandiapi import DandiAPIClient

dandiset_id = '000207'
filepath = "sub-1/sub-1_ses-1_ecephys+image.nwb"  # 5 MB file
with DandiAPIClient() as client:
    asset = client.get_dandiset(dandiset_id, 'draft').get_asset_by_path(filepath)
    s3_path = asset.get_content_url(follow_redirects=1, strip_query=True)
    filename = os.path.basename(asset.path)
asset.download(filename)

###############################################################################
# Define output settings and clean up old files
# ---------------------------------------------
#

zarr_filename = "test_zarr_" + filename
hdf_filename = "test_hdf5_" + filename

# Delete our converted HDF5 file from previous runs of this notebook
if os.path.exists(hdf_filename):
    print("Removing %s" % hdf_filename)
    os.remove(hdf_filename)
# Delete our converted Zarr file from previous runs of this notebook
if os.path.exists(zarr_filename):
    print("Removing %s" % zarr_filename)
    shutil.rmtree(zarr_filename)

###############################################################################
# Convert the NWB file from HDF5 to Zarr
# --------------------------------------
#

from pynwb import NWBHDF5IO
from hdmf_zarr.nwb import NWBZarrIO

with NWBHDF5IO(filename , 'r', load_namespaces=False) as read_io:
    with NWBZarrIO(zarr_filename, mode='w') as export_io:
        export_io.export(src_io=read_io, write_args=dict(link_data=False))

###############################################################################
# .. note::
#
#     When converting between backends we need to set ``link_data=False`` as linking from Zarr
#     to HDF5 and vice-versa is not supported.
#
# Read the Zarr file back in
# --------------------------
#

zr = NWBZarrIO(zarr_filename, 'r')
zf = zr.read()

###############################################################################
# The basic behavior of the :py:class:`~pynwb.file.NWBFile` object is the same.

# Print the NWBFile to illustrate that
print(zf)

###############################################################################
# The main difference is that datasets are now represented by Zarr arrays compared
# to h5py Datasets when reading from HDF5

print(type(zf.get_acquisition(name='events').data))

###############################################################################
# Convert the Zarr file back to HDF5
# ----------------------------------
#

with NWBZarrIO(zarr_filename, mode='r') as read_io:
    with NWBHDF5IO(hdf_filename, 'w') as export_io:
        export_io.export(src_io=read_io, write_args=dict(link_data=False))

###############################################################################
# Read the new HDF5 file back
# ---------------------------
#
# Now our file has been converted from HDF5 to Zarr and back again to HDF5.
# Here we check that we can stil read that file

with NWBHDF5IO(hdf_filename , 'r') as hr:
    hf = hr.read()