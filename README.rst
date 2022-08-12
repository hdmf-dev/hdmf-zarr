.. image:: docs/source/figures/logo_hdmf_zarr.png
     :width: 400

hdmf-zarr
=========

The ``hdmf-zarr`` library implements a Zarr I/O backend for HDMF.

**Status:** The library is under development and not indented for production use.

**Citation:** If you use HDMF or hdmf_zarr in your research, please use the following citation:

* A. J. Tritt, O. Ruebel, B. Dichter, R. Ly, D. Kang, E. F. Chang, L. M. Frank, K. Bouchard,
  *"HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards,"*
  2019 IEEE International Conference on Big Data (Big Data),
  Los Angeles, CA, USA, 2019, pp. 165-179, doi: 10.1109/BigData47090.2019.9005648.

Documentation
-------------

See the ``hdmf-zarr`` documentation for details https://hdmf-zarr.readthedocs.io/en/latest/

Usage
-----

The library is intended to be used in conjunction with HDMF. ``hdmf-zarr`` mainly provides
with the ``ZarrIO`` class an alternative to the ``HDF5IO`` I/O backend that ships with HDMF.
To support customization of I/O settings, ``hdmf-zarr`` provides ``ZarrDataIO`` (similar to
``H5DataIO`` in HDMF). Using ``ZarrIO`` and ``ZarrDataIO`` works much in the same way as ``HDF5IO``.
To ease integration with the NWB data standard and PyNWB, ``hdmf-zarr`` provides the ``NWBZarrIO``
class as alternative to ``pynwb.NWBHDF5IO``. See the tutorials included with the documentation for more details.
