"""Build-time native UI profile; never mutates a running or installed pack."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import components

ROOT = Path(__file__).resolve().parent.parent
PROFILE = "native-lan-ui-v1"
SOURCE_COMMIT = "bdcea00e30ca519fa8190c0c5c04785d42b31dbc"
PAUSE = "link/e4steam/mixin/PauseScreenMixin.class"
MIXINS = "e4steam.mixins.json"
NOTICE = "META-INF/NOTICE-LANMinecraft-native-ui.txt"
REDIRECTS = {"ShareToLanScreenMixin", "MultiplayerOptionsScreenMixin", "WorldOptionsScreenMixin"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def author_index():
    """Frozen author inventories remain authoritative after active selection changes."""
    documents = [json.loads((ROOT / "releases" / (version + ".json")).read_text(encoding="utf-8"))
                 for version in ("v0.3.2", "v0.3.4")]
    builds = [build for document in documents for build in document["builds"]]
    if len(builds) != 19 or len({build["fileName"] for build in builds}) != 19:
        raise ValueError("Expected the frozen nineteen author platform artifacts")
    return builds


def find_verified(directory: Path, build: dict) -> Path:
    found = list(directory.rglob(build["fileName"]))
    if len(found) != 1:
        raise ValueError("Expected exactly one original: " + build["fileName"])
    components.verify_file(found[0], build)
    return found[0]


def has_extra_ui(archive: zipfile.ZipFile) -> bool:
    names = set(archive.namelist())
    if PAUSE in names and (b"LanSettingsScreen" in archive.read(PAUSE) or
                           b"text.e4steam_minecraft.lan.settings" in archive.read(PAUSE)):
        return True
    if MIXINS in names:
        config = json.loads(archive.read(MIXINS))
        if REDIRECTS.intersection(config.get("client", [])):
            return True
    # Retro no-op artifacts must not hide an equivalent panel caller.
    return any(b"LanSettingsScreen" in archive.read(name)
               for name in names if name.endswith(".class"))


def validate_pause(data: bytes, original: bytes):
    if data[:4] != b"\xca\xfe\xba\xbe" or data[6:8] != original[6:8]:
        raise ValueError("Source-built pause class has a different JVM target")
    if b"LanSettingsScreen" in data or b"text.e4steam_minecraft.lan.settings" in data:
        raise ValueError("The extra LAN settings entry remains in the pause class")
    if b"openInviteOverlayAsync" not in data or b"text.e4steam_minecraft.inviteFriends" not in data:
        raise ValueError("Steam invitation handling must remain")


def without_redirects(original: bytes) -> bytes:
    config = json.loads(original)
    config["client"] = [name for name in config["client"] if name not in REDIRECTS]
    return (json.dumps(config, indent=2) + "\n").encode("utf-8")


def notice(original_sha: str) -> bytes:
    return ("LANMinecraft native-lan-ui-v1 distribution, based on e4steam by Kamilchik.\n"
            "Author license, NOTICE and third-party notices are retained unchanged.\n"
            "Original artifact SHA256: " + original_sha + "\n"
            "Source commit: " + SOURCE_COMMIT + "\n"
            "Modified files: link/e4steam/mixin/PauseScreenMixin.class and e4steam.mixins.json.\n"
            "Only the additional LAN Settings widget and native-screen redirects are removed.\n"
            "Steam invitations, transport, authentication and all other original entries are retained.\n"
            "This is a declared downstream distribution, not an unmodified author release.\n").encode("utf-8")


def derive(original: Path, built: Path, target: Path, expected_sha: str):
    if sha(original.read_bytes()) != expected_sha:
        raise ValueError("Original SHA256 changed before derivation")
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(built) as compiled:
        if len(old.namelist()) != len(set(old.namelist())) or NOTICE in old.namelist():
            raise ValueError("Duplicate or already-derived original entries")
        if any(name.upper().startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC"))
               for name in old.namelist()):
            raise ValueError("Signed author artifact needs a separately reviewed signing strategy")
        pause = compiled.read(PAUSE)
        validate_pause(pause, old.read(PAUSE))
        if any(name in json.loads(compiled.read(MIXINS)).get("client", []) for name in REDIRECTS):
            raise ValueError("Source-built artifact still enables a form redirect")
        replacement = {PAUSE: pause, MIXINS: without_redirects(old.read(MIXINS))}
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for entry in old.infolist():
                output.writestr(copy.copy(entry), replacement.get(entry.filename, old.read(entry.filename)))
            entry = zipfile.ZipInfo(NOTICE, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, notice(expected_sha))
    return verify_derivative(original, built, target, expected_sha)


def verify_derivative(original: Path, built: Path, candidate: Path, expected_sha: str):
    if sha(original.read_bytes()) != expected_sha:
        raise ValueError("Original SHA256 differs from frozen author inventory")
    with zipfile.ZipFile(original) as old, zipfile.ZipFile(built) as compiled, zipfile.ZipFile(candidate) as new:
        if len(new.namelist()) != len(set(new.namelist())) or set(new.namelist()) != set(old.namelist()) | {NOTICE}:
            raise ValueError("Derivative entry set changed beyond the modification notice")
        changed = []
        for name in old.namelist():
            if old.read(name) != new.read(name):
                changed.append(name)
                if name not in {PAUSE, MIXINS}:
                    raise ValueError("Unrelated author entry changed: " + name)
        if set(changed) != {PAUSE, MIXINS}:
            raise ValueError("Expected exactly the two declared UI modifications")
        validate_pause(new.read(PAUSE), old.read(PAUSE))
        if new.read(PAUSE) != compiled.read(PAUSE) or new.read(MIXINS) != without_redirects(old.read(MIXINS)):
            raise ValueError("Derivative does not match pinned source-built UI or exact configuration edit")
        if new.read(NOTICE) != notice(expected_sha):
            raise ValueError("Missing or changed downstream modification notice")
        return {"changedEntries": sorted(changed), "addedEntries": [NOTICE],
                "unchangedOriginalEntries": len(old.namelist()) - len(changed),
                "sourceBuiltPauseSha256": sha(compiled.read(PAUSE)), "allOtherEntriesByteIdentical": True}


def stage(originals: Path, compiled: Path, output: Path):
    builds = []
    payloads = []
    for author in author_index():
        original = find_verified(originals, author)
        with zipfile.ZipFile(original) as archive:
            needs_change = has_extra_ui(archive)
        item = dict(author)
        item.update(authorVersion=author["version"], authorFileName=author["fileName"], authorSha256=author["sha256"],
                    authorSizeBytes=author["sizeBytes"], profile=PROFILE, deliveryTag="v" + author["version"])
        if needs_change:
            built = compiled / author["fileName"]
            filename = author["fileName"][:-4] + "-lanmc-native-ui.1.jar"
            target = output / filename
            evidence = derive(original, built, target, author["sha256"])
            item.update(fileName=filename, sizeBytes=target.stat().st_size, sha256=sha(target.read_bytes()),
                        deliveryTag=PROFILE,
                        downloadUrl="https://github.com/MarkZamore/e4steam/releases/download/" + PROFILE + "/" + filename,
                        derivation={"type": "source-built-native-ui-removal", "sourceCommit": SOURCE_COMMIT, **evidence})
            payloads.append(filename)
        else:
            item["derivation"] = {"type": "byte-identical-author-artifact", "uiAbsent": True}
        builds.append(item)
    if len(payloads) != 6 or sum(item["derivation"]["type"] == "byte-identical-author-artifact" for item in builds) != 13:
        raise ValueError("Unexpected original UI matrix; review rather than skipping a platform")
    manifest = {"schemaVersion": 2, "componentId": "e4steam", "publisher": "MarkZamore",
                "profile": PROFILE, "sourceCommit": SOURCE_COMMIT,
                "sourcePatchSha256": sha((ROOT / "source/native-ui.patch").read_bytes()), "builds": builds}
    output.mkdir(parents=True, exist_ok=True)
    (output / "components.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    (output / "SHA256SUMS.txt").write_text(components.checksums(builds), encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "source/native-ui.patch", output / "native-ui.patch")
    shutil.copyfile(ROOT / "source/UPSTREAM.json", output / "UPSTREAM.json")
    print("Staged profile: six declared derivatives, thirteen exact author no-op variants")
    return manifest


def verify_profile(originals: Path, compiled: Path, output: Path):
    # Reproduce into a separate owned directory before any remote mutation;
    # output files, frozen author inputs and source-built class must all agree.
    with tempfile.TemporaryDirectory(prefix="e4steam-native-ui-verify-") as directory:
        expected = Path(directory)
        manifest = stage(originals, compiled, expected)
        expected_names = {path.name for path in expected.iterdir()}
        if {path.name for path in output.iterdir()} != expected_names:
            raise ValueError("Staged native UI asset set differs")
        for name in expected_names:
            if (expected / name).read_bytes() != (output / name).read_bytes():
                raise ValueError("Staged native UI bytes differ: " + name)
        return manifest


def publish(originals: Path, compiled: Path, output: Path):
    verify_profile(originals, compiled, output)
    repository = "MarkZamore/e4steam"
    probe = subprocess.run(["gh", "api", "repos/" + repository + "/releases/tags/" + PROFILE],
                           capture_output=True, text=True, encoding="utf-8")
    if probe.returncode:
        if "404" not in probe.stderr:
            raise RuntimeError(probe.stderr.strip())
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        components.gh("release", "create", PROFILE, "--repo", repository, "--target", commit,
                      "--title", "e4steam native LAN UI profile v1", "--notes-file", ROOT / "NATIVE-UI.md")
        release = json.loads(components.gh("api", "repos/" + repository + "/releases/tags/" + PROFILE))
    else:
        release = json.loads(probe.stdout)
    existing = {asset["name"]: asset for asset in release["assets"]}
    ordered = sorted(output.glob("*.jar")) + [output / "native-ui.patch", output / "UPSTREAM.json",
                                              output / "SHA256SUMS.txt", output / "components.json"]
    for path in ordered:
        if path.name in existing:
            asset = existing[path.name]
            if asset["size"] != path.stat().st_size or asset.get("digest") != "sha256:" + sha(path.read_bytes()):
                raise ValueError("Conflicting immutable profile asset: " + path.name)
    for path in ordered:
        if path.name not in existing:
            components.gh("release", "upload", PROFILE, path, "--repo", repository)
            print("Uploaded", PROFILE, path.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["stage", "verify", "publish"])
    parser.add_argument("--originals", type=Path, required=True)
    parser.add_argument("--compiled", type=Path, default=ROOT / "source/e4steam/release/0.3.4")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / PROFILE)
    args = parser.parse_args()
    if args.command == "stage":
        stage(args.originals, args.compiled, args.out)
    elif args.command == "verify":
        verify_profile(args.originals, args.compiled, args.out)
    else:
        publish(args.originals, args.compiled, args.out)


if __name__ == "__main__":
    main()
