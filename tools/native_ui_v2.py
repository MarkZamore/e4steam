"""Build-time native UI/auth lifecycle profile; no installed or running JAR edits."""
from __future__ import annotations

import argparse
import copy
import concurrent.futures
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import components
import native_ui as prior

ROOT = Path(__file__).resolve().parent.parent
PROFILE = 'native-lan-ui-v2'
MIXIN = 'link/e4steam/mixin/IntegratedServerLanMixin.class'
APPLIER = 'link/e4steam/lan/LanServerSettingsApplier.class'
CHANGED = {prior.PAUSE, prior.MIXINS, MIXIN, APPLIER}
META = 'source/native-lan-auth-v2.json'
FEATURES = {'nativeLanSettingsUiAbsent': True, 'configuredOnlineModeAtNativePublish': True,
            'authorSteamAuthenticationAndTransportRetained': True}
CAPABILITIES = ['native-lan-settings-ui-hidden-or-absent',
                'modern-configured-online-mode-at-native-publish',
                'author-steam-authentication-retained']


def metadata():
    document = json.loads((ROOT / META).read_text(encoding='utf-8'))
    if document['upstreamCommit'] != prior.SOURCE_COMMIT or document['profile'] != PROFILE:
        raise ValueError('Unexpected native LAN auth source provenance')
    if document.get('requiredFeatures') != FEATURES:
        raise ValueError('Required native UI/auth behavior is not retained')
    inventory = document.get('authorInventory', [])
    if {row.get('path') for row in inventory} != {'author-components.json', 'releases/v0.3.2.json', 'releases/v0.3.4.json'}:
        raise ValueError('Reviewed author inventory changed; rebase review is required')
    for row in [*document['sourcePatches'], *document['sourceFiles'], *inventory]:
        relative = row['path']
        if (not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative
                or any(part in {'', '.', '..'} for part in relative.split('/'))):
            raise ValueError('Unsafe native LAN auth source path')
        path = ROOT / relative
        if (path.stat().st_size != row['sizeBytes'] or prior.sha(path.read_bytes()) != row['sha256']):
            raise ValueError('Reviewed native LAN auth source changed: ' + relative)
    return document


def validate_online_mode(mixin: bytes, applier: bytes, old_mixin: bytes, old_applier: bytes):
    for current, original in ((mixin, old_mixin), (applier, old_applier)):
        if current[:4] != b'\xca\xfe\xba\xbe' or current[6:8] != original[6:8]:
            raise ValueError('Native LAN auth class has a different JVM target')
    for required in (b'e4steam$applyPublishOnlineMode', b'applyOnlineMode', b'lanOnlineMode',
                     b'/^(publishServer|method_3763|m_7386_|func_195457_a)$/'):
        if required not in mixin:
            raise ValueError('Native publish online-mode hook is missing')
    for required in (b'applyOnlineMode', b'setUsesAuthentication', b'method_3864', b'm_129985_'):
        if required not in applier:
            raise ValueError('Native online-mode setter bridge is missing')


def notice(author_sha: str, source: dict):
    return ('LANMinecraft native-lan-ui-v2 distribution, based on e4steam by Kamilchik.\n'
            'Author license, NOTICE and third-party notices are retained unchanged.\n'
            'Original artifact SHA256: ' + author_sha + '\n'
            'Source commit: ' + prior.SOURCE_COMMIT + '\n'
            'Removes the additional LAN Settings widget and native-screen redirects.\n'
            'Before native integrated LAN publication, applies only configured lanOnlineMode.\n'
            'Game mode, commands, PvP, player capacity and port are not applied by this hook.\n'
            'Steam authentication, invitations, transport and native libraries retain author bytes.\n'
            'Changed entries: ' + ', '.join(sorted(CHANGED)) + '.\n'
            'Auth source patch SHA256: ' + source['sourcePatches'][1]['sha256'] + '\n'
            'This is a declared downstream distribution, not an unmodified author release.\n').encode('utf-8')


def replacements(old, compiled):
    pause = compiled.read(prior.PAUSE)
    prior.validate_pause(pause, old.read(prior.PAUSE))
    mixin, applier = compiled.read(MIXIN), compiled.read(APPLIER)
    validate_online_mode(mixin, applier, old.read(MIXIN), old.read(APPLIER))
    if any(name in json.loads(compiled.read(prior.MIXINS)).get('client', []) for name in prior.REDIRECTS):
        raise ValueError('Source-built artifact still enables a form redirect')
    original_mixins = json.loads(old.read(prior.MIXINS))
    if 'IntegratedServerLanMixin' not in original_mixins.get('client', []):
        raise ValueError('Author integrated publish mixin is not registered')
    return {prior.PAUSE: pause, prior.MIXINS: prior.without_redirects(old.read(prior.MIXINS)),
            MIXIN: mixin, APPLIER: applier}


