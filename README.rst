.. image:: docs/source/figures/logo_hdmf_zarr.png
     :width: 400

hdmf-zarr
=========

The ``hdmf-zarr`` library implements a Zarr backend for HDMF as well as convenience classes for integration of Zarr with PyNWB to support writing of NWB files to Zarr.

**Status:** The Zarr backend is **under development** and may still change. See the `overiew page <https://hdmf-zarr.readthedocs.io/en/latest/overview.html>`_ for an overview of the available features and known limitations of hdmf-zarr.


Latest Release
--------------

.. image:: https://readthedocs.org/projects/hdmf-zarr/badge/?version=latest
     :target: https://hdmf-zarr.readthedocs.io/en/latest/?badge=latest
     :alt: Documentation Status

CI / Health Status
-------------------

.. image:: https://codecov.io/gh/hdmf-dev/hdmf-zarr/branch/dev/graph/badge.svg
    :target: https://codecov.io/gh/hdmf-dev/hdmf-zarr

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Run%20code%20coverage/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_coverage.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Run%20tests/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_tests.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Run%20all%20tests/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_all_tests.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Check%20Sphinx%20external%20links/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/check_external_links.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Deploy%20release/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/deploy_release.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/black/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/black.yml

.. image:: https://github.com/hdmf-dev/hdmf-zarr/workflows/Run%20style%20check/badge.svg
    :target: https://github.com/hdmf-dev/hdmf-zarr/actions/workflows/run_flake8.yml



Citing hdmf-zarr
----------------

If you use HDMF or hdmf_zarr in your research, please use the following citation:

* A. J. Tritt, O. Ruebel, B. Dichter, R. Ly, D. Kang, E. F. Chang, L. M. Frank, K. Bouchard,
  *"HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards,"*
  2019 IEEE International Conference on Big Data (Big Data),
  Los Angeles, CA, USA, 2019, pp. 165-179, doi: 10.1109/BigData47090.2019.9005648.
* HDMF-Zarr, RRID:SCR_022709

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
