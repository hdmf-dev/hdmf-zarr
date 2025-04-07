# HDMF-ZARR Changelog

## 0.11.1 (April 8, 2025)

### Changed
* Added scipy to optional dependencies to be compatible with HDMF 4.0. @rly [#261](https://github.com/hdmf-dev/hdmf-zarr/pull/261)
* Restricted numcodecs dependency to <0.16 due to incompatibility with the latest zarr<3 version. @rly [#270](https://github.com/hdmf-dev/hdmf-zarr/pull/270)

## 0.11.0 (January 17, 2025)

### Changed
* Adopted changelog format conventions: https://keepachangelog.com/en/1.0.0/ . @rly [#254](https://github.com/hdmf-dev/hdmf-zarr/pull/254)
* Made docs site point to latest stable release: https://hdmf-zarr.readthedocs.io/en/stable/ instead of "latest" tag. @rly [#254](https://github.com/hdmf-dev/hdmf-zarr/pull/254)
* Removed GitHub Actions workflow that automatically generated GitHub pre-releases on the "latest" tag on each commit to dev to simplify maintenance. @rly [#254](https://github.com/hdmf-dev/hdmf-zarr/pull/254)
* Clarified docs and updated links to say that only Zarr v2 is currently supported. @rly [#257](https://github.com/hdmf-dev/hdmf-zarr/pull/257)
* Removed `ZarrIO.get_zarr_parent_path` and `ZarrIO.is_zarr_file` methods. @rly [#256](https://github.com/hdmf-dev/hdmf-zarr/pull/256)
* Fixed bug in how links and references are stored in the Zarr file. They are now written as relative paths from the Zarr file, using "." to indicate the current file. This is how hdmf-zarr wrote internal links and references pre-0.10.0. @rly [#256](https://github.com/hdmf-dev/hdmf-zarr/pull/256)

## 0.10.0 (December 18, 2024)

### Enhancements
* Added initial refactor of export, supporting references and internal/external links from Zarr to Zarr. This will introduce breaking changes that could lead to existing exported files to be invalid. This update removes '.' as the object default file source. @mavaylon1 [#194](https://github.com/hdmf-dev/hdmf-zarr/pull/194)
* Added support for Pathlib paths. @mavaylon1 [#212](https://github.com/hdmf-dev/hdmf-zarr/pull/212)
* Updated packages used for testing and readthedocs configuration. @mavaylon1, @rly [#214](https://github.com/hdmf-dev/hdmf-zarr/pull/214)
* Add `force_overwite` parameter for `ZarrIO.__init__` to allow overwriting an existing file or directory. @oruebel [#229](https://github.com/hdmf-dev/hdmf-zarr/pull/229)
* Remove allowance of `hdmf.Array` in `__init__` of `AbstractZarrTableDataset` and `ZarrDataset` to be compatible with HDMF 4.0. @rly [#236](https://github.com/hdmf-dev/hdmf-zarr/pull/236)
* Remove support for python 3.8 and added testing for Python 3.13. @mavaylon1 [#240](https://github.com/hdmf-dev/hdmf-zarr/pull/240)
* Added `NWBZarrIO.read_nwb` convenience method to simplify reading an NWB file. @oruebel [#226](https://github.com/hdmf-dev/hdmf-zarr/pull/226)
* Updated optional dependency groups in `pyproject.toml` and GitHub Actions workflows. @rly, @mavaylon1 [#239](https://github.com/hdmf-dev/hdmf-zarr/pull/239)
* Applied black code formatter. @rly [#247](https://github.com/hdmf-dev/hdmf-zarr/pull/247)

### Bug Fixes
* Fix reading of cached specs and caching of specs during export. @rly [#232](https://github.com/hdmf-dev/hdmf-zarr/pull/232)
* Fix hiding of pynwb compatibility errors. @rly [242](https://github.com/hdmf-dev/hdmf-zarr/pull/242)


## 0.9.0 (September 16, 2024)

### Enhancements
* Added support for appending a dataset of references. @mavaylon1 [#203](https://github.com/hdmf-dev/hdmf-zarr/pull/203)
* NWBZarrIO load_namespaces=True by default. @mavaylon1 [#204](https://github.com/hdmf-dev/hdmf-zarr/pull/204)
* Added test for opening file with consolidated metadata from DANDI. @mavaylon1 [#206](https://github.com/hdmf-dev/hdmf-zarr/pull/206)
* Add dimension labels compatible with xarray. @mavaylon1 [#207](https://github.com/hdmf-dev/hdmf-zarr/pull/207)
* Added link_data --> clear_cache relationship to support repacking zarr nwbfiles: [#215](https://github.com/hdmf-dev/hdmf-zarr/pull/215)


## 0.8.0 (June 4, 2024)

### Bug Fixes
* Fixed bug when opening a file in with `mode=r+`. The file will open without using the consolidated metadata. @mavaylon1 [#182](https://github.com/hdmf-dev/hdmf-zarr/issues/182)
* Fixed bug on how we access scalar arrays. Added warning filter for Zarr deprecation of NestedDirectoryStore. Fixed bug on how we write a dataset of references. @mavaylon1 [#195](https://github.com/hdmf-dev/hdmf-zarr/pull/195)


## 0.7.0 (May 2, 2024)

### Enhancements
* Added support for python 3.12. @mavaylon1 [#172](https://github.com/hdmf-dev/hdmf-zarr/pull/172)
* Added support for forcing read of files without consolidated metadata using  `mode=r-` in `ZarrIO`. @oruebel [#183](https://github.com/hdmf-dev/hdmf-zarr/pull/183)
- Updated testing to not install in editable mode and not run `coverage` by default. @rly [#188](https://github.com/hdmf-dev/hdmf-zarr/pull/188)

### Docs
* Removed `linkable` from the documentation to keep in line with `hdmf-schema-language`. @mavaylon1 [#180](https://github.com/hdmf-dev/hdmf-zarr/pull/180)

### Bug Fixes
* Fixed bug in `ZarrIO.__open_file_consolidated` that led to remote files being opened without consolidated metadata. @oruebel  [#184](https://github.com/hdmf-dev/hdmf-zarr/pull/184)
* Fixed minor bug where `ZarrIO.__open_file_consolidated` used properties of `ZarrIO` instead of the provided input parameters. @oruebel [#183](https://github.com/hdmf-dev/hdmf-zarr/pull/183)


## 0.6.0 (February 21, 2024)

### Enhancements
* Enhanced `ZarrIO` and `ZarrDataIO` to infer io settings (e.g., chunking and compression) from HDF5 datasets to preserve storage settings on export if possible @oruebel [#153](https://github.com/hdmf-dev/hdmf-zarr/pull/153)
* Updated writing references in compound datasets to same-sized array, rather than iteratively as an array of lists. @sneakers-the-rat [#146](https://github.com/hdmf-dev/hdmf-zarr/pull/146)

### Bug Fixes
* Fixed bug when converting HDF5 datasets with unlimited dimensions @oruebel [#155](https://github.com/hdmf-dev/hdmf-zarr/pull/155)
* Fixed bug resolving bytes dtype when exporting from Zarr to Zarr @oruebel [#161](https://github.com/hdmf-dev/hdmf-zarr/pull/161)
* Adjusted gallery tests to not fail on deprecation warnings from pandas. @rly [#157](https://github.com/hdmf-dev/hdmf-zarr/pull/157)
* Fixed bug in `pyproject.toml` where duplicate versions of `numcodec` where specified. @oruebel [#163](https://github.com/hdmf-dev/hdmf-zarr/pull/163)

### Internal Fixes
* Updated actions in `deploy_release.yml` workflow to avoid use of deprecated Node.js 16. @oruebel [#165](https://github.com/hdmf-dev/hdmf-zarr/pull/165)


## 0.5.0 (December 8, 2023)

### Enhancements
* Added a new default to consolidate metadata in order more efficeintly traverse storage contents. @mavaylon1 [#142](https://github.com/hdmf-dev/hdmf-zarr/pull/142)
* Fix linking for FSSpec and support passing of `storage_options` required reading data from S3 #138. @alejoe91 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/138)
* Updated versioning to hatch-vcs and deprecated setup.py in full transition to `pyproject.toml`. @mavaylon1 [#143](https://github.com/hdmf-dev/hdmf-zarr/pull/143)

## 0.4.0 (October 3, 2023)

### Enhancements
* Enhanced ZarrIO to resolve object references lazily on read similar to HDMF's `HDF5IO` backend. @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)
* Updated storage of references to also save the ``object_id`` and ``source_object_id``. While not strictly necessary this information is useful for validation and rigor of references. @oruebel [#57](https://github.com/hdmf-dev/hdmf-zarr/pull/57)

### New Features
* Added parallel write support for the ``ZarrIO`` for datasets wrapped with ``GenericDataChunkIterator``. @CodyCBakerPhD [#118](https://github.com/hdmf-dev/hdmf-zarr/pull/118) @oruebel [#128](https://github.com/hdmf-dev/hdmf-zarr/pull/128)

### Dependencies
* Updated HDMF and PyNWB version to the most recent release @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)
* Updated minimum Python version from 3.7 to 3.8 @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)
* Added ``threadpoolctl`` dependency for parallel write. @CodyCBakerPhD [#118](https://github.com/hdmf-dev/hdmf-zarr/pull/118)
* Added support for specifying optional dependencies and add optional dependency for ``tqdm`` used in parallel write. @CodyCBakerPhD [#118](https://github.com/hdmf-dev/hdmf-zarr/pull/118)

### Bug fixes
* Fixed error in deploy workflow. @mavaylon1 [#109](https://github.com/hdmf-dev/hdmf-zarr/pull/109)
* Fixed build error for ReadtheDocs by degrading numpy for python 3.7 support. @mavaylon1 [#115](https://github.com/hdmf-dev/hdmf-zarr/pull/115)
* Fixed bug in the resolution of references to Containers. Previously references were only resolved to Builders. @mavaylon1 [#120](https://github.com/hdmf-dev/hdmf-zarr/pull/120)


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
* Updated gallery tests to use test_gallery.py and necessary package dependencies
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
