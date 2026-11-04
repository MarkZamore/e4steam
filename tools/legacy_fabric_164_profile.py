"""Stage the twenty-target frozen profile after the source port is committed.

No network publication or active-index rewrite is performed by this command.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PROFILE='native-lan-ui-v3'
TAG='legacy-fabric-164-v1'
BASE='native-lan-ui-v2'
UPSTREAM='bdcea00e30ca519fa8190c0c5c04785d42b31dbc'

def sha(data):return hashlib.sha256(data).hexdigest()

def committed(source_commit,path):
    if not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('An exact committed source revision is required')
    return subprocess.check_output(['git','-C',str(ROOT),'show',source_commit+':'+path])

def stage(directory,source_commit):
    receipt_path=directory/'build-receipt.json';receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt['type']!='source-built-legacy-port' or receipt['upstreamSourceCommit']!=UPSTREAM:raise ValueError('Unexpected port provenance')
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
    base=json.loads((ROOT/'profiles'/f'{BASE}.json').read_text(encoding='utf-8'))
    if len(base['builds'])!=19:raise ValueError('The reviewed nineteen-target base changed')
    result=copy.deepcopy(base);result['profile']=PROFILE;result['sourceCommit']=source_commit
    for row in result['builds']:row['profile']=PROFILE
    result['builds'].append({
        'version':'0.3.4','fileName':receipt['fileName'],'sizeBytes':receipt['sizeBytes'],'sha256':receipt['sha256'],
        'loaders':['LegacyFabric'],'minimumMinecraftVersion':[1,6,4],'exclusiveMaximumMinecraftVersion':[1,6,5],
        'downloadUrl':f'https://github.com/MarkZamore/e4steam/releases/download/{TAG}/{receipt["fileName"]}',
        'upstreamDownloadUrl':f'https://github.com/Kamilhik/e4steam/tree/{UPSTREAM}',
        'upstreamReleaseUrl':'https://github.com/Kamilhik/e4steam/releases/tag/v0.3.4',
        'metadataPath':'fabric.mod.json','authorVersion':'0.3.4','deliveryTag':TAG,'profile':PROFILE,
        'derivation':{'type':'source-built-legacy-port','sourceCommit':source_commit,'upstreamSourceCommit':UPSTREAM,
            'sourceBuildRecipe':{'path':'tools/legacy_fabric_164.py','sha256':receipt['recipeSha256']},
            'sourceBuildReceipt':{'fileName':'build-receipt.json','sizeBytes':receipt_path.stat().st_size,'sha256':sha(receipt_path.read_bytes()),'downloadUrl':f'https://github.com/MarkZamore/e4steam/releases/download/{TAG}/build-receipt.json'},
            'sourceBuiltClassSha256':receipt['sourceBuiltClassSha256']}})
    for old,new in zip(base['builds'],result['builds']):
        expected=copy.deepcopy(old);expected['profile']=PROFILE
        if new!=expected:raise ValueError('Existing target provenance or bytes changed')
    payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (directory/'components.json').write_text(payload,encoding='utf-8')
    (directory/f'{PROFILE}.json').write_text(payload,encoding='utf-8')
    (directory/'SHA256SUMS.txt').write_text(''.join(row['sha256']+'  '+row['fileName']+'\n' for row in sorted(result['builds'],key=lambda r:r['fileName'])),encoding='utf-8')
    print(json.dumps({'profile':PROFILE,'targets':20,'sourceCommit':source_commit,'staging':str(directory)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'dist'/TAG);p.add_argument('--source-commit',required=True)
    args=p.parse_args();stage(args.out.resolve(),args.source_commit)
