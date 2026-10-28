"""Stage, publish and verify exact author binaries in the single own-account mirror."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPOSITORY = 'MarkZamore/e4steam'


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load_index(path=ROOT / 'components.json'):
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('schemaVersion') != 1 or document.get('componentId') != 'e4steam':
        raise ValueError('Unsupported component index')
    seen = set()
    for build in document['builds']:
        name, version = build['fileName'], build['version']
        if (not re.fullmatch(r'e4steam-[A-Za-z0-9._+-]+\.jar', name) or name.casefold() in seen or
                not re.fullmatch(r'\d+\.\d+\.\d+', version) or not name.endswith('-v' + version + '.jar')):
            raise ValueError('Invalid or duplicate author filename: ' + name)
        seen.add(name.casefold())
        if not re.fullmatch(r'[a-f0-9]{64}', build['sha256']) or build['sizeBytes'] <= 0:
            raise ValueError('Invalid exact-byte pin: ' + name)
        suffix = '/releases/download/v' + version + '/' + name
        if (build['downloadUrl'] != 'https://github.com/' + REPOSITORY + suffix or
                build['upstreamDownloadUrl'] != 'https://github.com/Kamilhik/e4steam' + suffix):
            raise ValueError('Unexpected delivery or provenance URL: ' + name)
    return document


def verify_file(path, build):
    if path.stat().st_size != build['sizeBytes'] or digest(path) != build['sha256']:
        raise ValueError('Size/SHA-256 mismatch: ' + build['fileName'])
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not any('license' in name.lower() for name in names) or not any('notice' in name.lower() for name in names):
            raise ValueError('Author license/notice entries are missing: ' + build['fileName'])


def fetch(url, path):
    request = urllib.request.Request(url, headers={'User-Agent': 'LANMinecraft-SharedComponent/1.0'})
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        with urllib.request.urlopen(request, timeout=45) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def checksums(builds):
    return ''.join(build['sha256'] + '  ' + build['fileName'] + '\n'
                   for build in sorted(builds, key=lambda item: item['fileName']))


def version_manifest(document, version):
    return {**document, 'releaseVersion': version,
            'builds': [build for build in document['builds'] if build['version'] == version]}


def stage(output, cache):
    document = load_index()
    for version in sorted({build['version'] for build in document['builds']}):
        subset = version_manifest(document, version)
        directory = output / ('v' + version)
        directory.mkdir(parents=True, exist_ok=True)
        for build in subset['builds']:
            target = directory / build['fileName']
            if cache is not None:
                original = cache / build['fileName']
                verify_file(original, build)
                shutil.copyfile(original, target)
            elif not target.exists():
                fetch(build['upstreamDownloadUrl'], target)
            verify_file(target, build)
        (directory / 'SHA256SUMS.txt').write_text(checksums(subset['builds']), encoding='utf-8', newline='\n')
        (directory / 'components.json').write_text(json.dumps(subset, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    verify(output)


def verify(output):
    document = load_index()
    for version in sorted({build['version'] for build in document['builds']}):
        subset = version_manifest(document, version)
        directory = output / ('v' + version)
        actual = {path.name for path in directory.iterdir() if path.is_file()}
        expected = {build['fileName'] for build in subset['builds']} | {'SHA256SUMS.txt', 'components.json'}
        if actual != expected:
            raise ValueError('Staged file set differs from the versioned manifest: v' + version)
        if json.loads((directory / 'components.json').read_text(encoding='utf-8')) != subset:
            raise ValueError('Staged component manifest differs: v' + version)
        if (directory / 'SHA256SUMS.txt').read_text(encoding='utf-8') != checksums(subset['builds']):
            raise ValueError('Staged checksum file differs: v' + version)
        for build in subset['builds']:
            verify_file(directory / build['fileName'], build)
    print('Verified staged author JARs:', len(document['builds']), flush=True)


def gh(*arguments):
    return subprocess.check_output(['gh', *map(str, arguments)], text=True, encoding='utf-8')


def publish(output):
    verify(output)
    document = load_index()
    for version in sorted({build['version'] for build in document['builds']}):
        tag = 'v' + version
        directory = output / tag
        probe = subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + '/releases/tags/' + tag], capture_output=True, text=True, encoding='utf-8')
        if probe.returncode:
            if '404' not in probe.stderr:
                raise RuntimeError(probe.stderr.strip())
            gh('release', 'create', tag, '--repo', REPOSITORY, '--target', 'main', '--title', 'Shared e4steam ' + version,
               '--notes', 'Unmodified author JARs for LANMinecraft. Exact pins and attribution are in components.json. Upload order: JARs, SHA256SUMS.txt, then components.json. No game was launched for this mirror.')
            release = json.loads(gh('api', 'repos/' + REPOSITORY + '/releases/tags/' + tag))
        else:
            release = json.loads(probe.stdout)
        existing = {asset['name']: asset for asset in release['assets']}
        subset = version_manifest(document, version)
        # All author payloads first. Exact, immutable names are never clobbered.
        ordered = [directory / build['fileName'] for build in subset['builds']]
        ordered += [directory / 'SHA256SUMS.txt', directory / 'components.json']
        for path in ordered:
            if path.name in existing:
                asset = existing[path.name]
                if asset['size'] != path.stat().st_size or asset.get('digest') != 'sha256:' + digest(path):
                    raise ValueError('Conflicting immutable release asset: ' + path.name)
                continue
            gh('release', 'upload', tag, path, '--repo', REPOSITORY)
            print('Uploaded', tag, path.name, flush=True)


def verify_remote(output):
    document = load_index()
    output.mkdir(parents=True, exist_ok=True)

    def check(build):
        path = output / build['fileName']
        fetch(build['downloadUrl'], path)
        verify_file(path, build)
        return {key: build[key] for key in ('fileName', 'version', 'sizeBytes', 'sha256', 'downloadUrl')}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        verified = list(executor.map(check, document['builds']))
    report = {'schemaVersion': 1, 'repository': REPOSITORY, 'verifiedCount': len(verified), 'verified': verified}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Verified downloaded own-account JARs:', len(verified), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('stage', 'verify', 'publish', 'verify-remote'))
    parser.add_argument('--cache', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if args.command == 'stage':
        stage(args.out, args.cache)
    elif args.command == 'verify':
        verify(args.out)
    elif args.command == 'publish':
        publish(args.out)
    else:
        verify_remote(args.out / 'remote-downloads')


if __name__ == '__main__':
    main()
