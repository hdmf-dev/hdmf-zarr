# Add the zarr.Array to the HDMF docval macro os that it can pass as array_data
def configure_hdmf_docval_macros():
    """
    Private helper function to add zarr.Array to the HDMF docval macros.

    We do this in a function to avoid pulling zarr and hdmf into main
    namespace of the package
    """
    import zarr
    return [('array_data', zarr.Array)]