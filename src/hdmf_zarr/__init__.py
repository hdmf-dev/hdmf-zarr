from .backend import ZarrIO
from .utils import ZarrDataIO
from .nwb import NWBZarrIO

try:
    # see https://effigies.gitlab.io/posts/python-packaging-2023/
    from ._version import __version__
except ImportError:  # pragma: no cover
    # this is a relatively slower method for getting the version string
    from importlib.metadata import version  # noqa: E402

    __version__ = version("hdmf")
    del version

__all__ = ["ZarrIO", "ZarrDataIO", "NWBZarrIO"]

# Duecredit definitions
from ._due import due, BibTeX  # noqa: E402

due.cite(
    BibTeX(
        """
@INPROCEEDINGS{9005648,
  author={A. J. {Tritt} and O. {Rübel} and B. {Dichter} and R. {Ly} and D. {Kang} and E. F. {Chang} and L. M. {Frank} and K. {Bouchard}},
  booktitle={2019 IEEE International Conference on Big Data (Big Data)},
  title={HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards},
  year={2019},
  volume={},
  number={},
  pages={165-179},
  doi={10.1109/BigData47090.2019.9005648}}
"""  # noqa: E501
    ),
    description="HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards",
    path="hdmf/",
    version=__version__,
    cite_module=True,
)
del due, BibTeX
