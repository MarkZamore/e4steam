"""Stage or verify the reviewed Forge 1.12.2 Steam login component selection."""

import argparse
import copy
import json
from pathlib import Path
import re
from zipfile import ZipFile

import components
import forge_guest_profile as guest


ROOT = Path(__file__).resolve().parents[1]
PROFILE = "native-lan-ui-v9-forge112-login"
TAG = "forge-java8-login-v1"
VERSION = "0.3.2-lanmc.2"
FILE = f"e4steam-forge-mc1.12.x-v{VERSION}.jar"
RECEIPT = "build-receipt.json"
V8_SHA256 = "0fb12fd15cffef72d8504fea81a6f90cf109f2c10a7227598573358bfba35427"
STOCK_FILE = "e4steam-forge-mc1.12.x-v0.3.2-lanmc.1.jar"
STOCK_SHA256 = "a0e0593ec5bc45ab098b0b30711edc3c4167f9bac4c65cad296d612a6c242f40"
UPSTREAM = "bdcea00e30ca519fa8190c0c5c04785d42b31dbc"


def canonical_json(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def frozen_v8(root):
    data = (root / "profiles" / f"{guest.PROFILE_WITH_CHAT}.json").read_bytes()
    guest.require(guest.sha256(data) == V8_SHA256,
                  "Frozen Forge guest and chat profile differs from the reviewed publication")
    v8 = json.loads(data)
    return v8, guest.verify_active(root, v8)


def verify_receipt(data):
    receipt = json.loads(data)
    guest.require(receipt.get("schemaVersion") == 1
                  and receipt.get("stockSha256") == STOCK_SHA256
                  and receipt.get("upstreamSourceCommit") == UPSTREAM
                  and guest.is_sha(receipt.get("sourceCommit"), 40),
                  "Invalid Forge 1.12.2 login receipt provenance")
    build = receipt["build"]
    guest.require(set(build) == {"fileName", "sizeBytes", "sha256"}
                  and build["fileName"] == FILE and type(build["sizeBytes"]) is int
                  and 0 < build["sizeBytes"] <= 128 * 1024 * 1024
                  and guest.is_sha(build["sha256"], 64) and build["sha256"] != STOCK_SHA256,
                  "Invalid new Forge 1.12.2 login artifact pin")
    pins = receipt["sourceBuiltClassSha256"]
    guest.require(isinstance(pins, dict) and pins and all(
        re.fullmatch(r"link/e4steam/(?:[A-Za-z0-9_$]+/)*[A-Za-z0-9_$]+\.class", name)
        and guest.is_sha(digest, 64) for name, digest in pins.items()
    ), "Invalid Forge 1.12.2 login JAR class inventory")
    return receipt


def read_jar(path):
    guest.require(path.name == FILE, "Unexpected Forge 1.12.2 login artifact filename")
    with ZipFile(path) as archive:
        names = archive.namelist()
        required = {"mcmod.info", "META-INF/LICENSE-e4steam.txt", "META-INF/NOTICE-e4steam.txt",
                    "e4steam.retro.mixins.json", "e4steam.retro.mixins-refmap.json", "e4steam-version.properties"}
        guest.require(len(names) == len(set(names)) and required.issubset(names) and archive.testzip() is None,
                      "Forge 1.12.2 login JAR is missing required entries or is corrupt")
        version = archive.read("e4steam-version.properties").decode("utf-8").splitlines()
        mixins = json.loads(archive.read("e4steam.retro.mixins.json"))
        guest.require(f"version={VERSION}" in version and mixins.get("compatibilityLevel") == "JAVA_8"
                      and "NetHandlerLoginServerMixin" in mixins["mixins"],
                      "Unexpected Java 8 version or login mixin metadata")
        classes = {}
        for name in names:
            if not name.endswith(".class") or name.startswith("META-INF/versions/"):
                continue
            data = archive.read(name)
            guest.require(len(data) >= 8 and data[:4] == b"\xca\xfe\xba\xbe"
                          and int.from_bytes(data[6:8], "big") <= 52,
                          f"Java 8 cannot load {path.name}!{name}")
            if name.startswith("link/e4steam/"):
                classes[name] = guest.sha256(data)
    return (
        {"fileName": path.name, "sizeBytes": path.stat().st_size, "sha256": components.digest(path)},
        classes,
    )


def make_receipt(jar, source_commit):
    build, classes = read_jar(jar)
    data = canonical_json({
        "schemaVersion": 1, "stockSha256": STOCK_SHA256, "sourceCommit": source_commit,
        "upstreamSourceCommit": UPSTREAM, "build": build, "sourceBuiltClassSha256": classes,
    })
    verify_receipt(data)
    return data


def candidate_index(v8, receipt_data):
    receipt = verify_receipt(receipt_data)
    guest.require(v8["profile"] == guest.PROFILE_WITH_CHAT and len(v8["builds"]) == 20
                  and len(v8["java8Builds"]) == 2, "Unexpected V8 component coverage")
    updated = copy.deepcopy(v8)
    updated.update(profile=PROFILE, sourceCommit=receipt["sourceCommit"])
    for row in guest.all_rows(updated):
        row["profile"] = PROFILE
    row, = (row for row in updated["java8Builds"] if row["fileName"] == STOCK_FILE)
    old_pins = row["derivation"]["sourceBuiltClassSha256"]
    pins = receipt["sourceBuiltClassSha256"]
    guest.require(row["sha256"] == STOCK_SHA256 and row["loaders"] == ["Forge"]
                  and row["minimumMinecraftVersion"] == [1, 12, 2]
                  and row["exclusiveMaximumMinecraftVersion"] == [1, 12, 3]
                  and row["derivation"]["upstreamSourceCommit"] == UPSTREAM,
                  "The V8 Forge 1.12.2 build pin differs from the reviewed publication")
    guest.require(old_pins.keys() <= pins.keys() and old_pins != pins,
                  "The Forge 1.12.2 derivative must retain the published class inventory and contain a source change")
    url = f"{guest.RELEASE_URL}{TAG}/"
    row.update(receipt["build"], version=VERSION, authorVersion=VERSION,
               deliveryTag=TAG, downloadUrl=url + FILE)
    row["derivation"].update(
        sourceCommit=receipt["sourceCommit"],
        sourceBuiltClassSha256=pins,
        sourceBuildReceipt={
            "fileName": RECEIPT, "sizeBytes": len(receipt_data),
            "sha256": guest.sha256(receipt_data), "downloadUrl": url + RECEIPT,
        },
    )
    return updated


def verify_active(root, active):
    v8, legacy = frozen_v8(root)
    receipt_data = (root / "releases" / TAG / RECEIPT).read_bytes()
    guest.require(active == candidate_index(v8, receipt_data),
                  "Active Forge 1.12.2 login profile differs from the reviewed single-row update")
    return legacy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--source-commit", help="Write an inactive receipt for this exact build source")
    parser.add_argument("--out", type=Path, help="Write candidate profile and checksums outside active files")
    args = parser.parse_args()
    v8, _ = frozen_v8(ROOT)
    if args.source_commit:
        receipt_data = make_receipt(args.jar, args.source_commit)
        candidate = candidate_index(v8, receipt_data)
        with args.receipt.open("xb") as output:
            output.write(receipt_data)
    else:
        receipt_data = args.receipt.read_bytes()
        receipt = verify_receipt(receipt_data)
        build, classes = read_jar(args.jar)
        guest.require(build == receipt["build"] and classes == receipt["sourceBuiltClassSha256"],
                      "Forge 1.12.2 login JAR differs from its receipt")
        candidate = candidate_index(v8, receipt_data)
    if args.out:
        args.out.mkdir()
        (args.out / f"{PROFILE}.json").write_bytes(canonical_json(candidate))
        (args.out / "SHA256SUMS.txt").write_bytes(components.checksums(guest.all_rows(candidate)).encode())
    print(f"Verified Forge 1.12.2 login component receipt: {args.receipt}")


if __name__ == "__main__":
    main()
