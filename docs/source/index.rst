.. hdmf-zarr documentation master file, created by
   sphinx-quickstart on Tue Apr 12 03:32:29 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to hdmf-zarr's documentation!
=====================================

**hdmf_zarr** implements a Zarr v2 backend for `HDMF <https://hdmf.readthedocs.io/en/stable/>`_ as well as
convenience classes for integration of Zarr with `PyNWB <https://pynwb.readthedocs.io/en/stable/>`_ to
support writing of NWB files to `Zarr v2 <https://zarr.readthedocs.io/en/v2.18.4/>`_.

**Status:** The Zarr backend is **under development** and may still change. See the
:ref:`sec-overview` section for a description of available features and known limitations of hdmf-zarr.

Support for Zarr v3 is planned. You can track progress of the support in https://github.com/hdmf-dev/hdmf-zarr/issues/202.


Citing hdmf-zarr
^^^^^^^^^^^^^^^^

* A. J. Tritt, O. Ruebel, B. Dichter, R. Ly, D. Kang, E. F. Chang, L. M. Frank, K. Bouchard,
  *"HDMF: Hierarchical Data Modeling Framework for Modern Science Data Standards,"*
  2019 IEEE International Conference on Big Data (Big Data),
  Los Angeles, CA, USA, 2019, pp. 165-179, doi: 10.1109/BigData47090.2019.9005648.

.. toctree::
   :maxdepth: 2
   :caption: For Users:

   installation
   overview
   tutorials/index

.. toctree::
   :maxdepth: 2
   :caption: For Developers:

   storage
   integrating_data_stores
   hdmf_zarr

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
