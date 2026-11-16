"""Stage and verify the modern Forge guest and chat profiles."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import zipfile

import components


ROOT = Path(__file__).resolve().parents[1]
BASE_PROFILE = "native-lan-ui-v6"
BASE_SNAPSHOT = "native-lan-ui-v6-java8-forge"
BASE_SHA256 = "4f623bf6a432d215411bcd928c6fedfc593851859d06e41f10c20b6a4da3a690"
PROFILE = "native-lan-ui-v7-forge-guest"
TAG = "forge-modern-guest-v1"
PROFILE_WITH_CHAT = "native-lan-ui-v8-forge-guest-chat"
TAG_WITH_CHAT = "forge-modern-guest-v2"
V7_SHA256 = "58c4ec822f9e1bab3db4ac58c2f70d397c16e733ceb48bfc6d5d17c09ac25245"
GUEST_ONLY_SHA256 = "0d907d5b24c6b28b1872926849c5cb363f79aac9071e485caa02b35e5ffd5e55"
FILE = "e4steam-forge-mc1.18.2-1.20.2-v0.3.4-lanmc-native-ui.2.jar"
STOCK_SHA256 = "3f397fc193f14d3c543b5ef9b4613bc149a21ca8e14bd93c39de3d1bc6f9553c"
RECEIPT = "build-receipt.json"
RELEASE_URL = "https://github.com/MarkZamore/e4steam/releases/download/"
GUEST_CLASSES = {
    "link/e4steam/steam/SteamGuestJoinState.class",
    "link/e4steam/steam/SteamLobbyManager.class",
    "link/e4steam/steam/SteamRuntime.class",
}
CHAT_CLASS = "link/e4steam/Mirror.class"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def is_sha(value, length):
    return isinstance(value, str) and re.fullmatch(f"[a-f0-9]{{{length}}}", value) is not None


def all_rows(catalog):
    return catalog["builds"] + catalog.get("java8Builds", [])


def read_baseline(root):
    data = (root / "profiles" / f"{BASE_SNAPSHOT}.json").read_bytes()
    require(sha256(data) == BASE_SHA256,
            "Frozen V6 Java 8 Forge selection differs from the reviewed publication")
    return json.loads(data)


def read_receipt(data, profile=PROFILE):
    receipt = json.loads(data)
    require(receipt.get("schemaVersion") == 1 and receipt.get("stockSha256") == STOCK_SHA256,
            "Forge guest receipt does not pin the reviewed stock JAR")
    build = receipt["build"]
    require(build["fileName"] == FILE and type(build["sizeBytes"]) is int
            and 0 < build["sizeBytes"] <= 128 * 1024 * 1024
            and is_sha(build["sha256"], 64) and build["sha256"] != STOCK_SHA256,
            "Invalid Forge guest build pin")
    changed = receipt["changedEntries"]
    classes = receipt["sourceBuiltClassSha256"]
    expected = GUEST_CLASSES
    entry_description = "three source-built guest"
    if profile == PROFILE_WITH_CHAT:
        require(receipt.get("guestOnlySha256") == GUEST_ONLY_SHA256
                and receipt.get("changedEntriesFromGuestOnly") == [CHAT_CLASS]
                and build["sha256"] != GUEST_ONLY_SHA256,
                "Forge guest/chat receipt does not pin the previous JAR and its single chat change")
        expected = GUEST_CLASSES | {CHAT_CLASS}
        entry_description = "four source-built guest/chat"
    require(isinstance(changed, list) and sorted(changed) == sorted(expected)
            and isinstance(classes, dict) and set(classes) == expected
            and all(is_sha(digest, 64) for digest in classes.values()),
            f"Expected exactly {entry_description} classes")
    return build, classes


def candidate_index(baseline, receipt_data, source_commit):
    require(baseline["profile"] == BASE_PROFILE and len(baseline["builds"]) == 20
            and len(baseline["java8Builds"]) == 2, "Unexpected V6 baseline coverage")
    require(is_sha(source_commit, 40), "Expected the exact build source commit")
    build, classes = read_receipt(receipt_data)
    old, = (row for row in baseline["builds"] if row["fileName"] == FILE)
    require(old["loaders"] == ["Forge"] and old["minimumMinecraftVersion"] == [1, 18, 2]
            and old["exclusiveMaximumMinecraftVersion"] == [1, 20, 3]
            and old["sha256"] == STOCK_SHA256 and old["deliveryTag"] == "native-lan-ui-v2",
            "Unexpected V6 Forge target or baseline pin")
    return replace_forge_build(baseline, old, build, classes, receipt_data, source_commit, PROFILE, TAG)


def replace_forge_build(baseline, old, build, classes, receipt_data, source_commit, profile, tag):
    release_url = f"{RELEASE_URL}{tag}/"
    catalog = copy.deepcopy(baseline)
    catalog.update(profile=profile, sourceCommit=source_commit)
    for row in all_rows(catalog):
        row["profile"] = profile
    target = next(row for row in catalog["builds"] if row["fileName"] == FILE)
    target.update(sizeBytes=build["sizeBytes"], sha256=build["sha256"],
                  deliveryTag=tag, downloadUrl=release_url + FILE)
    prior_derivation = old["derivation"]
    target["derivation"].update(
        sourceCommit=source_commit,
        baseline={**{key: old[key] for key in ("fileName", "sizeBytes", "sha256", "downloadUrl", "deliveryTag")},
                  "sourceCommit": prior_derivation["sourceCommit"]},
        changedEntries=sorted(set(prior_derivation["changedEntries"]) | classes.keys()),
        sourceBuiltClassSha256={**prior_derivation["sourceBuiltClassSha256"], **classes},
        sourceBuildReceipt={"fileName": RECEIPT, "sizeBytes": len(receipt_data),
                            "sha256": sha256(receipt_data), "downloadUrl": release_url + RECEIPT},
    )
    return catalog


def verify_artifact(path, receipt_data, profile=PROFILE):
    build, classes = read_receipt(receipt_data, profile)
    require(path.stat().st_size == build["sizeBytes"] and components.digest(path) == build["sha256"],
            "Forge guest artifact differs from its size or SHA256 pin")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and archive.testzip() is None,
                "Forge guest artifact has duplicate or corrupt entries")
        for name, digest in classes.items():
            require(name in names and sha256(archive.read(name)) == digest,
                    f"Forge guest class differs from its SHA256 pin: {name}")


def verify_guest_only(root, active):
    baseline = read_baseline(root)
    receipt = (root / "releases" / TAG / RECEIPT).read_bytes()
    require(active == candidate_index(baseline, receipt, active["sourceCommit"]),
            "Active Forge guest profile differs from the reviewed single-row update")
    return baseline


def read_guest_only(root):
    data = (root / "profiles" / f"{PROFILE}.json").read_bytes()
    require(sha256(data) == V7_SHA256, "Frozen V7 selection differs from the reviewed publication")
    return json.loads(data)


def candidate_with_chat(root, parent, receipt_data, source_commit):
    baseline = verify_guest_only(root, parent)
    require(is_sha(source_commit, 40), "Expected the exact build source commit")
    build, classes = read_receipt(receipt_data, PROFILE_WITH_CHAT)
    old, = (row for row in parent["builds"] if row["fileName"] == FILE)
    require(old["sha256"] == GUEST_ONLY_SHA256
            and all(classes[name] == old["derivation"]["sourceBuiltClassSha256"][name] for name in GUEST_CLASSES),
            "Forge guest/chat build changes the verified guest timeout classes")
    catalog = replace_forge_build(parent, old, build, classes, receipt_data, source_commit,
                                  PROFILE_WITH_CHAT, TAG_WITH_CHAT)
    return catalog, baseline


def verify_chat_delta(previous, candidate):
    require(components.digest(previous) == GUEST_ONLY_SHA256,
            "Previous Forge guest JAR does not match its published pin")
    with zipfile.ZipFile(previous) as original, zipfile.ZipFile(candidate) as patched:
        names = original.namelist()
        require(names == patched.namelist(), "Forge guest/chat archive changes the previous JAR inventory")
        changed = [name for name in names if original.read(name) != patched.read(name)]
        require(changed == [CHAT_CLASS], "Forge guest/chat archive must change only Mirror.class from V7")


def verify_active(root, active):
    if active["profile"] == PROFILE:
        return verify_guest_only(root, active)
    require(active["profile"] == PROFILE_WITH_CHAT, "Unsupported Forge guest catalog")
    receipt = (root / "releases" / TAG_WITH_CHAT / RECEIPT).read_bytes()
    expected, baseline = candidate_with_chat(root, read_guest_only(root), receipt, active["sourceCommit"])
    require(active == expected, "Active Forge guest/chat profile differs from the reviewed single-row update")
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=(PROFILE, PROFILE_WITH_CHAT), default=PROFILE)
    parser.add_argument("--guest-only-jar", type=Path)
    args = parser.parse_args()
    receipt_data = args.receipt.read_bytes()
    verify_artifact(args.jar, receipt_data, args.profile)
    if args.profile == PROFILE_WITH_CHAT:
        if args.guest_only_jar is None:
            parser.error("--guest-only-jar is required for the Forge guest/chat profile")
        verify_chat_delta(args.guest_only_jar, args.jar)
        catalog, _ = candidate_with_chat(ROOT, read_guest_only(ROOT), receipt_data, args.source_commit)
    else:
        catalog = candidate_index(read_baseline(ROOT), receipt_data, args.source_commit)
    payload = (json.dumps(catalog, indent=2, sort_keys=True) + "\n").encode()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "profiles").mkdir()
    (args.out / "components.json").write_bytes(payload)
    (args.out / "profiles" / f"{args.profile}.json").write_bytes(payload)
    (args.out / "SHA256SUMS.txt").write_bytes(components.checksums(all_rows(catalog)).encode())
    print(f"Staged {len(catalog['builds'])} regular and {len(catalog['java8Builds'])} optional builds")


if __name__ == "__main__":
    main()
