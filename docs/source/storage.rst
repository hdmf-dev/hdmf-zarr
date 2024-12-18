.. _sec-zarr-storage:

=====================
Storage Specification
=====================

hdmf-zarr currently uses the Zarr :zarr-docs:`DirectoryStore <api/storage.html#zarr.storage.DirectoryStore>`,
which uses directories and files on a standard file system to serialize data.

Format Mapping
==============

Here we describe the mapping of HDMF primitives (e.g., Groups, Datasets, Attributes, Links, etc.) used by
the HDMF schema language to Zarr storage primitives. HDMF data modeling primitives were originally designed
with HDF5 in mind. However, Zarr uses very similar primitives, and as such the high-level mapping between
HDMF schema and Zarr storage is overall fairly simple. The main complication is that Zarr does not support
links and references (see `Zarr issue #389 <https://github.com/zarr-developers/zarr-python/issues/389>`_)
and as such have to implemented by hdmf-zarr.

.. tabularcolumns:: |p{4cm}|p{11cm}|

.. table:: Mapping of groups
    :class: longtable

    =============  ===============================================
    NWB Primitive  Zarr Primitive
    =============  ===============================================
    Group          Group
    Dataset        Dataset
    Attribute      Attribute
    Link           Stored as JSON formatted Attributes
    =============  ===============================================

Mapping of HDMF specification language keys
===========================================

Here we describe the mapping of keys from the HDMF specification language to Zarr storage objects:

.. _sec-zarr-storage-groups:

Groups
------

.. tabularcolumns:: |p{4cm}|p{11cm}|

.. table:: Mapping of groups
    :class: longtable

    ============================  ======================================================================================
    NWB Key                       Zarr
    ============================  ======================================================================================
    name                          Name of the Group in Zarr
    doc                           Zarr attribute ``doc`` on the Zarr group
    groups                        Zarr groups within the Zarr group
    datasets                      Zarr datasets within the Zarr group
    attributes                    Zarr attributes on the Zarr group
    links                         Stored as JSON formatted attributes on the Zarr Group
    quantity                      Not mapped; Number of appearances of the group
    neurodata_type                Attribute ``neurodata_type`` on the Zarr Group
    namespace ID                  Attribute ``namespace`` on the Zarr Group
    object ID                     Attribute ``object_id`` on the Zarr Group
    ============================  ======================================================================================

.. _sec-zarr-storage-groups-reserved:

Reserved groups
----------------

The :py:class:`~hdmf_zarr.backend.ZarrIO` backend typically caches the schema used to create a file in the
group ``/specifications`` (see also :ref:`sec-zarr-caching-specifications`)

.. _sec-zarr-storage-datasets:

Datasets
--------

.. tabularcolumns:: |p{4cm}|p{11cm}|

.. table:: Mapping of datasets
    :class: longtable

    ============================  ======================================================================================================================
    HDMF Specification Key        Zarr
    ============================  ======================================================================================================================
    name                          Name of the dataset in Zarr
    doc                           Zarr attribute ``doc`` on the Zarr dataset
    dtype                         Data type of the Zarr dataset (see `dtype mappings`_ table) and stored in the ``zarr_dtype`` reserved attribute
    shape                         Shape of the Zarr dataset if the shape is fixed, otherwise shape defines the maxshape
    dims                          Not mapped
    attributes                    Zarr attributes on the Zarr dataset
    quantity                      Not mapped; Number of appearances of the dataset
    neurodata_type                Attribute ``neurodata_type`` on the Zarr dataset
    namespace ID                  Attribute ``namespace`` on the Zarr dataset
    object ID                     Attribute ``object_id`` on the Zarr dataset
    ============================  ======================================================================================================================

.. note::

    * TODO Update mapping of dims

.. _sec-zarr-storage-attributes:

Attributes
----------

.. tabularcolumns:: |p{4cm}|p{11cm}|

