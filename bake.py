"""South Australia planning and land layers from Data.SA (Department for Housing and Urban Development, CC BY 4.0), as
GeoParquet and vector tiles. Every feature and every field is kept; geometry is the GDA2020 (EPSG:7844) file of each zip, which
web maps can use as WGS 84 (they differ by under 2 m). The GDA94 copy in each zip is the same features in the older datum:
  gda94/<stem>_GDA94.geojson (+ its _metadata.html)  copied out of the zip byte for byte (no reprojection, no field changes);
                      published to Kaggle only (publish.KAGGLE_FILES), counted as <layer>_gda94
  <layer>.parquet     GeoParquet, every feature, every field as published (+ `geom`)
  <layer>.pmtiles     vector tiles, one layer named <layer>, zooms 4 to 14, every field. Zoom 14 holds EVERY feature at full
                      detail (no feature or size limit, no tiny-polygon reduction, no simplification); zooms 4 to 13 may thin
                      dense areas and simplify shapes (tippecanoe --drop-densest-as-needed) so tiles stay small. Built as two
                      tile sets joined with tile-join; the bake fails unless zoom 14 holds every feature (counted by `fid`,
                      the feature's row number in <layer>.parquet).
index.json: counts (rows per layer, features at zoom 14 per layer) and `sources` (each zip's URL, Last-Modified and size).
The sources are checked weekly: when no zip has changed since the published index.json, nothing is baked (REBAKE=1 bakes
anyway). Usage: python3 bake.py [layer ...]   (default: every layer)"""
import datetime, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request, zipfile
import duckdb
import sources

BASE = 'https://www.dptiapps.com.au/dataportal/'
# layer -> (file stem on dptiapps, Data.SA dataset id)
LAYERS = {
    'zones': ('PDCodeZones', '8321117d-2712-4912-9c47-a52ddb6b527f'),
    'overlays': ('PDCodeOverlays', 'ef82af6a-b57b-426b-949e-1ff97969fc1c'),
    'land-use': ('LandUseGeneralised2025', '9712e707-1a7a-464e-a4c3-980f40770d48'),
    'height-limits': ('BuildingHeightLimits', '4c4edb70-28fc-448f-a88f-29ba8f854b79'),
    'climate-zones': ('EnergyEfficiencyClimateZones', '1ae7c6ac-1c07-46a7-be09-b060a53752d7'),
    'energy-concession-areas': ('EnergyEfficiencyConcessionAreas', '131403e0-3f15-457d-a73f-a607b35f7e73'),
    'bushfire-protection-areas': ('BushfireProtectionAreas', '30e275dd-a6f3-4af5-8b8a-6f4919ff6fe7'),
    'earthquake-hazard-zones': ('EarthquakeHazardZones', '98259e9b-480f-401f-b715-f52d0c17cb72'),
    'corrosion-areas': ('CorrosionEnvironmentAreas', '00077ae8-57b2-40b7-b4b5-491872163d70'),
}
UA = {'User-Agent': 'AlreadyOpen sa-planning (https://github.com/milleleaf/sa-planning)'}
REPO = 'milleleaf/sa-planning'
MINZOOM, MAXZOOM = 4, 14
url = lambda layer: f'{BASE}{LAYERS[layer][0]}_geojson.zip'


def retry(f, tries=4):
    """dptiapps once timed out from a runner (2026-10-10) that it had served an hour earlier: try again after 1, 2, 4 min"""
    for i in range(tries):
        try: return f()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code < 500 or i == tries - 1: raise
            print(f'::warning::{e}; retrying in {60 << i} s', flush=True); time.sleep(60 << i)


def head(layer):
    def get():
        with urllib.request.urlopen(urllib.request.Request(url(layer), method='HEAD', headers=UA), timeout=120) as r:
            return {'url': url(layer), 'last_modified': r.headers['Last-Modified'], 'bytes': int(r.headers['Content-Length'])}
    return retry(get)


def published():
    try: return json.load(urllib.request.urlopen(f'https://huggingface.co/buckets/{REPO}/resolve/index.json', timeout=60))
    except urllib.error.HTTPError as e:
        if e.code in (401, 404): return None
        raise


