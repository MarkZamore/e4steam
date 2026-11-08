"""Stage, reproduce and verify delivery of the reviewed Legacy Fabric update.

This command never uploads assets or changes the active index.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import zipfile

import active_profile
import components
from legacy_fabric_164 import IMPLEMENTATION_VERSION, NAME, TAG, UPSTREAM

ROOT=Path(__file__).resolve().parents[1]
PROFILE=active_profile.V6
BASE=active_profile.V5
BASE_SHA256='c718ce3b1b817b63faadc11745057d008c10e5ad6f3852c1cfb8b666b31295f9'
REPOSITORY='MarkZamore/e4steam'
RELEASE_URL=f'https://github.com/{REPOSITORY}/releases/download/{TAG}/'

def sha(data):return hashlib.sha256(data).hexdigest()

def committed(source_commit,path):
    if not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('An exact committed source revision is required')
    return subprocess.check_output(['git','-C',str(ROOT),'show',source_commit+':'+path])

def stage(directory,source_commit):
    receipt_path=directory/'build-receipt.json';receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if (receipt['type'] != 'source-built-legacy-port' or receipt['upstreamSourceCommit'] != UPSTREAM
            or receipt['fileName'] != NAME):
        raise ValueError('Unexpected port provenance or immutable artifact name')
    jar_path=directory/receipt['fileName'];data=jar_path.read_bytes()
    if sha(data)!=receipt['sha256'] or len(data)!=receipt['sizeBytes']:raise ValueError('Port delivery differs from its build receipt')
    for name,digest in receipt['sources'].items():
        if sha(committed(source_commit,name))!=digest:raise ValueError('Port source is not in the supplied commit: '+name)
    if sha(committed(source_commit,'tools/legacy_fabric_164.py'))!=receipt['recipeSha256']:raise ValueError('Build recipe differs from committed source')
    with zipfile.ZipFile(jar_path) as jar:
        names=set(jar.namelist())
        if len(names)!=len(jar.namelist()):raise ValueError('Duplicate delivery entry')
        if any(n.startswith('org/apache/logging/') for n in names):raise ValueError('Port must use platform Log4j, not override the author library')
        for name,digest in receipt['sourceBuiltClassSha256'].items():
            if sha(jar.read(name))!=digest:raise ValueError('Source-built class pin differs: '+name)
        preload=jar.read('e4steam-retro-preload.txt').decode().splitlines()
        if any('.mixin.' in n for n in preload):raise ValueError('Mixin implementation must not be directly preloaded')
        metadata=json.loads(jar.read('fabric.mod.json'))
        if metadata['id']!='e4steam' or metadata['version']!='0.3.4' or metadata['depends']['minecraft']!='1.6.4':raise ValueError('Wrong native port metadata')
        if f'Implementation-Version: {IMPLEMENTATION_VERSION}' not in jar.read('META-INF/MANIFEST.MF').decode('ascii').splitlines():
            raise ValueError('Wrong native port implementation version')
    base_bytes = (ROOT/'profiles'/f'{BASE}.json').read_bytes()
    if sha(base_bytes) != BASE_SHA256:
        raise ValueError('The published base profile changed')
    base=json.loads(base_bytes)
    active_profile.verify_legacy_profile(ROOT, base)
    result=copy.deepcopy(base);result['profile']=PROFILE;result['sourceCommit']=source_commit
    for row in result['builds']:row['profile']=PROFILE
    legacy = next(row for row in result['builds'] if row['loaders'] == ['LegacyFabric'])
    legacy.update(fileName=NAME, sizeBytes=receipt['sizeBytes'], sha256=receipt['sha256'],
                  downloadUrl=RELEASE_URL + NAME, deliveryTag=TAG)
    legacy['derivation'].update(
        sourceCommit=source_commit,
        sourceBuildRecipe={'path': 'tools/legacy_fabric_164.py', 'sha256': receipt['recipeSha256']},
        sourceBuildReceipt={
            'fileName': 'build-receipt.json',
            'sizeBytes': receipt_path.stat().st_size,
            'sha256': sha(receipt_path.read_bytes()),
            'downloadUrl': RELEASE_URL + 'build-receipt.json',
        },
        sourceBuiltClassSha256=receipt['sourceBuiltClassSha256'],
    )
    payload=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    (directory/'components.json').write_text(payload,encoding='utf-8',newline='\n')
    (directory/f'{PROFILE}.json').write_text(payload,encoding='utf-8',newline='\n')
    (directory/'SHA256SUMS.txt').write_text(components.checksums(result['builds']),encoding='utf-8',newline='\n')
    print(json.dumps({'profile':PROFILE,'targets':20,'sourceCommit':source_commit,'staging':str(directory)}))

def verify_frozen(directory):
    frozen_path=ROOT/'profiles'/f'{PROFILE}.json'
    frozen=frozen_path.read_bytes();document=json.loads(frozen)
    active_profile.verify_legacy_profile(ROOT, document)
    receipt_path=ROOT/'releases'/TAG/'build-receipt.json'
    if (directory/'build-receipt.json').read_bytes()!=receipt_path.read_bytes():raise ValueError('Fresh source-port receipt differs from frozen bytes')
    stage(directory,document['sourceCommit'])
    if (directory/'components.json').read_bytes()!=frozen or (directory/f'{PROFILE}.json').read_bytes()!=frozen:raise ValueError('Fresh source-port profile differs from frozen bytes')
    expected=components.checksums(document['builds']).encode()
    if (directory/'SHA256SUMS.txt').read_bytes()!=expected:raise ValueError('Fresh source-port checksums differ from frozen selection')
    print('Fresh Legacy Fabric JAR, receipt, committed inputs and frozen profile: PASS')

def require_ci(run_id):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Commit the reviewed profile before checking publication CI')
    endpoint = f'repos/{REPOSITORY}/actions/runs/{run_id}'
    run = json.loads(components.gh('api', endpoint))
    if (run.get('head_sha') != revision or run.get('conclusion') != 'success'
            or run.get('path') != '.github/workflows/native-ui.yml'):
        raise ValueError('Exact native profile CI has not passed for the release commit')
    jobs = json.loads(components.gh('api', endpoint + '/jobs'))['jobs']
    expected = {'build (ubuntu-latest)', 'build (windows-latest)',
                'legacy-port (ubuntu-24.04)', 'legacy-port (windows-latest)'}
    if (len(jobs) != len(expected) or {job['name'] for job in jobs} != expected
            or any(job.get('conclusion') != 'success' for job in jobs)):
        raise ValueError('The exact modern and legacy Linux/Windows jobs must all pass')
    print(revision)

def verify_public():
    frozen = (ROOT/'profiles'/f'{PROFILE}.json').read_bytes()
    document = json.loads(frozen)
    active_profile.verify_legacy_profile(ROOT, document)
    rows = document['builds']
    legacy = next(row for row in rows if row['loaders'] == ['LegacyFabric'])
    metadata = {
        'build-receipt.json': (ROOT/'releases'/TAG/'build-receipt.json').read_bytes(),
        'SHA256SUMS.txt': components.checksums(rows).encode(),
        'components.json': frozen,
    }
    assets = {name: (len(data), sha(data)) for name, data in metadata.items()}
    assets[NAME] = (legacy['sizeBytes'], legacy['sha256'])
    release = json.loads(components.gh('api', f'repos/{REPOSITORY}/releases/tags/{TAG}'))
    if release['draft'] or {asset['name'] for asset in release['assets']} != set(assets):
        raise ValueError('Unexpected public immutable Legacy Fabric release inventory')
    for asset in release['assets']:
        name = asset['name']
        size, digest = assets[name]
        if (asset['state'] != 'uploaded' or asset['size'] != size or asset.get('digest') != 'sha256:' + digest
                or asset['browser_download_url'] != RELEASE_URL + name):
            raise ValueError('Release API digest, size or URL mismatch: ' + name)

    def check(row):
        url = row['downloadUrl']
        name = row['fileName']
        size, expected = row['sizeBytes'], row['sha256']
        request = urllib.request.Request(url, headers={'User-Agent': 'LANMinecraft-SharedComponent/1.0'})
        digest = hashlib.sha256()
        downloaded = 0
        with urllib.request.urlopen(request, timeout=45) as response:
            while chunk := response.read(64 * 1024):
                downloaded += len(chunk)
                if downloaded > size:
                    raise ValueError('Public asset exceeds its pinned size: ' + name)
                digest.update(chunk)
        if downloaded != size or digest.hexdigest() != expected:
            raise ValueError('Public asset SHA256 or size mismatch: ' + name)
        return {key: row[key] for key in ('fileName', 'sizeBytes', 'sha256', 'downloadUrl')}

    expected_metadata = [
        dict(fileName=name, sizeBytes=len(data), sha256=sha(data), downloadUrl=RELEASE_URL + name)
        for name, data in metadata.items()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        checked = list(pool.map(check, [*rows, *expected_metadata]))
    print(json.dumps({
        'schemaVersion': 1, 'profile': PROFILE, 'sourceCommit': document['sourceCommit'],
        'status': 'PASS_ACTUAL_PUBLIC_BYTES_NOT_GAME', 'actualSelectedJarDownloads': len(rows),
        'actualReleaseAssets': [row for row in checked if row['downloadUrl'].startswith(RELEASE_URL)],
        'checked': checked[:len(rows)],
    }, indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,default=ROOT/'dist'/TAG)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--source-commit')
    action.add_argument('--verify-frozen', action='store_true')
    action.add_argument('--verify-ci', type=int, metavar='RUN_ID')
    action.add_argument('--verify-public', action='store_true')
    args=p.parse_args()
    if args.verify_frozen:
        verify_frozen(args.out.resolve())
    elif args.source_commit:stage(args.out.resolve(),args.source_commit)
    elif args.verify_ci is not None:require_ci(args.verify_ci)
    else:verify_public()