.. table:: Mapping of attributes
    :class: longtable

    ============================  ======================================================================================
    HDMF Specification Key        Zarr
    ============================  ======================================================================================
    name                          Name of the attribute in Zarr
    doc                           Not mapped; Stored in schema only
    dtype                         Data type of the Zarr attribute
    shape                         Shape of the Zarr attribute if the shape is fixed, otherwise shape defines the maxshape
    dims                          Not mapped; Reflected by the shape of the attribute data
    required                      Not mapped; Stored in schema only
    value                         Data value of the attribute
    ============================  ======================================================================================

.. note::

    Attributes are stored as JSON documents in Zarr (using the DirectoryStore). As such, all attributes
    must be JSON serializable. The :py:class:`~hdmf_zarr.backend.ZarrIO` backend attempts to cast types
    (e.g., numpy arrays) to JSON serializable types as much as possible, but not all possible types may
    be supported.

.. _sec-zarr-storage-attributes-reserved:

Reserved attributes
-------------------

The :py:class:`~hdmf_zarr.backend.ZarrIO` backend defines a set of reserved attribute names defined in
:py:attr:`~hdmf_zarr.backend.ZarrIO.__reserve_attribute`. These reserved attributes are used to implement
functionality (e.g., links and object references, which are not natively supported by Zarr) and may be
added on any Group or Dataset in the file.

    ============================  ======================================================================================
    Reserved Attribute Name       Usage
    ============================  ======================================================================================
    zarr_link                     Attribute used to store links. See :ref:`sec-zarr-storage-links` for details.
    zarr_dtype                    Attribute used to specify the data type of a dataset. This is used to implement the
                                  storage of object references as part of datasets.
                                  See :ref:`sec-zarr-storage-references`
    ============================  ======================================================================================

In addition, the following reserved attributes are added to the root Group of the file only:

    ============================  ======================================================================================
    Reserved Attribute Name       Usage
    ============================  ======================================================================================
    .specloc                      Attribute storing the path to the Group where the scheme for the file are
                                  cached. See :py:attr:`~hdmf_zarr.backend.SPEC_LOC_ATTR`
    ============================  ======================================================================================


.. _sec-zarr-storage-links:

Links
-----

Similar to soft links in a file system, a link is an object in a Group that links to another Group or Dataset,
either within the same Zarr file or another external Zarr file. Links and reference are not natively supported by
Zarr but are implemented in :py:class:`~hdmf_zarr.backend.ZarrIO` in an OS independent fashion using the ``zarr_link``
reserved attribute (see :py:attr:`~hdmf_zarr.backend.ZarrIO.__reserve_attribute`) to store a list of dicts serialized
as JSON. Each dict (i.e., element) in the list defines a link, with each dict containing the following keys:

* ``name`` : Name of the link
* ``source`` : Relative path to the root of the Zarr file containing the linked object. For links
  pointing to an object within the same Zarr file, the value of source will be ``"."``. For external
  links that point to object in another Zarr file, the value of source will be the path to
  the other Zarr file relative to the root path of the Zarr file containing the link.
