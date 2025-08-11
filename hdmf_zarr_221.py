import datetime
import uuid

import hdmf_zarr
import numpy
import pynwb

nwbfile = pynwb.NWBFile(
    session_description="", identifier=str(uuid.uuid4()), session_start_time=datetime.datetime.now().astimezone()
)
regular_timestamps = numpy.arange(1.2, 11.2, 2)
timestamps_length = len(regular_timestamps)
time_series = pynwb.TimeSeries(
    name="test_time_series",
    data=numpy.zeros(shape=(timestamps_length, timestamps_length - 1)),
    timestamps=regular_timestamps,
    unit="",
)
nwbfile.add_acquisition(time_series)

nwbfile_path = "test_validation_time_series.nwb.zarr"
with hdmf_zarr.NWBZarrIO(path=nwbfile_path, mode="w") as io:
    io.write(nwbfile)

with hdmf_zarr.NWBZarrIO(path=nwbfile_path, mode="r") as io:
    invalidations = pynwb.validate(io=io)
