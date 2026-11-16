"""Stage and verify the narrow modern Forge guest timeout selection."""

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
FILE = "e4steam-forge-mc1.18.2-1.20.2-v0.3.4-lanmc-native-ui.2.jar"
STOCK_SHA256 = "3f397fc193f14d3c543b5ef9b4613bc149a21ca8e14bd93c39de3d1bc6f9553c"
RECEIPT = "build-receipt.json"
RELEASE_URL = f"https://github.com/MarkZamore/e4steam/releases/download/{TAG}/"
GUEST_CLASSES = {
    "link/e4steam/steam/SteamGuestJoinState.class",
    "link/e4steam/steam/SteamLobbyManager.class",
    "link/e4steam/steam/SteamRuntime.class",
}


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


def read_receipt(data):
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
    require(isinstance(changed, list) and sorted(changed) == sorted(GUEST_CLASSES)
            and isinstance(classes, dict) and set(classes) == GUEST_CLASSES
            and all(is_sha(digest, 64) for digest in classes.values()),
            "Expected exactly three source-built guest classes")
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
    catalog = copy.deepcopy(baseline)
    catalog.update(profile=PROFILE, sourceCommit=source_commit)
    for row in all_rows(catalog):
        row["profile"] = PROFILE
    target = next(row for row in catalog["builds"] if row["fileName"] == FILE)
    target.update(sizeBytes=build["sizeBytes"], sha256=build["sha256"],
                  deliveryTag=TAG, downloadUrl=RELEASE_URL + FILE)
    prior_derivation = old["derivation"]
    target["derivation"].update(
        sourceCommit=source_commit,
        baseline={**{key: old[key] for key in ("fileName", "sizeBytes", "sha256", "downloadUrl", "deliveryTag")},
                  "sourceCommit": prior_derivation["sourceCommit"]},
        changedEntries=sorted(set(prior_derivation["changedEntries"]) | GUEST_CLASSES),
        sourceBuiltClassSha256={**prior_derivation["sourceBuiltClassSha256"], **classes},
        sourceBuildReceipt={"fileName": RECEIPT, "sizeBytes": len(receipt_data),
                            "sha256": sha256(receipt_data), "downloadUrl": RELEASE_URL + RECEIPT},
    )
    return catalog


def verify_artifact(path, receipt_data):
    build, classes = read_receipt(receipt_data)
    require(path.stat().st_size == build["sizeBytes"] and components.digest(path) == build["sha256"],
            "Forge guest artifact differs from its size or SHA256 pin")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and archive.testzip() is None,
                "Forge guest artifact has duplicate or corrupt entries")
        for name, digest in classes.items():
            require(name in names and sha256(archive.read(name)) == digest,
                    f"Forge guest class differs from its SHA256 pin: {name}")


def verify_active(root, active):
    baseline = read_baseline(root)
    receipt = (root / "releases" / TAG / RECEIPT).read_bytes()
    require(active == candidate_index(baseline, receipt, active["sourceCommit"]),
            "Active Forge guest profile differs from the reviewed single-row update")
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt_data = args.receipt.read_bytes()
    verify_artifact(args.jar, receipt_data)
    catalog = candidate_index(read_baseline(ROOT), receipt_data, args.source_commit)
    payload = (json.dumps(catalog, indent=2, sort_keys=True) + "\n").encode()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "profiles").mkdir()
    (args.out / "components.json").write_bytes(payload)
    (args.out / "profiles" / f"{PROFILE}.json").write_bytes(payload)
    (args.out / "SHA256SUMS.txt").write_bytes(components.checksums(all_rows(catalog)).encode())
    print(f"Staged {len(catalog['builds'])} regular and {len(catalog['java8Builds'])} optional builds")


if __name__ == "__main__":
    main()