def derive(original: Path, built: Path, target: Path, expected_sha: str, source: dict):
    if prior.sha(original.read_bytes()) != expected_sha:
        raise ValueError('Original SHA256 changed before derivation')
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(built) as compiled:
        if len(old.namelist()) != len(set(old.namelist())) or prior.NOTICE in old.namelist():
            raise ValueError('Duplicate or already-derived original entries')
        if any(name.upper().startswith('META-INF/') and name.upper().endswith(('.SF', '.RSA', '.DSA', '.EC'))
               for name in old.namelist()):
            raise ValueError('Signed author artifact needs a separately reviewed signing strategy')
        changed = replacements(old, compiled)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for entry in old.infolist():
                output.writestr(copy.copy(entry), changed.get(entry.filename, old.read(entry.filename)))
            entry = zipfile.ZipInfo(prior.NOTICE, (1980, 1, 1, 0, 0, 0))
            entry.create_system, entry.compress_type = 3, zipfile.ZIP_DEFLATED
            output.writestr(entry, notice(expected_sha, source))
    return verify_derivative(original, built, target, expected_sha, source)


def verify_derivative(original, built, candidate, expected_sha, source):
    if prior.sha(original.read_bytes()) != expected_sha:
        raise ValueError('Original SHA256 differs from frozen author inventory')
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(built) as compiled, zipfile.ZipFile(candidate) as new:
        if len(new.namelist()) != len(set(new.namelist())) or set(new.namelist()) != set(old.namelist()) | {prior.NOTICE}:
            raise ValueError('Derivative entry set changed beyond its declared notice')
        replacement = replacements(old, compiled)
        changed = {name for name in old.namelist() if old.read(name) != new.read(name)}
        if changed != CHANGED:
            raise ValueError('Expected exactly four declared native UI/auth lifecycle modifications')
        for name in old.namelist():
            if new.read(name) != replacement.get(name, old.read(name)):
                raise ValueError('Unrelated author entry changed: ' + name)
        if new.read(prior.NOTICE) != notice(expected_sha, source):
            raise ValueError('Native LAN auth modification notice differs')
        return {'changedEntries': sorted(changed), 'addedEntries': [prior.NOTICE],
                'unchangedOriginalEntries': len(old.namelist()) - len(changed),
                'allOtherEntriesByteIdentical': True,
                'sourceBuiltClassSha256': {name: prior.sha(compiled.read(name)) for name in sorted(CHANGED - {prior.MIXINS})}}


def stage(originals: Path, compiled: Path, output: Path):
    source, builds, derivatives = metadata(), [], 0
    for author in prior.author_index():
        original = prior.find_verified(originals, author)
        with zipfile.ZipFile(original) as archive:
            modern = prior.has_extra_ui(archive)
        item = dict(author)
        item.update(authorVersion=author['version'], authorFileName=author['fileName'], authorSha256=author['sha256'],
                    authorSizeBytes=author['sizeBytes'], profile=PROFILE, deliveryTag='v' + author['version'])
        if modern:
            filename = author['fileName'][:-4] + '-lanmc-native-ui.2.jar'
            target = output / filename
            proof = derive(original, compiled / author['fileName'], target, author['sha256'], source)
            item.update(fileName=filename, sizeBytes=target.stat().st_size, sha256=prior.sha(target.read_bytes()),
                        deliveryTag=PROFILE, downloadUrl='https://github.com/MarkZamore/e4steam/releases/download/' + PROFILE + '/' + filename,
                        derivation={'type': 'source-built-native-ui-and-lan-online-mode', 'sourceCommit': prior.SOURCE_COMMIT, **proof})
            derivatives += 1
        else:
            item['derivation'] = {'type': 'byte-identical-author-artifact', 'uiAbsent': True,
                                  'removedLanSettingsApplierAbsent': True}
        builds.append(item)
    if derivatives != 6 or len(builds) != 19:
        raise ValueError('Unexpected native LAN auth platform scope; review required')
    manifest = {'schemaVersion': 2, 'componentId': 'e4steam', 'publisher': 'MarkZamore',
                'profile': PROFILE, 'sourceCommit': prior.SOURCE_COMMIT,
                'capabilities': CAPABILITIES,
                'sourcePatches': source['sourcePatches'], 'builds': builds}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'components.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    (output / 'SHA256SUMS.txt').write_text(components.checksums(builds), encoding='utf-8', newline='\n')
    for row in source['sourcePatches']:
        shutil.copyfile(ROOT / row['path'], output / Path(row['path']).name)
    shutil.copyfile(ROOT / META, output / Path(META).name)
    print('Staged native LAN auth profile: six explicit derivatives; thirteen unchanged retro selections')
    return manifest


