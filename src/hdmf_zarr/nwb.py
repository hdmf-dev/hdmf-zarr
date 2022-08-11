"""Module with Zarr backend for NWB for integration with PyNWB"""
from warnings import warn
from .backend import ZarrIO
import zarr

from hdmf.utils import (docval,
                        popargs)
from hdmf.backends.io import HDMFIO
from hdmf.build import (BuildManager,
                        TypeMap)

try:
    from pynwb import get_manager, get_type_map

    class NWBZarrIO(ZarrIO):
        """
        IO backend for PyNWB for writing NWB files

        This class is similar to the NWBHDF5IO class in PyNWB. The main purpose of this class
        is to perform default setup for BuildManager, loading or namespaces etc., in the context
        of the NWB format.
        """

        @docval({'name': 'path', 'type': str, 'doc': 'the path to the Zarr file'},
                {'name': 'mode', 'type': str,
                 'doc': 'the mode to open the Zarr file with, one of ("w", "r", "r+", "a", "w-")'},
                {'name': 'load_namespaces', 'type': bool,
                 'doc': 'whether or not to load cached namespaces from given path - not applicable in write mode',
                 'default': False},
                {'name': 'manager', 'type': BuildManager, 'doc': 'the BuildManager to use for I/O',
                 'default': None},
                {'name': 'extensions', 'type': (str, TypeMap, list),
                 'doc': 'a path to a namespace, a TypeMap, or a list consisting paths  to namespaces and TypeMaps',
                 'default': None},
                {'name': 'synchronizer', 'type': (zarr.ProcessSynchronizer, zarr.ThreadSynchronizer, bool),
                 'doc': 'Zarr synchronizer to use for parallel I/O. If set to True a ProcessSynchronizer is used.',
                 'default': None})
        def __init__(self, **kwargs):
            path, mode, manager, extensions, load_namespaces, synchronizer = \
                popargs('path', 'mode', 'manager', 'extensions',
                        'load_namespaces', 'synchronizer', kwargs)
            if load_namespaces:
                if manager is not None:
                    warn("loading namespaces from file - ignoring 'manager'")
                if extensions is not None:
                    warn("loading namespaces from file - ignoring 'extensions' argument")
                # namespaces are not loaded when creating an NWBZarrIO object in write mode
                if 'w' in mode or mode == 'x':
                    raise ValueError("cannot load namespaces from file when writing to it")

                tm = get_type_map()
                super(NWBZarrIO, self).load_namespaces(tm, path)
                manager = BuildManager(tm)
            else:
                if manager is not None and extensions is not None:
                    raise ValueError("'manager' and 'extensions' cannot be specified together")
                elif extensions is not None:
                    manager = get_manager(extensions=extensions)
                elif manager is None:
                    manager = get_manager()
            super(NWBZarrIO, self).__init__(path,
                                            manager=manager,
                                            mode=mode,
                                            synchronizer=synchronizer)

        @docval({'name': 'src_io', 'type': HDMFIO, 'doc': 'the HDMFIO object for reading the data to export'},
                {'name': 'nwbfile', 'type': 'NWBFile',
                 'doc': 'the NWBFile object to export. If None, then the entire contents of src_io will be exported',
                 'default': None},
                {'name': 'write_args', 'type': dict, 'doc': 'arguments to pass to :py:meth:`write_builder`',
                 'default': dict()})
        def export(self, **kwargs):
            nwbfile = popargs('nwbfile', kwargs)
            kwargs['container'] = nwbfile
            super().export(**kwargs)

except ImportError:
    warn("PyNWB is not installed. Support for NWBZarrIO is disabled.")
