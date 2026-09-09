# Investigation: Automatic reset_parent for HDF5 Objects During Zarr Export

## Issue Description
From issue: When adding HDF5 objects from one file to another and exporting to Zarr, users must manually call `reset_parent()` on the objects. Otherwise, Zarr attempts to create links to HDF5 objects, which is not supported.

## Investigation Findings

### Problem Analysis
1. When objects are read from an HDF5 file, they have `container_source` and `parent` attributes set
2. When these objects are added to a container from a different file and exported to Zarr, HDMF attempts to create links
3. Cross-backend links (HDF5 → Zarr) are not supported, causing export failures

### Why Automatic `reset_parent()` Doesn't Work

The investigation revealed fundamental limitations:

1. **`container_source` is immutable**: Once set, HDMF doesn't allow reassigning `container_source` (by design, to prevent data corruption)
   ```python
   @container_source.setter
   def container_source(self, source):
       if self.__container_source is not None:
           raise Exception('cannot reassign container_source')
   ```

2. **`reset_parent()` doesn't clear `container_source`**: Calling `reset_parent()` only clears the parent reference, not the source

3. **HDMF's link detection logic**: The ObjectMapper checks `container_source` to determine whether to create links:
   ```python
   elif value.container_source:  # make a link to an existing container
       if (value.container_source != parent_container.container_source
               or value.parent is not parent_container):
   ```

4. **Timing issue**: If we call `reset_parent()` during export (after containers are already assembled), we create orphaned containers that fail HDMF's validation

### Attempted Solutions

1. **Automatic `reset_parent()` in export()**: Failed because:
   - Can't clear `container_source` 
   - Creates orphaned containers if called after parent assignment
   - Too late in the process to be effective

2. **Selective reset based on source comparison**: Failed because:
   - Still can't clear `container_source`
   - Complex logic needed to avoid breaking valid scenarios

3. **Manual `container_source` clearing**: Not possible due to HDMF's immutability constraint

## Recommended Solution

This issue requires changes at the **HDMF core level**, not hdmf-zarr. Specifically:

### Option 1: HDMF Enhancement
Modify HDMF's `ObjectMapper` to recognize cross-backend export scenarios when `export=True` and treat containers from different backend sources as new objects rather than creating links.

### Option 2: New HDMF API
Add a method like `reset_for_export()` that clears both `parent` and `container_source` in a controlled way, specifically for cross-backend export scenarios.

### Option 3: Documentation (Short-term)
Clearly document that users MUST call `reset_parent()` on objects from different HDF5 files before adding them to a container that will be exported to Zarr. However, note that even this has limitations due to `container_source` persistence.

## Current Workaround

Users experiencing this issue should:

1. Call `reset_parent()` on objects from file B BEFORE adding them to file A's container
2. Be aware that this doesn't fully solve the problem if `container_source` is checked
3. Consider reconstructing objects instead of directly transferring them between files

## Next Steps

1. Open discussion with HDMF team about proper solution
2. Consider if this is actually a bug in HDMF's export logic
3. Document current limitations clearly in hdmf-zarr

## References

- Original issue: [Feature]: When adding an HDF5 object and exporting across backends, `reset_parent` should be called automatically
- Related helpdesk discussion: https://github.com/NeurodataWithoutBorders/helpdesk/discussions/94
- HDMF ObjectMapper code: `hdmf/build/objectmapper.py`
- HDMF Container code: `hdmf/container.py`
