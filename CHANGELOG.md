# HDMF-ZARR Changelog

## 0.1.7 (Upcoming)

### Bugs
* Use path relative to the current Zarr file in the definition of links and references to avoid breaking
  links when moving Zarr files @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Fix bugs in requirements defined in setup.py @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Fix bug regarding Sphinx external links @mavaylon1 [#53](https://github.com/hdmf-dev/hdmf-zarr/pull/53)
* Updated gallery tests to use test_gallery.py and necessary package dependcies @mavaylon1 [#53](https://github.com/hdmf-dev/hdmf-zarr/pull/53)
* Update dateset used in conversion tutorial, which caused warnings  @oruebel [#56](https://github.com/hdmf-dev/hdmf-zarr/pull/56)

### Docs
* Add tutorial illustrating how to create a new NWB file with NWBZarrIO @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Add docs for describing the mapping of HDMF schema to Zarr storage @oruebel [#48](https://github.com/hdmf-dev/hdmf-zarr/pull/48)
* Remove dependency on ``dandi`` library for data download in the conversion tutorial by storing the NWB files as local resources @oruebel [#61](https://github.com/hdmf-dev/hdmf-zarr/pull/61)

## 0.1.0 

### New features

- Created new optional Zarr-based I/O backend for writing files using Zarr's `zarr.store.DirectoryStore` backend, including support for iterative write, chunking, compression, simple and compound data types, links, object references, namespace and spec I/O.
