"""
.. _s3_streaming_tutorial:

Streaming NWB Zarr files from S3
=================================

This tutorial demonstrates how to stream NWB files stored in Zarr format from Amazon S3 cloud storage.
Streaming from S3 allows you to access large datasets without downloading the entire file, which is
particularly useful for exploring data, reading specific subsets, or working with datasets too large
for local storage.

Prerequisites
-------------

To stream data from S3, you need to install the optional dependencies ``fsspec`` and ``s3fs``:

.. code-block:: bash

    pip install hdmf-zarr[full]

Or install the dependencies separately:

.. code-block:: bash

    pip install fsspec s3fs

"""
# sphinx_gallery_thumbnail_path = 'figures/gallery_thumbnail_plot_streaming_s3.png'

###############################################################################
# Streaming from a Public S3 Bucket
# ----------------------------------
#
# To read an NWB Zarr file from a public S3 bucket, you can provide the S3 URL
# to :py:class:`~hdmf_zarr.nwb.NWBZarrIO`. For HTTPS URLs (``https://``), no
# additional configuration is needed. For ``s3://`` protocol URLs, you need to
# specify ``storage_options=dict(anon=True)`` to enable anonymous access.
#
# Here we demonstrate reading from a public dataset in the DANDI Archive using
# an HTTPS URL:

from hdmf_zarr import NWBZarrIO

# Public S3 URL from DANDI Archive (DANDISET 000719)
# Path: sub-R6_ses-20200206T210000_behavior+ophys_DirectoryStore_rechunked.nwb.zarr
s3_url = "https://dandiarchive.s3.amazonaws.com/zarr/c8c6b848-fbc6-4f58-85ff-e3f2618ee983/"

# Open the file from S3
try:
    with NWBZarrIO(s3_url, mode="r") as io:
        nwbfile = io.read()
        print(f"Session Description: {nwbfile.session_description}")
        print(f"Identifier: {nwbfile.identifier}")
        print(f"Subject ID: {nwbfile.subject.subject_id if nwbfile.subject else 'N/A'}")
except Exception as e:
    print(f"Note: Could not access S3 file (network access may be required): {e}")

###############################################################################
# .. note::
#
#     For S3 URLs with the ``s3://`` protocol, you need to provide the ``storage_options``
#     parameter explicitly. For example:
#
#     .. code-block:: python
#
#         s3_path = "s3://your-bucket/path/to/file.nwb.zarr/"
#         with NWBZarrIO(s3_path, mode="r", storage_options=dict(anon=True)) as io:
#             nwbfile = io.read()

###############################################################################
# Accessing Private S3 Buckets
# -----------------------------
#
# To access files in private S3 buckets, you need to provide AWS credentials.
# There are several ways to do this:
#
# **Option 1: Use AWS credentials from environment or ~/.aws/credentials**
#
# If your AWS credentials are configured via environment variables
# (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``) or in the AWS credentials file,
# you can simply omit the ``anon=True`` option:
#
# .. code-block:: python
#
#     with NWBZarrIO(s3_url, mode="r") as io:
#         nwbfile = io.read()
#
# **Option 2: Provide credentials explicitly**
#
# You can also provide credentials directly via the ``storage_options`` parameter:
#
# .. code-block:: python
#
#     storage_options = {
#         'key': 'YOUR_ACCESS_KEY_ID',
#         'secret': 'YOUR_SECRET_ACCESS_KEY',
#     }
#     with NWBZarrIO(s3_url, mode="r", storage_options=storage_options) as io:
#         nwbfile = io.read()
#
# **Note:** Never hardcode credentials in your scripts. Use environment variables
# or AWS credentials files instead.

###############################################################################
# The Importance of Consolidated Metadata
# ----------------------------------------
#
# Zarr files store metadata for each array and group in separate files. When reading
# from S3, each metadata access requires a separate network request, which can
# significantly slow down file opening and data access.
#
# **Consolidated metadata** addresses this by storing all metadata in a single
# ``.zmetadata`` file at the root of the Zarr store. This helps improve read performance
# by reducing the number of S3 requests needed to open a file.
#
# By default, :py:class:`~hdmf_zarr.nwb.NWBZarrIO` consolidates metadata when
# writing files, and automatically uses consolidated metadata when available
# during read operations.

###############################################################################
# Generating and Updating Consolidated Metadata
# ----------------------------------------------
#
# When you create or modify a Zarr file, you should consolidate the metadata
# to ensure optimal performance for readers, especially those streaming from S3.
# By default, :py:class:`~hdmf_zarr.nwb.NWBZarrIO` automatically consolidates
# metadata when writing files. See the
# :py:meth:`~hdmf_zarr.nwb.NWBZarrIO.write` method's ``consolidate_metadata``
# parameter for more details.
#
# .. note::
#
#     If you modify a Zarr file after creation (e.g., by directly using zarr APIs),
#     you need to manually update the consolidated metadata:
#
#     .. code-block:: python
#
#         import zarr
#         path = "myfile.nwb.zarr"
#         zarr.consolidate_metadata(path)
#
#     This ensures that the ``.zmetadata`` file reflects the current state of the
#     Zarr store. This step is critical before uploading modified files to S3.
#
#     For more details on consolidated metadata, see the
#     `Zarr documentation <https://zarr.readthedocs.io/en/stable/user-guide/consolidated_metadata.html>`_ and the
#     :ref:`sec-zarr-storage` section of the hdmf-zarr documentation.

###############################################################################
# Using the Convenience Method
# ----------------------------
#
# :py:class:`~hdmf_zarr.nwb.NWBZarrIO` provides a convenience static method
# :py:meth:`~hdmf_zarr.nwb.NWBZarrIO.read_nwb` for quick read access:

# Read file directly using the convenience static method
try:
    nwbfile = NWBZarrIO.read_nwb(s3_url)
    print(f"Session Start Time: {nwbfile.session_start_time}")
except Exception as e:
    print(f"Note: Could not access S3 file (network access may be required): {e}")

###############################################################################
# .. note::
#
#     PyNWB also provides a more general :py:func:`~pynwb.NWBHDF5IO.read` method that
#     can automatically detect and use the appropriate IO class (HDF5 or Zarr) based
#     on the file path or URL.

###############################################################################
# Best Practices for S3 Streaming
# --------------------------------
#
# 1. **Always use consolidated metadata** for files stored on S3. This is the default
#    when writing with :py:class:`~hdmf_zarr.nwb.NWBZarrIO`.
#
# 2. **Use HTTPS URLs** (``https://``) for public buckets when possible, as they
#    work without additional configuration.
#
# 3. **For private buckets**, configure AWS credentials properly using environment
#    variables or the AWS credentials file rather than hardcoding them.
#
# 4. **After modifying Zarr files**, always run ``zarr.consolidate_metadata(path)``
#    before uploading to S3.
#
# 5. **Test your S3 URLs** to ensure they are accessible before sharing them with
#    collaborators.
#
# 6. **Consider network costs**: While streaming is convenient, repeated access to
#    the same data may be less efficient than downloading the file once for local
#    access.
