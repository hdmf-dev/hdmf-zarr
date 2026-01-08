"""
Converting NWB HDF5 files to/from Zarr
======================================

This tutorial illustrates how to convert data between HDF5 and Zarr using
a Neurodata Without Borders (NWB) file from the DANDI data archive as an example.
In this tutorial we will convert our example file from HDF5 to Zarr and then
back again to HDF5. The NWB standard is defined using :hdmf-docs:`HDMF <>` and uses the
:py:class:`~ hdmf.backends.hdf5.h5tools.HDF5IO`  HDF5 backend from HDMF for storage.
"""

###############################################################################
# Setup
# -----
#
# Here we use a small NWB file from the DANDI neurophysiology data archive from
# `Dandiset 001333 <https://dandiarchive.org/dandiset/001333/0.250327.2220>`_ as an example.
# To download the file directly from DANDI we can use:
#
# .. code-block:: python
#    :linenos:
#
#    import os
#    from dandi.dandiapi import DandiAPIClient
#
#    dandiset_id = "001333"
#    filepath = "sub-healthy-simulated-beta/sub-healthy-simulated-beta_ses-162_ecephys.nwb"   # 220 KiB file
#    with DandiAPIClient() as client:
#        asset = client.get_dandiset(dandiset_id, 'draft').get_asset_by_path(filepath)
#
#    s3_path = asset.get_content_url(follow_redirects=1, strip_query=True)
#    filename = os.path.basename(asset.path)
#    asset.download(filename)
#
# We here use a local copy of a small file from this Dandiset as an example:


# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_convert_nwb.png'
import os
import shutil
from pynwb import NWBHDF5IO
from hdmf_zarr.nwb import NWBZarrIO

# Input file to convert
basedir = "resources"
filename = os.path.join(basedir, "sub-healthy-simulated-beta_ses-162_ecephys.nwb")
# Zarr file to generate for converting from HDF5 to Zarr
zarr_filename = "test_zarr_" + os.path.basename(filename) + ".zarr"
# HDF5 file to generate for converting from Zarr to HDF5
hdf_filename = "test_hdf5_" + os.path.basename(filename)

# Delete our converted HDF5 and Zarr file from previous runs of this notebook
for fname in [zarr_filename, hdf_filename]:
    if os.path.exists(fname):
        print("Removing %s" % fname)
        if os.path.isfile(fname):  # Remove a single file (here the HDF5 file)
            os.remove(fname)
        else:  # Remove whole directory and subtree (here the Zarr file)
            shutil.rmtree(fname)

###############################################################################
# Convert the NWB file from HDF5 to Zarr
# --------------------------------------
#
# To convert files between storage backends, we use HDMF's :hdmf-docs:`export <export.html>` functionality.
# As this is an NWB file, we here use the :py:class:`pynwb.NWBHDF5IO` backend for reading the file from
# from HDF5 and use the :py:class:`~hdmf_zarr.nwb.NWBZarrIO` backend to export the file to Zarr.

with NWBHDF5IO(filename, 'r') as read_io:  # Create HDF5 IO object for read
    with NWBZarrIO(zarr_filename, 'w') as export_io:  # Create Zarr IO object for write
        export_io.export(src_io=read_io, write_args=dict(link_data=False))  # Export from HDF5 to Zarr

###############################################################################
# .. note::
#
#     When converting between backends we need to set ``link_data=False`` as linking
#     from Zarr to HDF5 (and vice-versa) is not supported.
#
# Read the Zarr file back in
# --------------------------

zarr_io = NWBZarrIO(zarr_filename, 'r')
nwb_zarr = zarr_io.read()

###############################################################################
# The basic behavior of the :py:class:`~pynwb.file.NWBFile` object is the same.

# Print the NWBFile to illustrate that
print(nwb_zarr)

###############################################################################
# The main difference is that datasets are now represented by Zarr arrays compared
# to h5py Datasets when reading from HDF5.

print(type(nwb_zarr.electrodes['label'].data))

###############################################################################
# For illustration purposes, we here show the NWB
# :pynwb-docs:`Electrodes <tutorials/domain/ecephys.html>` table.

print(nwb_zarr.electrodes.to_dataframe())
zarr_io.close()

###############################################################################
# Convert the Zarr file back to HDF5
# ----------------------------------
#
# Using the same approach as above, we can now convert our Zarr file back to HDF5.

with NWBZarrIO(zarr_filename, 'r') as read_io:  # Create Zarr IO object for read
    with NWBHDF5IO(hdf_filename, 'w') as export_io:  # Create HDF5 IO object for write
        export_io.export(src_io=read_io, write_args=dict(link_data=False))  # Export from Zarr to HDF5

###############################################################################
# Read the new HDF5 file back
# ---------------------------
#
# Now our file has been converted from HDF5 to Zarr and back again to HDF5.
# Here we check that we can still read that file.

with NWBHDF5IO(hdf_filename, 'r') as hdf5_io:
    nwb_hdf5 = hdf5_io.read()
    print(nwb_hdf5)
