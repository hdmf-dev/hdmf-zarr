"""
.. _nwbzarrio_tutorial:

Creating NWB files using ``NWBZarrIO``
======================================

Similar to :py:class:`pynwb.NWBHDF5IO`, the :py:class:`~hdmf_zarr.nwb.NWBZarrIO` extends the basic
:py:class:`~hdmf_zarr.backend.ZarrIO` to perform default setup for BuildManager, loading or namespaces etc.,
in the context of the NWB format, to simplify using hdmf-zarr with the NWB data standard.  With this we
can use :py:class:`~hdmf_zarr.nwb.NWBZarrIO` directly with the PyNWB API to read/write NWB files to/from Zarr.
I.e., we can follow the standard PyNWB tutorials for using NWB files, and only need to replace
:py:class:`pynwb.NWBHDF5IO` with :py:class:`~hdmf_zarr.nwb.NWBZarrIO` for read/write (and replace the
use of py:class:`H5DataIO`  with :py:class:`~hdmf_zarr.utils.ZarrDataIO`).


Creating and NWB extracellular electrophysiology file
-----------------------------------------------------

As an example, we here create an extracellular electrophysiology NWB file.
This example is derived from :pynwb-docs:`Extracellular Electrophysiology <tutorials/domain/ecephys.html>`
tutorial.

"""
# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_nwbzarrio.png'
# Ignore warnings about the development of the ZarrIO backend

from datetime import datetime
from dateutil.tz import tzlocal
import zarr

import numpy as np
from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries, LFP

# Create the NWBFile
nwbfile = NWBFile(
    session_description="my first synthetic recording",
    identifier="EXAMPLE_ID",
    session_start_time=datetime.now(tzlocal()),
    experimenter="Dr. Bilbo Baggins",
    lab="Bag End Laboratory",
    institution="University of Middle Earth at the Shire",
    experiment_description="I went on an adventure with thirteen dwarves "
    "to reclaim vast treasures.",
    session_id="LONELYMTN",
)

# Create a device
device = nwbfile.create_device(
    name="array", description="the best array", manufacturer="Probe Company 9000"
)

# Add electrodes and electrode groups to the NWB file
nwbfile.add_electrode_column(name="label", description="label of electrode")

nshanks = 4
nchannels_per_shank = 3
electrode_counter = 0

for ishank in range(nshanks):
    # create an electrode group for this shank
    electrode_group = nwbfile.create_electrode_group(
        name="shank{}".format(ishank),
        description="electrode group for shank {}".format(ishank),
        device=device,
        location="brain area",
    )
    # add electrodes to the electrode table
    for ielec in range(nchannels_per_shank):
        nwbfile.add_electrode(
            x=5.3, y=1.5, z=8.5, imp=np.nan,
            filtering='unknown',
            group=electrode_group,
            label="shank{}elec{}".format(ishank, ielec),
            location="brain area",
        )
        electrode_counter += 1

# Create a table region to select the electrodes to record from
all_table_region = nwbfile.create_electrode_table_region(
    region=list(range(electrode_counter)),  # reference row indices 0 to N-1
    description="all electrodes",
)

# Add a mock electrical recording acquisition to the NWBFile
raw_data = np.random.randn(50, len(all_table_region))
raw_electrical_series = ElectricalSeries(
    name="ElectricalSeries",
    data=raw_data,
    electrodes=all_table_region,
    starting_time=0.0,  # timestamp of the first sample in seconds relative to the session start time
    rate=20000.0,  # in Hz
)
nwbfile.add_acquisition(raw_electrical_series)

# Add a mock LFP processing result to the NWBFile
lfp_data = np.random.randn(50, len(all_table_region))
lfp_electrical_series = ElectricalSeries(
    name="ElectricalSeries",
    data=lfp_data,
    electrodes=all_table_region,
    starting_time=0.0,
    rate=200.0,
)
lfp = LFP(electrical_series=lfp_electrical_series)
ecephys_module = nwbfile.create_processing_module(
    name="ecephys", description="processed extracellular electrophysiology data"
)
ecephys_module.add(lfp)

# Add mock spike times and units to the NWBFile
nwbfile.add_unit_column(name="quality", description="sorting quality")

poisson_lambda = 20
firing_rate = 20
n_units = 10
for n_units_per_shank in range(n_units):
    n_spikes = np.random.poisson(lam=poisson_lambda)
    spike_times = np.round(
        np.cumsum(np.random.exponential(1 / firing_rate, n_spikes)), 5
    )
    nwbfile.add_unit(
        spike_times=spike_times, quality="good", waveform_mean=[1.0, 2.0, 3.0, 4.0, 5.0]
    )

###############################################################################
# Writing the NWB file to Zarr
# -----------------------------
from hdmf_zarr.nwb import NWBZarrIO
import os

path = "ecephys_tutorial.nwb.zarr"
absolute_path = os.path.abspath(path)
with NWBZarrIO(path=path, mode="w") as io:
    io.write(nwbfile)

###############################################################################
# Test opening with the absolute path instead
# -------------------------------------------
#
# The main reason for using the ``absolute_path`` here is for testing purposes
# to ensure links and references work as expected. Otherwise, using the
# relative ``path`` here instead is fine.
with NWBZarrIO(path=absolute_path, mode="r") as io:
    infile = io.read()

###############################################################################
# Consolidating Metadata
# ----------------------
# When writing to Zarr, the metadata within the file will be consolidated into a single
# file within the root group, `.zmetadata`. Users who do not wish to consolidate the
# metadata can set the boolean parameter `consolidate_metadata` to `False` within `write`.
# Even when the metadata is consolidated, the metadata natively within the file can be altered.
# Any alterations within would require the user to call `zarr.convenience.consolidate_metadata()`
# to sync the file with the changes. Please refer to the Zarr documentation for more details:
# https://zarr.readthedocs.io/en/v2.18.4/tutorial.html#storage-alternatives
zarr.consolidate_metadata(path)
