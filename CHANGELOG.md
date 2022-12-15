# HDMF-ZARR Changelog

## 0.1.x (Upcoming)
- Add docs for describing the mapping of HDMF schema to Zarr storage

## 0.1.0 

### New features

- Created new optional Zarr-based I/O backend for writing files using Zarr's `zarr.store.DirectoryStore` backend, including support for iterative write, chunking, compression, simple and compound data types, links, object references, namespace and spec I/O.