def download(layer, src):
    """the cached zip when its size and Last-Modified match the server's, else a fresh download"""
    p = os.path.join(sources.CACHE, os.path.basename(src['url'])); meta = p + '.json'
    if os.path.exists(meta) and json.load(open(meta)) == src and os.path.getsize(p) == src['bytes']:
        return p
    def get():
        with urllib.request.urlopen(urllib.request.Request(src['url'], headers=UA), timeout=1800) as r, open(p + '.part', 'wb') as f:
            shutil.copyfileobj(r, f, 1 << 24)
    retry(get)
    assert os.path.getsize(p + '.part') == src['bytes'], f'{layer}: short download'
    os.replace(p + '.part', p); json.dump(src, open(meta, 'w'))
    return p


def fids(pmtiles, layer, zoom=MAXZOOM):
    """the distinct `fid` values at one zoom (a feature crossing tiles appears in each); decoded as a stream"""
    ids, pat = set(), re.compile(r'"fid": ?(\d+)')
    with subprocess.Popen(['tippecanoe-decode', '-l', layer, '-z', str(zoom), '-Z', str(zoom), pmtiles], stdout=subprocess.PIPE, text=True) as p:
        for line in p.stdout:
            if '"Feature"' in line and (m := pat.search(line)): ids.add(int(m.group(1)))
    assert p.returncode == 0, f'tippecanoe-decode failed on {pmtiles}'
    return ids


def gda94(con, layer, z):
    """the zip's GDA94 files, byte for byte, into OUT/gda94/; returns (their paths relative to OUT, features in the GeoJSON)"""
    zf = zipfile.ZipFile(z); names = [n for n in zf.namelist() if '_GDA94' in os.path.basename(n)]
    gj = [n for n in names if n.endswith('_GDA94.geojson')]
    assert len(gj) == 1, f'{layer}: expected one *_GDA94.geojson in the zip, found {gj}'
    os.makedirs(os.path.join(sources.OUT, 'gda94'), exist_ok=True)
    paths = [f'gda94/{os.path.basename(n)}' for n in names]
    for n, p in zip(names, paths):
        with zf.open(n) as src, open(os.path.join(sources.OUT, p), 'wb') as dst: shutil.copyfileobj(src, dst, 1 << 24)
        assert os.path.getsize(os.path.join(sources.OUT, p)) == zf.getinfo(n).file_size, f'{layer}: short copy of {n}'
    n = con.execute(f"SELECT count(*) FROM ST_Read('{os.path.join(sources.OUT, 'gda94', os.path.basename(gj[0]))}')").fetchone()[0]
    return sorted(paths), n


