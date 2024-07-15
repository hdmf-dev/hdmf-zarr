from datetime import datetime
from uuid import uuid4

import numpy as np
from dateutil.tz import tzlocal

from pynwb import NWBHDF5IO, NWBFile
from pynwb.ecephys import LFP, ElectricalSeries

from hdmf_zarr.nwb import NWBZarrIO

from hdmf.common import VectorData, DynamicTable


nwbfile = NWBFile(
    session_description="my first synthetic recording",
    identifier=str(uuid4()),
    session_start_time=datetime.now(tzlocal()),
    experimenter=[
        "Baggins, Bilbo",
    ],
    lab="Bag End Laboratory",
    institution="University of Middle Earth at the Shire",
    experiment_description="I went on an adventure to reclaim vast treasures.",
    session_id="LONELYMTN001",
)

nwbfile.add_unit_column(name="quality", description="sorting quality")

firing_rate = 20
n_units = 10
res = 1000
duration = 20
for n_units_per_shank in range(n_units):
    spike_times = np.where(np.random.rand((res * duration)) < (firing_rate / res))[0] / res
    nwbfile.add_unit(spike_times=spike_times, quality="good")

# breakpoint()

with NWBHDF5IO("ecephys_tutorial.nwb", "w") as io:
    io.write(nwbfile)

# ########
# #Convert
# # ########
filename = "ecephys_tutorial.nwb"
zarr_filename = "ecephys_tutorial.nwb.zarr"
with NWBHDF5IO(filename, 'r', load_namespaces=False) as read_io:  # Create HDF5 IO object for read
    with NWBZarrIO(zarr_filename, mode='w') as export_io:         # Create Zarr IO object for write
        export_io.export(src_io=read_io, write_args=dict(link_data=False))   # Export from HDF5 to Zarr

###NWBFILE to First zarr
# io1 = NWBZarrIO(str('ecephys_tutorial.nwb.zarr'), "r")
# nwbfile = io1.read()
# breakpoint()

# Add new data to units
col1 = VectorData(
    name='col1',
    description='column #1',
    data=list(range(0,10)),
)
# some_df_with_data = DynamicTable(name='foo', description='foo', columns=[col1])

nwb_output_path = "exported_ecephys_tutorial.nwb.zarr"
read_io = NWBZarrIO(zarr_filename, "r")
nwbfile = read_io.read()
nwbfile.add_unit_column(
    name='col',
    description='col',
    data=col1.data
)
# breakpoint()
#
with NWBZarrIO(str(nwb_output_path), "w") as export_io:
    export_io.export(src_io=read_io, nwbfile=nwbfile)
# breakpoint()
# # loading the exported NWB zarr folder fails
io = NWBZarrIO(str(nwb_output_path), "r")
breakpoint()
nwbfile = io.read()
