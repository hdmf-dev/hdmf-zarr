Resources
=========

sub_anm00239123_ses_20170627T093549_ecephys_and_ogen.nwb
--------------------------------------------------------

This NWB file was downloaded from `Dandiset 000009 <https://dandiarchive.org/dandiset/000009/0.220126.1903>`_
The file was modified to replace ``:`` characters used in the name of the ``ElectrodeGroup`` called ``ADunit: 32`` in
``'general/extracellular_ephys/`` to ``'ADunit_32'``. The dataset ``general/extracellular_ephys/electrodes/group_name``
as part of the electrodes table was updated accordingly to list the appropriate group name. This is to avoid issues
on Windows file systems that do not support ``:`` as part of folder names. The asset can be downloaded from DANDI via:

.. code-block:: python
    :linenos:

    from dandi.dandiapi import DandiAPIClient
    dandiset_id = "000009"
    filepath = "sub-anm00239123/sub-anm00239123_ses-20170627T093549_ecephys+ogen.nwb"   # ~0.5MB file
    with DandiAPIClient() as client:
        asset = client.get_dandiset(dandiset_id, 'draft').get_asset_by_path(filepath)
        s3_path = asset.get_content_url(follow_redirects=1, strip_query=True)
        filename = os.path.basename(asset.path)
    asset.download(filename)

