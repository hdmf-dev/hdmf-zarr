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

The following illustrates how to install both ``hdmf`` and ``hdmf_zarr`` from GitHub
in a Conda environment, with all of the optional, testing, and documentation dependencies
for hdmf-zarr. Normally, we don't need to install ``hdmf`` directly, but it is
often useful to use the ``dev`` branch of the ``hdmf`` GitHub repository.

.. code-block::

    conda create --name hdmf-zarr-dev python=3.13
    conda activate hdmf-zarr-dev

    git clone --recurse-submodules https://github.com/hdmf-dev/hdmf.git
    cd hdmf
    pip install -e ".[all]"
    cd ..

    git clone https://github.com/hdmf-dev/hdmf-zarr.git
    cd hdmf-zarr
    pip install -e ".[all]"

.. note::

   Depending on versions, it is possible that when installing ``hdmf-zarr``, that ``pip`` will
   install HDMF directly from PyPI instead of using the development version of HDMF
   that is already installed. In that case call ``pip uninstall hdmf`` and
   go to the ``hdmf`` directory and run ``pip install -e .`` again
