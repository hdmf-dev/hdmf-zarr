.. _sec-zarr-storage:

=====================
Storage Specification
=====================

hdmf-zarr currently uses the Zarr :zarr-docs:`LocalStore <api/zarr/storage/index.html#zarr.storage.LocalStore>`,
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
    dtype                         Data type of the Zarr dataset (see `dtype mappings`_ table) and stored in reserved attributes
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

    Attributes are stored as JSON documents in Zarr (using the LocalStore). As such, all attributes
    must be JSON serializable. The :py:class:`~hdmf_zarr.backend.ZarrIO` backend attempts to cast types
    (e.g., numpy arrays) to JSON serializable types as much as possible, but not all possible types may
    be supported. Float ``NaN``, ``Infinity``, and ``-Infinity`` values are written as the bare tokens
    ``NaN``, ``Infinity``, and ``-Infinity``, following zarr-python. These tokens are a zarr-python
    extension to JSON rather than part of the JSON standard, so a store containing them is readable by
    Python's :py:mod:`json` module and rejected by strict JSON parsers. Writing them this way keeps a
    float distinct from a string holding the same text, and keeps hdmf-zarr consistent with any other
    tool reading the store through zarr-python.

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
    ``_LINKS``                    Attribute on Groups used to store links. See :ref:`sec-zarr-storage-links`.
    ``_DTYPE``                    Attribute on Datasets used to specify the data type. Set to
                                  ``"object_reference"`` for reference datasets. See :ref:`sec-zarr-storage-references`.
    ``_REFERENCE_FIELDS``         Attribute on compound Datasets listing field names that contain object references.
    ============================  ======================================================================================

.. note::

    Files written with hdmf-zarr < 0.14 (Zarr v2) use the attribute names ``zarr_link`` and ``zarr_dtype``
    instead. These are still recognized on read so that legacy files can be opened with
    :py:class:`~hdmf_zarr.backend_zarrv2.ZarrV2IO`. See :ref:`sec-zarr-storage-legacy` for the old definitions.

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
Zarr but are implemented in :py:class:`~hdmf_zarr.backend.ZarrIO` in an OS independent fashion using the ``_LINKS``
reserved attribute (see :py:attr:`~hdmf_zarr.backend.ZarrIO.__reserve_attribute`) to store a list of dicts serialized
as JSON. Each dict (i.e., element) in the list defines a link, with each dict containing the following keys:

* ``name`` : Name of the link
* ``source`` : Relative path to the root of the Zarr file containing the linked object. For links
  pointing to an object within the same Zarr file, the value of source will be ``"."``. For external
  links that point to object in another Zarr file, the value of source will be the path to
  the other Zarr file relative to the root path of the Zarr file containing the link.
* ``path`` : Path to the linked object within the Zarr file identified by the ``source`` key

For example:

