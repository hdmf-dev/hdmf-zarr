"""Generate a zarr v2 NWB file using hdmf-zarr<1.0 and zarr<3.

This script is meant to run in a temporary environment with::

    pip install "hdmf-zarr<1.0" "zarr>=2.18,<3" pynwb

It creates a small but representative NWB zarr file that exercises the
data types most affected by the zarr v2 → v3 migration:

* Scalar string / datetime datasets (fill_value=0 issue)
* Object-dtype columns in DynamicTables (pickle / json2 / vlen-utf8 codecs)
* Electrode groups, devices (object references)
* TimeSeries with numerical data
* Subject metadata with date_of_birth

The file is written to the path given as the first CLI argument.
Metadata expectations are printed as JSON to stdout so the test can
capture them without hard-coding values in two places.
"""

import json
import os
from argparse import ArgumentParser
import numpy as np
from datetime import datetime
from dateutil.tz import tzlocal

from pynwb import NWBFile
from pynwb.ecephys import ElectricalSeries
from hdmf_zarr import NWBZarrIO


def main(nwb_output_path: str, expectations_output_path: str = None) -> None:
    if os.path.exists(nwb_output_path):
        import shutil
        shutil.rmtree(nwb_output_path)

    session_start = datetime(2024, 3, 15, 10, 30, 0, tzinfo=tzlocal())

    nwbfile = NWBFile(
        session_description="backward compat test session",
        identifier="v2-compat-test-id",
        session_start_time=session_start,
        experimenter=["Alice", "Bob"],
        lab="Compat Lab",
        institution="Test University",
        experiment_description="Testing zarr v2 to v3 backward compatibility",
        session_id="session-001",
    )

    # Subject with date_of_birth (datetime, |O dtype with fill_value=0)
    from pynwb.file import Subject
    nwbfile.subject = Subject(
        subject_id="mouse-001",
        age="P90D",
        species="Mus musculus",
        sex="M",
        description="Test subject for backward compat",
        date_of_birth=datetime(2023, 12, 15, 0, 0, 0, tzinfo=tzlocal()),
    )

    # Device + electrode group + electrodes (object-dtype 'group' column)
    device = nwbfile.create_device(name="probe_A", description="Test probe", manufacturer="ACME")
    electrode_group = nwbfile.create_electrode_group(
        name="shank0",
        description="Shank 0 of probe A",
        location="brain area X",
        device=device,
    )

    n_electrodes = 8
    for i in range(n_electrodes):
        nwbfile.add_electrode(
            x=float(i), y=0.0, z=0.0,
            imp=np.nan,
            filtering="none",
            group=electrode_group,
            location="brain area X",
        )

    # Electrical series (numerical data — should be readable via normal zarr v3 path)
    electrode_table_region = nwbfile.create_electrode_table_region(
        region=list(range(n_electrodes)),
        description="all electrodes",
    )
    n_samples = 100
    electrical_series = ElectricalSeries(
        name="test_ephys",
        data=np.random.randn(n_samples, n_electrodes).astype(np.float64),
        electrodes=electrode_table_region,
        timestamps=np.linspace(0, 1, n_samples),
        description="Test ephys data",
    )
    nwbfile.add_acquisition(electrical_series)

    # Write
    with NWBZarrIO(path=nwb_output_path, mode="w") as io:
        io.write(nwbfile)

    # Emit metadata expectations as JSON
    expectations = {
        "identifier": "v2-compat-test-id",
        "session_description": "backward compat test session",
        "session_id": "session-001",
        "lab": "Compat Lab",
        "institution": "Test University",
        "experiment_description": "Testing zarr v2 to v3 backward compatibility",
        "subject_id": "mouse-001",
        "subject_species": "Mus musculus",
        "subject_sex": "M",
        "subject_age": "P90D",
        "n_electrodes": n_electrodes,
        "n_devices": 1,
        "n_electrode_groups": 1,
        "device_name": "probe_A",
        "electrode_group_name": "shank0",
        "ephys_data_shape": [n_samples, n_electrodes],
        "ephys_name": "test_ephys",
    }
    with open(expectations_output_path, "w") as f:
        json.dump(expectations, f)


parser = ArgumentParser(description="Generate a zarr v2 NWB file for backward compatibility tests.")
parser.add_argument(
    "--nwb-output-path",
    type=str,
    help="Path to write the output NWB zarr file (e.g. /tmp/test_file.zarr)",
)
parser.add_argument(
    "--expectations-output-path",
    type=str,
    help="Path to write the JSON file with metadata expectations (e.g. /tmp/expectations.json)",
)
if __name__ == "__main__":
    args = parser.parse_args()
    main(args.nwb_output_path, args.expectations_output_path)