def verify_profile(originals, compiled, output):
    with tempfile.TemporaryDirectory(prefix='e4steam-native-ui-v2-') as directory:
        expected = Path(directory)
        document = stage(originals, compiled, expected)
        frozen = json.loads((ROOT / 'profiles' / (PROFILE + '.json')).read_text(encoding='utf-8'))
        if document != frozen:
            raise ValueError('Built profile differs from reviewed frozen selection; retain last verified release')
        if {path.name for path in expected.iterdir()} != {path.name for path in output.iterdir()}:
            raise ValueError('Native LAN auth asset set differs')
        for path in expected.iterdir():
            if path.read_bytes() != (output / path.name).read_bytes():
                raise ValueError('Native LAN auth staged bytes differ: ' + path.name)
        return document


def verify_active():
    metadata()
    active = json.loads((ROOT / 'components.json').read_text(encoding='utf-8'))
    frozen = json.loads((ROOT / 'profiles' / (PROFILE + '.json')).read_text(encoding='utf-8'))
    if active != frozen or active.get('schemaVersion') != 2 or active.get('profile') != PROFILE:
        raise ValueError('Active shared selection must be the reviewed patched profile; author fallback is forbidden')
    if not set(CAPABILITIES).issubset(active.get('capabilities', [])):
        raise ValueError('Active shared profile does not retain required capabilities')
    if (ROOT / 'SHA256SUMS.txt').read_text(encoding='utf-8') != components.checksums(frozen['builds']):
        raise ValueError('Active patched-profile checksum inventory differs')
    modern = [row for row in frozen['builds'] if row['authorVersion'] == '0.3.4']
    retro = [row for row in frozen['builds'] if row['authorVersion'] == '0.3.2']
    if (len(modern) != 6 or len(retro) != 13
            or any(row['deliveryTag'] != PROFILE or row['derivation']['type'] != 'source-built-native-ui-and-lan-online-mode'
                   for row in modern)
            or any(row['derivation']['type'] != 'byte-identical-author-artifact' for row in retro)):
        raise ValueError('Active profile target coverage or retained features changed')
    return active


def require_ci(run_id):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('Commit reviewed source before publishing')
    run = json.loads(components.gh('api', 'repos/MarkZamore/e4steam/actions/runs/' + str(run_id)))
    if (run.get('head_sha') != revision or run.get('conclusion') != 'success'
            or run.get('path') != '.github/workflows/native-ui.yml'):
        raise ValueError('Exact source native-profile CI has not passed')
    jobs = json.loads(components.gh('api', 'repos/MarkZamore/e4steam/actions/runs/' + str(run_id) + '/jobs'))['jobs']
    if len(jobs) != 2 or any(job.get('conclusion') != 'success' for job in jobs):
        raise ValueError('Both native Linux and Windows source-profile jobs must pass')
    return revision


def ordered_assets(output):
    return (sorted(output.glob('*.jar'))
            + [output / 'native-ui.patch', output / 'native-lan-auth-v2.patch', output / 'native-lan-auth-v2.json',
               output / 'SHA256SUMS.txt', output / 'components.json'])


