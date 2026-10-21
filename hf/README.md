---
pretty_name: South Australia planning and land layers
license: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/
tags:
  - geospatial
  - planning
  - zoning
  - land-use
  - south-australia
---

# South Australia planning and land layers

Statewide planning and land layers published by the Department for Housing and Urban Development on Data.SA, as GeoParquet
and vector tiles, checked weekly and rebuilt when a source changes by
[AlreadyOpen/sa-planning](https://github.com/milleleaf/sa-planning). Every feature and every field of each source is kept.

| Layer | Source | Holds |
|---|---|---|
| `zones` | [Planning and Design Code Zones](https://data.sa.gov.au/data/dataset/8321117d-2712-4912-9c47-a52ddb6b527f) | P&D Code zones, all of SA |
| `overlays` | [Planning and Design Code Overlays](https://data.sa.gov.au/data/dataset/ef82af6a-b57b-426b-949e-1ff97969fc1c) | Every P&D Code overlay in one layer (heritage, hazards, flooding, noise, height and more); filter on `name` |
| `land-use` | [Land Use Generalised (2025)](https://data.sa.gov.au/data/dataset/9712e707-1a7a-464e-a4c3-980f40770d48) | Generalised land use |
| `height-limits` | [Building Height Limits](https://data.sa.gov.au/data/dataset/4c4edb70-28fc-448f-a88f-29ba8f854b79) | Statutory maximum building heights (storeys, metres) |
| `climate-zones` | [Energy Efficiency (Climate) Zones](https://data.sa.gov.au/data/dataset/1ae7c6ac-1c07-46a7-be09-b060a53752d7) | NCC energy-efficiency climate zones |
| `energy-concession-areas` | [Energy Efficiency Concession Areas](https://data.sa.gov.au/data/dataset/131403e0-3f15-457d-a73f-a607b35f7e73) | Areas with energy-rating concessions |
| `bushfire-protection-areas` | [Bushfire Protection Areas](https://data.sa.gov.au/data/dataset/30e275dd-a6f3-4af5-8b8a-6f4919ff6fe7) | Bushfire risk areas used by the building rules |
| `earthquake-hazard-zones` | [Earthquake Hazard Zones](https://data.sa.gov.au/data/dataset/98259e9b-480f-401f-b715-f52d0c17cb72) | Building-code earthquake hazard factor zones |
| `corrosion-areas` | [Corrosion Environment Areas](https://data.sa.gov.au/data/dataset/00077ae8-57b2-40b7-b4b5-491872163d70) | Building-code corrosion environments |

Per layer:

- **`<layer>.parquet`** (in this dataset): GeoParquet, every feature, every field as published, geometry in `geom`.
- **`<layer>.pmtiles`** (on the [bucket](https://huggingface.co/buckets/milleleaf/sa-planning), read by browsers): vector
  tiles, one layer named after the file, zooms 4 to 14, every field plus `fid` (the feature's row number in the Parquet file,
  from 0). **Zoom 14 holds every feature** at full detail: no feature or tile size limit, no tiny-polygon reduction, no
  simplification. Zooms 4 to 13 may leave out features in dense areas and simplify shapes, so those tiles stay small. A
  polygon too thin to survive the zoom-14 grid (a sliver a few centimetres wide) is also given as a point on its surface,
  with `tiny_polygon_point: true`; `index.json` counts them per layer.

`index.json` holds the counts, each source's URL, Last-Modified and size, and the CRS. `manifest.json` lists every file's
sha256. Geometry is the GDA2020 (EPSG:7844) file of each source, which web maps can use as WGS 84 (they differ by less than
2 m).

**GDA94 copies (Kaggle only).** Each source zip also holds the same features in GDA94 (EPSG:4283). They are not on Hugging
Face; they are in the Kaggle mirror, [helenkwok/sa-planning](https://www.kaggle.com/datasets/helenkwok/sa-planning), folder
`gda94/`: each zip's `<stem>_GDA94.geojson` and `<stem>_GDA94_metadata.html`, copied out byte for byte (no reprojection, no
field changes). `manifest.json` lists their sha256 too, and `index.json` counts their features (`<layer>_gda94`).

## Sources and terms

Data from the Department for Housing and Urban Development, Government of South Australia, published on
[Data.SA](https://data.sa.gov.au) under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
(the `License.txt` inside each zip, dated 2015, names CC BY 3.0 Australia). Changes: converted to GeoParquet and vector
tiles; nothing removed. Provided as is, with no warranty, not endorsed by the Government of South Australia. Not a planning
or legal record: check the [SA Property and Planning Atlas](https://sappa.plan.sa.gov.au/) and the Planning and Design Code.
