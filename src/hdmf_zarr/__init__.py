# flake8: noqa: F401
from . import backend
from .backend import ZarrIO
from . import utils
from .utils import ZarrDataIO

# Add the zarr.Array to the HDMF docval macro os that it can pass as array_data
def __add_zarr_array_to_docval():
    """
    Private helper function to add zarr.Array to the HDMF docval macros.

    We do this in a function to avoid pulling zarr and hdmf into main
    namespace of the package
    """
    import zarr
    import hdmf
    hdmf.utils.__macros['array_data'].append(zarr.Array)

__add_zarr_array_to_docval()