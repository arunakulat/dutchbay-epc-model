# changelog.d/boundary-clip-segfault.fixed.md
- **`boundary_clip.clip_to_polygon` no longer segfaults on a loaded polygon** — the natural
  composition `clip_to_polygon(polygon=load_polygon(path))` crashed the interpreter (exit 139)
  inside rasterio's C extension (`mask -> raster_geometry_mask -> geometry_window -> bounds`).
  Root cause was a double extraction, not a rasterio bug: `load_polygon` already returns
  extracted geometries, and `clip_to_polygon` re-extracted them; `_extract_geometries` mistook
  the geometry *list* for a bare ring coordinate list and wrapped it into a malformed
  `{"type": "Polygon", "coordinates": [ {geom} ]}`, whose nested mapping GDAL's coordinate
  bounds walk dereferenced as a C double. `_extract_geometries` is now idempotent (a list of
  geometry/feature mappings is re-extracted, not wrapped), and a pure-Python coordinate
  validator (`_validate_geometry`) rejects any geometry whose coordinates hide a mapping,
  string or short position with a catchable `ValueError` before it can reach the C extension
  (CESSPIT fail-loud). Add-only GIS/reporting layer; `finance/` and `analytics/` finance paths
  are untouched and the canonical KPIs stay byte-identical.