.. code-block:: json

    "_LINKS": [
        {
            "name": "device",
            "source": ".",
            "path": "/general/devices/array"
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

    In Zarr, attributes are stored in JSON in the ``attributes`` field of the ``zarr.json`` file in the folder
    defining the Group or Dataset.

.. hint::

    In :py:class:`~hdmf_zarr.backend.ZarrIO`, links are written by the
    :py:meth:`~hdmf_zarr.backend.ZarrIO.__write_link__` function, which also uses the helper functions
    i) :py:meth:`~hdmf_zarr.backend.ZarrIO._create_ref` to construct py:meth:`~hdmf_zarr.utils.ZarrReference`
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

To identify that a dataset contains object references, the reserved attribute ``_DTYPE`` is set to
``'object_reference'`` (see also :ref:`sec-zarr-storage-attributes-reserved`). In this way, we can
unambiguously determine if a dataset stores references that need to be resolved.

Each element of a reference dataset is stored as a **plain target path string** (e.g.,
``"/general/extracellular_ephys/electrodes"``) in a variable-length string (``StringDType``) array.
Since ``_DTYPE = "object_reference"`` already marks the dataset as containing references, there is no
need to wrap each value in a dict. The ``source`` defaults to ``"."`` (same file). For future
cross-file references, the format can be extended to store dicts instead of plain strings.

Object references are created via :py:meth:`~hdmf_zarr.backend.ZarrIO._create_ref` and resolved
via :py:meth:`~hdmf_zarr.backend.ZarrIO.resolve_ref`.

Storing object references in Attributes
---------------------------------------

Object references are stored in attributes as dicts with a ``_REFERENCE`` wrapper key containing a dict
with ``source`` and ``path`` keys:

For example in NWB, the attribute ``ElectricalSeries.electrodes.table`` would be defined as follows:

.. code-block:: json

    "table": {
        "_REFERENCE": {
            "path": "/general/extracellular_ephys/electrodes",
            "source": "."
        }
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
    |  * "ascii"               | unicode. Zarr v3 has no            | variable       |
    |  * "bytes"               | byte-string data type, so these    |                |
    |                          | are stored as UTF-8 text and read  |                |
    |                          | back as ``str``. Writing bytes     |                |
    |                          | that are not valid UTF-8 raises    |                |
    |                          | ``ValueError``.                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * "object"              | Reference to another group or      |                |
    |  * a mapping with        | dataset. See                       |                |
    |    ``target_type`` and   | :ref:`sec-zarr-storage-references` |                |
    |    ``reftype: object``   |                                    |                |
    +--------------------------+------------------------------------+----------------+
    |  * compound dtype        | Compound data type. Uses zarr v3's |                |
    |                          | zarr v3 ``struct`` data type.      |                |
    |                          | Reference fields marked with       |                |
    |                          | ``_REFERENCE_FIELDS`` attribute.   |                |
    +--------------------------+------------------------------------+----------------+
    |  * "isodatetime"         | unicode ISO 8601 datetime string.  | variable       |
    |                          | For example                        |                |
    |                          | ``2018-09-28T14:43:54.123+02:00``  |                |
    +--------------------------+------------------------------------+----------------+

.. note::

    Compound data types use zarr v3's ``struct`` data type, which carries full field information
    (names and types).

    String and reference fields within compound dtypes are stored as fixed-length Unicode strings
    (``FixedLengthUTF32``). The string length is dynamically sized to fit the actual data, with a
    minimum of :py:attr:`~hdmf_zarr.backend.COMPOUND_DTYPE_MIN_STRING_LENGTH` characters.
    Reference fields store plain target path strings (not JSON dicts).

    If a compound dataset contains reference fields, the ``_REFERENCE_FIELDS`` attribute lists
    which field names contain references. For example: ``_REFERENCE_FIELDS = ["electrode", "group"]``.

.. note::

    Scalar datasets are stored as zero-dimensional arrays with shape ``()``. The dtype matches the
    original data type (numeric scalars preserve their native dtype; strings use ``StringDType``).
    Scalar object references and scalar compound datasets are stored the same way.


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
will consolidate all metadata within into the ``zarr.json`` file of the root group. This reduces the number of read
operations when retrieving certain metadata in read mode.

.. note::

    When updating a file, the consolidated metadata will also need to be updated via
    `zarr.consolidate_metadata(path)` to ensure the consolidated metadata is consistent
    with the file.

.. _sec-zarr-storage-legacy:

Legacy Zarr v2 Convention
=========================

Files written with hdmf-zarr < 0.14 use Zarr v2 and an older attribute convention. These files are
read-only in hdmf-zarr >= 0.14 via :py:class:`~hdmf_zarr.backend_zarrv2.ZarrV2IO` and
:py:class:`~hdmf_zarr.nwb_zarrv2.NWBZarrV2IO`, and can be converted to the current convention with
:py:meth:`~hdmf_zarr.nwb_zarrv2.NWBZarrV2IO.convert_to_v3`. The old definitions are recorded here for
reference when debugging legacy data.

hdmf-zarr 0.13 and earlier encode object datasets with the pickle codec by default, so most of these
files hold at least one pickle-encoded dataset (an electrodes table's object-reference columns, for
instance). Decoding pickle executes arbitrary code, so both reading and converting refuse it and raise
``UnsafePickleCodecError``. Pass ``allow_pickle=True`` for a source you trust::

    NWBZarrV2IO.read_nwb("old_v2.nwb.zarr", allow_pickle=True)
    NWBZarrV2IO.convert_to_v3("old_v2.nwb.zarr", "new_v3.nwb.zarr", allow_pickle=True)

    ============================  ======================================================================================
    Legacy Attribute Name         Usage
    ============================  ======================================================================================
    ``zarr_link``                 Attribute on Groups used to store links. Each entry is a dict with ``name``,
                                  ``source``, and ``path`` keys. Replaced by ``_LINKS``.
    ``zarr_dtype``                Attribute on Datasets specifying the data type. Set to ``"object"`` for reference
                                  datasets, ``"scalar"`` for scalar datasets, and to a list of ``{"name", "dtype"}``
                                  dicts for compound datasets. Replaced by ``_DTYPE``, zero-dimensional arrays for
                                  scalars, and the zarr v3 ``struct`` data type together with
                                  ``_REFERENCE_FIELDS``.
    ============================  ======================================================================================

Object references in datasets were stored as dicts with ``source``, ``path``, ``object_id``, and
``source_object_id`` keys, written to an object-dtype array (Zarr v2) or as JSON strings. Object
references in attributes were stored as a dict with a ``zarr_dtype`` key set to ``"object"`` and a
``value`` key holding the reference dict:

.. code-block:: json

    "table": {
        "value": {
            "source": ".",
            "path": "/general/extracellular_ephys/electrodes",
            "object_id": "f6685427-3919-4e06-b195-ccb7ab42f0fa",
            "source_object_id": "6224bb89-578a-4839-b31c-83f11009292c"
        },
        "zarr_dtype": "object"
    }

In the current convention this is written as ``{"_REFERENCE": {"source": ".", "path": "..."}}``.