* ``path`` : Path to the linked object within the Zarr file identified by the ``source`` key
* ``object_id``: Object id of the reference object. May be None in case the referenced object
  does not have an assigned object_id (e.g., in the case we reference a dataset with a fixed
  name but without and assigned ``data_type`` (or ``neurodata_type`` in the case of NWB).
* ``source_object_id``: Object id of the source Zarr file indicated by the ``source`` key.
  The ``source`` should always have an ``object_id`` (at least if the ``source`` file is
  a valid HDMF formatted file).

For example:

.. code-block:: json

    "zarr_link": [
        {
            "name": "device",
            "source": ".",
            "path": "/general/devices/array",
            "object_id": "f6685427-3919-4e06-b195-ccb7ab42f0fa",
            "source_object_id": "6224bb89-578a-4839-b31c-83f11009292c"
        }
    ]

.. tabularcolumns:: |p{4cm}|p{11cm}|

.. table:: Mapping of links
    :class: longtable

    ============================  ======================================================================================
    HDMF Specification Key        Zarr
    ============================  ======================================================================================
    name                          Name of the link
    doc                           Not mapped; Stored in schema only
    target_type                   Not mapped. The target type is determined by the type of the target of the link
    ============================  ======================================================================================


.. hint::

    In Zarr, attributes are stored in JSON as part of the hidden ``.zattrs`` file in the folder defining
    the Group or Dataset.

.. hint::

    In :py:class:`~hdmf_zarr.backend.ZarrIO`, links are written by the
    :py:meth:`~hdmf_zarr.backend.ZarrIO.__write_link__` function, which also uses the helper functions
    i) :py:meth:`~hdmf_zarr.backend.ZarrIO._create_ref` to construct py:meth:`~hdmf_zarr.utils.ZarrRefernce`
    and ii) :py:meth:`~hdmf_zarr.backend.ZarrIO.__add_link__` to add a link to the Zarr file.
    :py:meth:`~hdmf_zarr.backend.ZarrIO.__read_links` then parses links and also uses the
    :py:meth:`~hdmf_zarr.backend.ZarrIO.__resolve_ref` helper function to resolve the paths stored in links.


.. _sec-zarr-storage-references:

Object References
-----------------

Object reference behave much the same way as Links, with the key difference that they are stored as part
of datasets or attributes. This approach allows for storage of large collections of references as values
of multi-dimensional arrays (i.e., the data type of the array is a reference type).

Storing object references in Datasets
-------------------------------------

To identify that a dataset contains object reference, the reserved attribute ``zarr_dtype`` is set to
``'object'`` (see also :ref:`sec-zarr-storage-attributes-reserved`). In this way, we can unambiguously
if a dataset stores references that need to be resolved.

Similar to Links, object references are defined via dicts, which are stored as elements of
the Dataset. In contrast to links, individual object reference do not have a ``name`` but are identified
by their location (i.e., index) in the dataset. As such, object references only have the ``source`` with
the relative path to the target Zarr file, and the ``path`` identifying the object within the source
Zarr file. The individual object references are defined in the
:py:class:`~hdmf_zarr.backend.ZarrIO` as py:class:`~hdmf_zarr.utils.ZarrReference` object created via
the :py:meth:`~hdmf_zarr.backend.ZarrIO._create_ref` helper function.

By default, :py:class:`~hdmf_zarr.backend.ZarrIO` uses the ``numcodecs.pickles.Pickle`` codec to
encode object references defined as py:class:`~hdmf_zarr.utils.ZarrReference` dicts in datasets.
Users may set the codec used to encode objects in Zarr datasets via the ``object_codec_class``
parameter of the :py:func:`~hdmf_zarr.backend.ZarrIO.__init__` constructor of
:py:class:`~hdmf_zarr.backend.ZarrIO`. E.g.,  we could use
``ZarrIO( ... , object_codec_class=numcodecs.JSON)`` to serialize objects using JSON.

Storing object references in Attributes
---------------------------------------

Object references are stored in a attributes as dicts with the following keys:

* ``zarr_dtype`` : Indicating the data type for the attribute. For object references
  ``zarr_dtype`` is set to ``"object"``
* ``value``: The value of the object references, i.e., here the py:class:`~hdmf_zarr.utils.ZarrReference`
  dictionary with the ``source``, ``path``, ``object_id``, and ``source_object_id`` keys defining
  the object reference, with the definition of the keys being the same as
  for :ref:`sec-zarr-storage-links`.

For example in NWB, the attribute ``ElectricalSeries.electrodes.table`` would be defined as follows:

.. code-block:: json

    "table": {
        "value": {
            "path": "/general/extracellular_ephys/electrodes",
            "source": ".",
            "object_id": "f6685427-3919-4e06-b195-ccb7ab42f0fa",
            "source_object_id": "6224bb89-578a-4839-b31c-83f11009292c"
        },
        "zarr_dtype": "object"
    }


.. _sec-zarr-storage-dtypes:

dtype mappings
--------------