def publish(originals, compiled, output, run_id):
    verify_profile(originals, compiled, output)
    revision = require_ci(run_id)
    repository = 'MarkZamore/e4steam'
    probe = subprocess.run(['gh', 'api', 'repos/' + repository + '/releases/tags/' + PROFILE],
                           capture_output=True, text=True, encoding='utf-8')
    if probe.returncode:
        if '404' not in probe.stderr:
            raise RuntimeError(probe.stderr.strip())
        components.gh('release', 'create', PROFILE, '--repo', repository, '--target', revision,
                      '--title', 'e4steam native LAN UI and configured authentication v2',
                      '--notes-file', ROOT / 'NATIVE-UI-V2.md')
        release = json.loads(components.gh('api', 'repos/' + repository + '/releases/tags/' + PROFILE))
    else:
        release = json.loads(probe.stdout)
    existing = {asset['name']: asset for asset in release['assets']}
    ordered = ordered_assets(output)
    if not set(existing).issubset({path.name for path in ordered}):
        raise ValueError('Unexpected existing immutable V2 release asset')
    # Check every conflict before the first upload; never replace historical assets.
    for path in ordered:
        if path.name in existing:
            asset = existing[path.name]
            if asset['size'] != path.stat().st_size or asset.get('digest') != 'sha256:' + prior.sha(path.read_bytes()):
                raise ValueError('Conflicting immutable V2 release asset: ' + path.name)
    for path in ordered:
        if path.name not in existing:
            components.gh('release', 'upload', PROFILE, path, '--repo', repository)
            print('Uploaded', PROFILE, path.name, flush=True)


def verify_remote(originals, compiled, output, downloads):
    document = verify_profile(originals, compiled, output)
    if downloads.exists():
        raise ValueError('Use a new private directory for actual remote verification')
    downloads.mkdir(parents=True)
    source = metadata()
    def check(build):
        target = downloads / build['fileName']
        components.fetch(build['downloadUrl'], target)
        components.verify_file(target, build)
        if build['authorVersion'] == '0.3.4':
            original = prior.find_verified(originals, {**build, 'fileName': build['authorFileName'],
                'sha256': build['authorSha256'], 'sizeBytes': build['authorSizeBytes']})
            verify_derivative(original, compiled / build['authorFileName'], target, build['authorSha256'], source)
        return {key: build[key] for key in ['fileName', 'sizeBytes', 'sha256', 'downloadUrl', 'deliveryTag']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        checked = list(pool.map(check, document['builds']))
    release = json.loads(components.gh('api', 'repos/MarkZamore/e4steam/releases/tags/' + PROFILE))
    existing = {asset['name']: asset for asset in release['assets']}
    ordered = ordered_assets(output)
    if len(existing) != len(ordered) or set(existing) != {path.name for path in ordered}:
        raise ValueError('Actual V2 API asset inventory differs')
    for path in ordered:
        expected_sha, expected_size = prior.sha(path.read_bytes()), path.stat().st_size
        asset = existing[path.name]
        url = 'https://github.com/MarkZamore/e4steam/releases/download/' + PROFILE + '/' + path.name
        if (asset['state'] != 'uploaded' or asset['size'] != expected_size
                or asset.get('digest') != 'sha256:' + expected_sha or asset['browser_download_url'] != url):
            raise ValueError('Actual V2 API full digest/size/URL differs: ' + path.name)
        target = downloads / path.name
        if not target.exists():
            components.fetch(url, target)
        if target.stat().st_size != expected_size or prior.sha(target.read_bytes()) != expected_sha:
            raise ValueError('Actual V2 asset bytes differ: ' + path.name)
    report = {'schemaVersion': 1, 'profile': PROFILE, 'status': 'PASS_ACTUAL_PUBLIC_BYTES_NOT_GAME',
              'manifestSha256': prior.sha((downloads / 'components.json').read_bytes()),
              'actualSelectedJarDownloads': len(checked), 'actualV2ApiFullDigestsAndSizes': len(ordered),
              'allModernNonDeclaredAuthorEntriesUnchanged': True, 'allRetroAuthorBytesUnchanged': True,
              'gameTestsClaimed': False, 'checked': checked}
    (downloads / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['stage', 'verify', 'verify-active', 'publish', 'verify-remote'])
    parser.add_argument('--originals', type=Path)
    parser.add_argument('--compiled', type=Path, default=ROOT / 'source/e4steam/release/0.3.4')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist' / PROFILE)
    parser.add_argument('--ci-run')
    parser.add_argument('--downloads', type=Path)
    args = parser.parse_args()
    if args.command == 'verify-active':
        verify_active()
    elif args.originals is None:
        parser.error('--originals is required for stage/verify')
    elif args.command == 'stage':
        stage(args.originals, args.compiled, args.out)
    elif args.command == 'verify':
        verify_profile(args.originals, args.compiled, args.out)
    elif args.command == 'publish':
        if not args.ci_run:
            parser.error('--ci-run is required before publication')
        publish(args.originals, args.compiled, args.out, args.ci_run)
    else:
        if not args.downloads:
            parser.error('--downloads must name a new private verification directory')
        print(json.dumps(verify_remote(args.originals, args.compiled, args.out, args.downloads)))

if __name__ == '__main__':
    main()
