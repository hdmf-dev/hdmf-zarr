Resources
=========

sub-healthy-simulated-beta_ses-162_ecephys.nwb
--------------------------------------------------------

This NWB file was downloaded from `Dandiset 001333 <https://dandiarchive.org/dandiset/001333/0.250327.2220>`_

.. code-block:: python
    :linenos:

    import os
    from dandi.dandiapi import DandiAPIClient

    dandiset_id = "001333"
    filepath = "sub-healthy-simulated-beta/sub-healthy-simulated-beta_ses-162_ecephys.nwb"   # 220 KiB file
    with DandiAPIClient() as client:
        asset = client.get_dandiset(dandiset_id, 'draft').get_asset_by_path(filepath)

    s3_path = asset.get_content_url(follow_redirects=1, strip_query=True)
    filename = os.path.basename(asset.path)
    asset.download(filename)
