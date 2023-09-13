# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_convert_nwb.png'
import os
import shutil

# Input file to convert
basedir = "resources"
filename = os.path.join(basedir, "sub_anm00239123_ses_20170627T093549_ecephys_and_ogen.nwb")
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
        else:  # remove whole directory and subtree (here the Zarr file)
            shutil.rmtree(zarr_filename)

###############################################################################
# Convert the NWB file from HDF5 to Zarr
# --------------------------------------
#
# To convert files between storage backends, we use HMDF's :hdmf-docs:`export <export.html>` functionality.
# As this is an NWB file, we here use the :py:class:`pynwb.NWBHDF5IO` backend for reading the file from
# from HDF5 and use the :py:class:`~hdmf_zarr.nwb.NWBZarrIO` backend to export the file to Zarr.

from pynwb import NWBHDF5IO
from hdmf_zarr.nwb import NWBZarrIO

with NWBHDF5IO(filename, 'r', load_namespaces=False) as read_io:
    file = read_io.read()
#
with NWBHDF5IO(filename, 'r', load_namespaces=False) as read_io:  # Create HDF5 IO object for read
    with NWBZarrIO(zarr_filename, mode='w') as export_io:         # Create Zarr IO object for write
        export_io.export(src_io=read_io, write_args=dict(link_data=False))   # Export from HDF5 to Zarr

with NWBZarrIO(path=zarr_filename, mode="r") as io:
    infile = io.read()

group = infile.electrodes.group.data[0]
breakpoint()
