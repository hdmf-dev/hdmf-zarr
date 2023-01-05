Installation
============

For Users
---------

Install hdmf-zarr from PyPI
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    pip install hdmf-zarr
    
Install hdmf-zarr from conda-forge
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block::

    conda install -c conda-forge hdmf-zarr

For Developers
--------------

Install hdmf-zarr from GitHub
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following illustrates how to install both ``hdmf`` and ``hdfm_zarr`` from GitHub
in a Conda environment. Normally we don't need to install ``hdmf`` directly, but until
``hdmf 3.4.0`` is released we need to use the ``dev`` version of ``hdmf``.

.. code-block::

    conda create --name hdmf-zarr-test python=3.9
    conda activate hdmf-zarr-test
    conda install h5py

    git clone --recurse-submodules https://github.com/hdmf-dev/hdmf.git
    cd hdmf
    pip install -r requirements.txt -r requirements-dev.txt -r requirements-doc.txt -r requirements-opt.txt
    pip install -e .
    cd ..

    git clone https://github.com/hdmf-dev/hdmf-zarr.git
    cd hdmf-zarr
    pip install -r requirements.txt -r requirements-dev.txt -r requirements-doc.txt
    pip install -e .

.. note::

   Depending on versions, it is possible that when installing ``hdmf-zarr`` that pip will
   install HDMF directly from PyPI instead of using the development version of HDMF
   that is already installed. In that case call ``pip uninstall hdmf`` and
   go to the ``hdmf`` directory and run ``pip install -e .`` again



