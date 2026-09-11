"""Interoperability test between hdmf-zarr and zindi.

zindi (https://github.com/bendichter/zindi) generates a Zarr v3 reference file system from an
HDF5 NWB file following the unified Zarr v3 convention (hdmf-dev/hdmf-zarr#335). This test
confirms that a store produced by zindi can be read directly with :class:`~hdmf_zarr.nwb.NWBZarrIO`,
which is the goal of that convention. The test is skipped when zindi is not installed.
"""

import unittest
import warnings
from datetime import datetime

import numpy as np
from dateutil.tz import tzlocal
from hdmf.testing import TestCase
from pynwb import NWBFile, NWBHDF5IO, TimeSeries
from pynwb.ecephys import ElectricalSeries

from hdmf_zarr import NWBZarrIO

try:
    from zindi import generate_rfs, RfsStore

    HAVE_ZINDI = True
except ImportError:
    HAVE_ZINDI = False


@unittest.skipIf(not HAVE_ZINDI, "zindi not installed")
class TestZindiInterop(TestCase):
    """Read a zindi-generated Zarr v3 store with NWBZarrIO."""

    def setUp(self):
        self.h5_path = "test_zindi_interop.nwb"
        nwbfile = NWBFile(
            session_description="zindi interop",
            identifier="zindi-interop",
            session_start_time=datetime(2024, 1, 1, tzinfo=tzlocal()),
        )
        device = nwbfile.create_device(name="dev")
        group = nwbfile.create_electrode_group(name="g", description="d", location="l", device=device)
        for _ in range(4):
            nwbfile.add_electrode(location="l", group=group)
        region = nwbfile.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
        self.es_data = np.arange(40, dtype="float32").reshape(10, 4)
        nwbfile.add_acquisition(
            ElectricalSeries(name="es", data=self.es_data, electrodes=region, rate=30000.0)
        )
        nwbfile.add_acquisition(TimeSeries(name="ts", data=np.arange(5.0), unit="v", rate=1.0))
        nwbfile.add_unit(spike_times=[0.1, 0.2], electrodes=[0, 1])
        nwbfile.add_unit(spike_times=[0.3], electrodes=[2])
        nwbfile.add_trial_column(name="cond", description="c")
        nwbfile.add_trial(start_time=0.0, stop_time=1.0, cond="a")
        with NWBHDF5IO(self.h5_path, "w") as io:
            io.write(nwbfile)

    def tearDown(self):
        import os

        if os.path.exists(self.h5_path):
            os.remove(self.h5_path)

    def test_read_zindi_store(self):
        rfs = generate_rfs(self.h5_path)
        store = RfsStore(rfs)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with NWBZarrIO(store, mode="r") as io:
                nwbfile = io.read()
                self.assertEqual(nwbfile.identifier, "zindi-interop")
                # scalar and numeric datasets
                np.testing.assert_array_equal(nwbfile.acquisition["ts"].data[:], np.arange(5.0))
                np.testing.assert_array_equal(nwbfile.acquisition["es"].data[:], self.es_data)
                # object reference in an attribute (electrodes.table) resolves to the electrodes table
                electrodes = nwbfile.acquisition["es"].electrodes
                self.assertIs(electrodes.table, nwbfile.electrodes)
                self.assertEqual(electrodes[:].index.tolist(), [0, 1, 2, 3])
                # link (ElectrodeGroup.device) and object references in dataset (electrodes.group)
                self.assertIs(nwbfile.electrodes["group"][0], nwbfile.electrode_groups["g"])
                self.assertIs(nwbfile.electrode_groups["g"].device, nwbfile.devices["dev"])
                # ragged (indexed) columns
                np.testing.assert_array_equal(nwbfile.units["spike_times"][0], [0.1, 0.2])
                np.testing.assert_array_equal(nwbfile.units["spike_times"][1], [0.3])
                self.assertEqual(nwbfile.units["electrodes"][1].index.tolist(), [2])
                # string column
                self.assertEqual(nwbfile.trials["cond"][0], "a")
