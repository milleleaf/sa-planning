"""Publish sources.OUT to Hugging Face (needs HF_TOKEN with write access to the alreadyopen org):
  dataset  REPO  index.json + every <layer>.parquet + manifest.json + the card (hf/README.md): one commit a run, versioned
  bucket   REPO  index.json + every <layer>.pmtiles + manifest.json, overwritten in place (read by browsers: CORS + HTTP Range)
Each big file is stored once on Hugging Face (Parquet in the dataset, PMTiles in the bucket); the Kaggle mirror has both.
KAGGLE_FILES (each zip's GDA94 copy, gda94/) go to Kaggle only, but are in manifest.json, so the gate covers them too.
Nothing is uploaded unless the publish gate passes (manifest.py). Does nothing when bake.py found every source unchanged.
Usage: python3 publish.py     (after bake.py)"""
import json, os
from huggingface_hub import CommitOperationAdd, HfApi, batch_bucket_files, create_bucket
import manifest, sources

REPO = 'milleleaf/sa-planning'
_idx = os.path.join(sources.OUT, 'index.json')
_i = json.load(open(_idx)) if os.path.exists(_idx) else {}
LAYERS = _i.get('layers', [])
DATASET_FILES = ['index.json'] + [f'{l}.parquet' for l in LAYERS]
BUCKET_FILES = ['index.json'] + [f'{l}.pmtiles' for l in LAYERS]            # the map reads these
KAGGLE_FILES = [p for l in LAYERS for p in _i.get('gda94', {}).get(l, [])]   # GDA94 copies: Kaggle only (kaggle_mirror.py)
KAGGLE = ('helenkwok/sa-planning', 'Milleleaf: South Australia planning')     # mirrored by kaggle_mirror.py (title 6-50 chars)

def main():
    if not LAYERS:
        print(json.dumps({'nothing new': True})); return
    o = lambda f: os.path.join(sources.OUT, f); idx = json.load(open(o('index.json')))
    m = manifest.manifest(sources.OUT, sorted(set(DATASET_FILES + BUCKET_FILES + KAGGLE_FILES)), idx['counts'], idx['built'])
    manifest.gate(m, f'https://huggingface.co/buckets/{REPO}/resolve/manifest.json')
    json.dump(m, open(o('manifest.json'), 'w'), indent=1)
    api = HfApi(); api.create_repo(REPO, repo_type='dataset', exist_ok=True)
    card = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hf', 'README.md')
    api.create_commit(REPO, repo_type='dataset', commit_message=f"bake of {idx['built']}",
                      operations=[CommitOperationAdd(f, o(f)) for f in DATASET_FILES + ['manifest.json']] + [CommitOperationAdd('README.md', card)])
    create_bucket(REPO, private=False, exist_ok=True)
    batch_bucket_files(REPO, add=[(o(f), f) for f in BUCKET_FILES] + [(o('manifest.json'), 'manifest.json')])   # the gate reads the bucket's
    print(json.dumps({'dataset': f'https://huggingface.co/datasets/{REPO}', 'bucket': f'https://huggingface.co/buckets/{REPO}', 'built': idx['built'], 'counts': m['counts']}))

if __name__ == '__main__':
    main()
