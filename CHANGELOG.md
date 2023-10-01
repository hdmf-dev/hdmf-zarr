# HDMF-ZARR Changelog

## 0.4.0 (Upcoming)

### Enhancements
* Enhanced ZarrIO to resolve object references lazily on read similar to HDMF's `HDF5IO` backend @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)

### Dependencies
* Updated HDMF and PyNWB version to the most recent release @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)
* Updated minimum Python version from 3.7 to 3.8 @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)

### Bug fixes
* Fixed error in deploy workflow. @mavaylon1 [#109](https://github.com/hdmf-dev/hdmf-zarr/pull/109)
* Fixed build error for ReadtheDocs by degrading numpy for python 3.7 support. @mavaylon1 [#115](https://github.com/hdmf-dev/hdmf-zarr/pull/115)


## 0.3.0 (July 21, 2023)

### New Features
* Added support, tests, and docs for using ``DirectoryStore``, ``TempStore``, and
  ``NestedDirectoryStore`` Zarr storage backends with ``ZarrIO`` and ``NWBZarrIO``. 
  @oruebel [#62](https://github.com/hdmf-dev/hdmf-zarr/pull/62)

### Minor enhancements
* Updated handling of references on read to simplify future integration of file-based Zarr 
  stores (e.g., ZipStore or database stores). @oruebel [#62](https://github.com/hdmf-dev/hdmf-zarr/pull/62)
* Added ``can_read`` classmethod to ``ZarrIO``. @bendichter [#97](https://github.com/hdmf-dev/hdmf-zarr/pull/97)

### Test suite enhancements
* Modularized unit tests to simplify running tests for multiple Zarr storage backends.
  @oruebel [#62](https://github.com/hdmf-dev/hdmf-zarr/pull/62)
* Fixed CI testing of minimum and optional installation requirement. @rly
  [#99](https://github.com/hdmf-dev/hdmf-zarr/pull/99)
* Updated tests to handle upcoming changes to ``HDMFIO``. @rly 
  [#102](https://github.com/hdmf-dev/hdmf-zarr/pull/102)


### Docs
* Added developer documentation on how to integrate new storage backends with ZarrIO. @oruebel
  [#62](https://github.com/hdmf-dev/hdmf-zarr/pull/62)

### API Changes
* Removed unused ``filepath`` argument from ``ZarrIO.get_builder_exists_on_disk`` [#62](https://github.com/hdmf-dev/hdmf-zarr/pull/62)

### Bug fixes
* Fixed error in nightly CI. @rly [#93](https://github.com/hdmf-dev/hdmf-zarr/pull/93)

## 0.2.0 (January 6, 2023)

### Bugs
* Updated the storage of links/references to use paths relative to the current Zarr file to avoid breaking
  links/reference when moving Zarr files @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Fixed bugs in requirements defined in setup.py @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Fixed bug regarding Sphinx external links @mavaylon1 [#53](https://github.com/hdmf-dev/hdmf-zarr/pull/53)
* Updated gallery tests to use test_gallery.py and necessary package dependcies 
  @mavaylon1 [#53](https://github.com/hdmf-dev/hdmf-zarr/pull/53)
* Updated dateset used in conversion tutorial, which caused warnings 
  @oruebel [#56](https://github.com/hdmf-dev/hdmf-zarr/pull/56)

### Docs
* Added tutorial illustrating how to create a new NWB file with NWBZarrIO 
  @oruebel [#46](https://github.com/hdmf-dev/hdmf-zarr/pull/46)
* Added docs for describing the mapping of HDMF schema to Zarr storage 
  @oruebel [#48](https://github.com/hdmf-dev/hdmf-zarr/pull/48)
* Added ``docs/gallery/resources`` for storing local files used by the tutorial galleries 
  @oruebel [#61](https://github.com/hdmf-dev/hdmf-zarr/pull/61)
* Removed dependency on ``dandi`` library for data download in the conversion tutorial by storing the NWB files as 
  local resources @oruebel [#61](https://github.com/hdmf-dev/hdmf-zarr/pull/61)

## 0.1.0 (August 23, 2022)

### New features

* Created new optional Zarr-based I/O backend for writing files using Zarr's `zarr.store.DirectoryStore` backend, 
  including support for iterative write, chunking, compression, simple and compound data types, links, object 
  references, namespace and spec I/O.