def bake(con, layer, z, tmp):
    o = lambda f: os.path.join(sources.OUT, f)
    member = [n for n in zipfile.ZipFile(z).namelist() if n.endswith('_GDA2020.geojson')]
    assert len(member) == 1, f'{layer}: expected one *_GDA2020.geojson in the zip, found {member}'
    con.execute(f"COPY (SELECT * FROM ST_Read('/vsizip/{z}/{member[0]}')) TO '{o(layer + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    pq = f"read_parquet('{o(layer + '.parquet')}', file_row_number=true)"
    cols = [r[0] for r in con.execute(f'DESCRIBE SELECT * FROM {pq}').fetchall()]
    assert not {'fid', 'tiny_polygon_point'} & set(cols), f'{layer}: has its own fid or tiny_polygon_point field'
    rows, located = con.execute(f'SELECT count(*), count(geom) FROM {pq}').fetchone()
    assert rows == located, f'{layer}: {rows - located} features have no geometry'
    gl, pl = os.path.join(tmp, layer + '.geojsonl'), os.path.join(tmp, layer + '-points.geojsonl')
    lo, hi, pt = (os.path.join(tmp, f'{layer}-{x}.pmtiles') for x in ('lo', 'hi', 'pt'))
    con.execute(f"COPY (SELECT * EXCLUDE (file_row_number), file_row_number AS fid FROM {pq}) TO '{gl}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')")
    common = ['tippecanoe', '--force', '--quiet', '-l', layer, '-t', tmp, '--read-parallel']
    deep = [f'-Z{MAXZOOM}', f'-z{MAXZOOM}', '--no-feature-limit', '--no-tile-size-limit', '--no-tiny-polygon-reduction', '--no-line-simplification']
    subprocess.run(common + ['-o', lo, f'-Z{MINZOOM}', f'-z{MAXZOOM - 1}', '--drop-densest-as-needed', gl], check=True)
    subprocess.run(common + ['-o', hi] + deep + [gl], check=True)
    # a sliver (e.g. 1.4 cm wide and 400 m long) collapses to nothing on the zoom-14 grid, even at 18-bit detail: each feature
    # missing there goes in again as a point on its surface, marked tiny_polygon_point, so every feature exists at zoom 14
    seen = fids(hi, layer)
    con.execute('CREATE OR REPLACE TEMP TABLE seen AS SELECT unnest(?::BIGINT[]) AS fid', [sorted(seen)])
    missing = con.execute(f'SELECT count(*) FROM {pq} WHERE file_row_number NOT IN (SELECT fid FROM seen)').fetchone()[0]
    parts = [lo, hi]
    if missing:
        con.execute(f"""COPY (SELECT * EXCLUDE (file_row_number, geom), ST_PointOnSurface(geom) AS geom, file_row_number AS fid,
                              true AS tiny_polygon_point FROM {pq} WHERE file_row_number NOT IN (SELECT fid FROM seen))
                        TO '{pl}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')""")
        subprocess.run(common + ['-o', pt] + deep + [pl], check=True)
        assert len(fids(pt, layer)) == missing, f'{layer}: points for collapsed slivers missing at zoom {MAXZOOM}'
        parts.append(pt)
    subprocess.run(['tile-join', '--force', '--quiet', '--no-tile-size-limit', '-o', o(layer + '.pmtiles')] + parts, check=True)
    for f in [gl, pl] + parts:
        if os.path.exists(f): os.remove(f)
    n = len(seen) + missing
    assert n == rows, f'{layer}: {n} features at zoom {MAXZOOM}, {rows} in the source'
    return rows, n, missing


def main():
    want = sys.argv[1:] or list(LAYERS)
    assert set(want) <= set(LAYERS), f'unknown layer: {set(want) - set(LAYERS)}'
    for d in (sources.CACHE, sources.OUT): os.makedirs(d, exist_ok=True)
    srcs = {l: head(l) for l in want}
    old = published()
    if old and os.environ.get('REBAKE') != '1' and all(old.get('sources', {}).get(l) == srcs[l] for l in LAYERS):
        print(json.dumps({'unchanged': True, 'since': old['built']})); return        # no index.json: publish.py does nothing
    tmp = os.path.join(sources.DATA, 'tmp'); os.makedirs(tmp, exist_ok=True)
    con = duckdb.connect(os.path.join(tmp, 'bake.duckdb')); con.execute('INSTALL spatial; LOAD spatial')
    counts, g94 = {}, {}
    for l in want:
        t = datetime.datetime.now(); z = download(l, srcs[l])
        counts[l], counts[l + '_tiles_deepest_zoom'], counts[l + '_tiny_polygon_points'] = bake(con, l, z, tmp)
        g94[l], counts[l + '_gda94'] = gda94(con, l, z)
        if counts[l + '_gda94'] != counts[l]:
            print(f'::warning::{l}: GDA94 copy has {counts[l + "_gda94"]} features, GDA2020 {counts[l]}', flush=True)
        print(json.dumps({'layer': l, 'rows': counts[l], 'seconds': (datetime.datetime.now() - t).seconds,
                          'parquet_bytes': os.path.getsize(os.path.join(sources.OUT, l + '.parquet')),
                          'pmtiles_bytes': os.path.getsize(os.path.join(sources.OUT, l + '.pmtiles'))}), flush=True)
    con.close(); shutil.rmtree(tmp)
    idx = {'built': datetime.datetime.now().isoformat(timespec='seconds'), 'counts': counts, 'layers': want,
           'sources': srcs, 'crs': 'EPSG:7844 (GDA2020)', 'gda94': g94}
    json.dump(idx, open(os.path.join(sources.OUT, 'index.json'), 'w'), indent=1)
    print(json.dumps(idx))


if __name__ == '__main__':
    main()
