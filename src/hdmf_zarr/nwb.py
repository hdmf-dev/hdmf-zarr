"""Module with Zarr backend for NWB for integration with PyNWB"""
from warnings import warn
from .backend import ZarrIO

from hdmf.utils import (docval,
                        popargs,
                        get_docval)
from hdmf.backends.io import HDMFIO
from hdmf.build import (BuildManager,
                        TypeMap)
try:
    from pynwb import get_manager, get_type_map

    class NWBZarrIO(ZarrIO):
        """
        IO backend for PyNWB for writing NWB files

        This class is similar to the :py:class:`~pynwb.NWBHDF5IO` class in PyNWB. The main purpose of this class
        is to perform default setup for BuildManager, loading or namespaces etc., in the context
        of the NWB format.
        """
        @docval(*get_docval(ZarrIO.__init__),
                {'name': 'load_namespaces', 'type': bool,
                 'doc': 'whether or not to load cached namespaces from given path - not applicable in write mode',
                 'default': True},
                {'name': 'extensions', 'type': (str, TypeMap, list),
                 'doc': 'a path to a namespace, a TypeMap, or a list consisting paths  to namespaces and TypeMaps',
                 'default': None})
        def __init__(self, **kwargs):
            path, mode, manager, extensions, load_namespaces, synchronizer, storage_options = \
                popargs('path', 'mode', 'manager', 'extensions',
                        'load_namespaces', 'synchronizer', 'storage_options', kwargs)

            io_modes_that_create_file = ['w', 'w-', 'x']
            if mode in io_modes_that_create_file or manager is not None or extensions is not None:
                load_namespaces = False

            if load_namespaces:
                tm = get_type_map()
                super(NWBZarrIO, self).load_namespaces(tm, path, storage_options)
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
                                            synchronizer=synchronizer,
                                            storage_options=storage_options)

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