The mappings of data types is as follows

    +--------------------------+------------------------------------+----------------+
    | ``dtype`` **spec value** | **storage type**                   | **size**       |
    +--------------------------+------------------------------------+----------------+
    |  * "float"               | single precision floating point    | 32 bit         |
    |  * "float32"             |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "double"              | double precision floating point    | 64 bit         |
    |  * "float64"             |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "long"                | signed 64 bit integer              | 64 bit         |
    |  * "int64"               |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "int"                 | signed 32 bit integer              | 32 bit         |
    |  * "int32"               |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "int16"               | signed 16 bit integer              | 16 bit         |
    +--------------------------+------------------------------------+----------------+
    |  * "int8"                | signed 8 bit integer               | 8 bit          |
    +--------------------------+------------------------------------+----------------+
    |  * "uint32"              | unsigned 32 bit integer            | 32 bit         |
    +--------------------------+------------------------------------+----------------+
    |  * "uint16"              | unsigned 16 bit integer            | 16 bit         |
    +--------------------------+------------------------------------+----------------+
    |  * "uint8"               | unsigned 8 bit integer             | 8 bit          |
    +--------------------------+------------------------------------+----------------+
    |  * "bool"                | boolean                            | 8 bit          |
    +--------------------------+------------------------------------+----------------+
    |  * "text"                | unicode                            | variable       |
    |  * "utf"                 |                                    |                |
    |  * "utf8"                |                                    |                |
    |  * "utf-8"               |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "ascii"               | ascii                              | variable       |
    |  * "str"                 |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "ref"                 | Reference to another group or      |                |
    |  * "reference"           | dataset. See                       |                |
    |  * "object"              | :ref:`sec-zarr-storage-references` |                |
    +--------------------------+------------------------------------+----------------+
    |  * compound dtype        | Compound data type                 |                |
    +--------------------------+------------------------------------+----------------+
    |  * "isodatetime"         | ASCII ISO8061 datetime string.     | variable       |
    |                          | For example                        |                |
    |                          | ``2018-09-28T14:43:54.123+02:00``  |                |
    +--------------------------+------------------------------------+----------------+


.. _sec-zarr-caching-specifications:

Caching format specifications
=============================

In practice it is useful to cache the specification a file was created with (including extensions)
directly in the Zarr file. Caching the specification in the file ensures that users can access
the specification directly if necessary without requiring external resources.
For the Zarr backend, caching of the schema is implemented as follows.

The :py:class:`~hdmf_zarr.backend.ZarrIO`` backend adds the reserved top-level group ``/specifications``
in which all format specifications (including extensions) are cached. The default name for this group is
defined in :py:attr:`~hdmf_zarr.backend.DEFAULT_SPEC_LOC_DIR` and caching of
specifications is implemented in ``ZarrIO.__cache_spec``.
The ``/specifications`` group contains for each specification namespace a subgroup
``/specifications/<namespace-name>/<version>`` in which the specification for a particular version of a namespace
are stored (e.g., ``/specifications/core/2.0.1`` in the case of the NWB core namespace at version 2.0.1).
The actual specification data is then stored as a JSON string in scalar datasets with a binary, variable-length string
data type. The specification of the namespace is stored in
``/specifications/<namespace-name>/<version>/namespace`` while additional source files are stored in
``/specifications/<namespace-name>/<version>/<source-filename>``. Here ``<source-filename>`` refers to the main name
of the source-file without file extension (e.g., the core namespace defines ``nwb.ephys.yaml`` as source which would
be stored in ``/specifications/core/2.0.1/nwb.ecephys``).

Consolidating Metadata
======================

Zarr allows users to consolidate all metadata for groups and arrays within the given store. By default, every file
will consolidate all metadata within into a single `.zmetadata` file, stored in the root group. This reduces the number of read
operations when retrieving certain metadata in read mode.

.. note::

    When updating a file, the consolidated metadata will also need to be updated via
    `zarr.consolidate_metadata(path)` to ensure the consolidated metadata is consistent
    with the file.
