"""Verify the exact reviewed active shared index without assuming a profile generation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

import components
import legacy_fabric_164
import native_ui_v2

ROOT=Path(__file__).resolve().parents[1]
V2='native-lan-ui-v2'
V3='native-lan-ui-v3'
V4='native-lan-ui-v4'
V5='native-lan-ui-v5'
V3_TAG='legacy-fabric-164-v1'

def require(value,message):
    if not value:raise ValueError(message)

def verify_active(root=None):
    root=Path(root) if root is not None else ROOT
    active_bytes=(root/'components.json').read_bytes();active=json.loads(active_bytes)
    profile=active.get('profile')
    require(profile in {V2,V3,V4,V5},'Unsupported active profile; author fallback is forbidden')
    frozen_bytes=(root/'profiles'/f'{profile}.json').read_bytes();frozen=json.loads(frozen_bytes)
    require(active_bytes==frozen_bytes,'Active index bytes differ from the reviewed frozen profile')
    require(active.get('schemaVersion')==2 and active.get('componentId')=='e4steam','Invalid shared component index')
    require((root/'SHA256SUMS.txt').read_bytes()==components.checksums(frozen['builds']).encode(),'Active checksum bytes differ from the frozen profile')
    if profile==V2:
        return native_ui_v2.verify_active()
    verify_legacy_profile(root, active)
    return active

def verify_legacy_profile(root, document):
    profile = document['profile']
    require(profile in {V3, V4, V5}, 'Unsupported Legacy Fabric profile')
    revision = {V3: 1, V4: 2, V5: 3}[profile]
    tag = f'legacy-fabric-164-v{revision}'
    filename = f'e4steam-legacy-fabric-mc1.6.4-v0.3.4-lf164.{revision}.jar'
    require(set(native_ui_v2.CAPABILITIES).issubset(document.get('capabilities', [])),
            f'{profile} drops a reviewed native UI/auth capability')
    base=json.loads((root/'profiles'/f'{V2}.json').read_bytes())
    previous={row['fileName']:row for row in base['builds']}
    require(len(previous) == 19 and len(document['builds']) == 20, 'Invalid legacy profile target coverage')
    legacy=[]
    for row in document['builds']:
        if row['fileName'] in previous:
            expected = {**previous.pop(row['fileName']), 'profile': profile}
            require(row == expected, f'{profile} changes an existing target pin or provenance')
        else:legacy.append(row)
    require(not previous and len(legacy) == 1, 'Legacy profile must retain nineteen targets and one source port')
    row=legacy[0];derivation=row.get('derivation',{})
    release_url = f'https://github.com/MarkZamore/e4steam/releases/download/{tag}/'
    require(row.get('loaders') == ['LegacyFabric'] and row.get('minimumMinecraftVersion') == [1, 6, 4]
            and row.get('exclusiveMaximumMinecraftVersion') == [1, 6, 5]
            and row.get('metadataPath') == 'fabric.mod.json' and row.get('profile') == profile,
            'Unexpected legacy target compatibility')
    require(row.get('deliveryTag') == tag and row.get('fileName') == filename
            and row.get('downloadUrl') == release_url + filename,
            'Unexpected immutable legacy delivery tag or artifact')
    require(derivation.get('type') == 'source-built-legacy-port'
            and derivation.get('sourceCommit') == document.get('sourceCommit')
            and re.fullmatch('[a-f0-9]{40}', document.get('sourceCommit', '')),
            'Invalid legacy source revision')
    require(not any(name in row for name in ('authorFileName','authorSizeBytes','authorSha256')),'Legacy source port must not invent an author JAR')
    receipt_bytes=(root/'releases'/tag/'build-receipt.json').read_bytes();receipt=json.loads(receipt_bytes)
    pin=derivation.get('sourceBuildReceipt',{})
    require(pin.get('fileName') == 'build-receipt.json' and pin.get('sizeBytes') == len(receipt_bytes)
            and pin.get('sha256') == hashlib.sha256(receipt_bytes).hexdigest()
            and pin.get('downloadUrl') == release_url + 'build-receipt.json',
            'Frozen source-port receipt pin differs')
    require(all(receipt.get(key)==row.get(key) for key in ('fileName','sizeBytes','sha256')) and receipt.get('type')==derivation['type'] and receipt.get('upstreamSourceCommit')==derivation.get('upstreamSourceCommit') and receipt.get('recipeSha256')==derivation.get('sourceBuildRecipe',{}).get('sha256') and receipt.get('sourceBuiltClassSha256')==derivation.get('sourceBuiltClassSha256'),'Frozen source-port receipt provenance differs')
    require(bool(receipt.get('sourceBuiltClassSha256')),'Source-port class inventory is empty')

if __name__=='__main__':
    document=verify_active();print('Verified active frozen profile:',document['profile'],len(document['builds']),'targets')
