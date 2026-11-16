"""Build the narrow modern Forge guest timeout fix against the frozen delivered JAR."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
STOCK_NAME = "e4steam-forge-mc1.18.2-1.20.2-v0.3.4-lanmc-native-ui.2.jar"
STOCK_SHA = "3f397fc193f14d3c543b5ef9b4613bc149a21ca8e14bd93c39de3d1bc6f9553c"
STOCK_SIZE = 3_801_632
GAME_PATH = "net/minecraft/client/1.19.2-20220805.130853/client-1.19.2-20220805.130853-srg.jar"
GAME_SHA = "844f5333e261c3bf6a4b99c9fa3872e7beb913d087d0d759c08b3a6d236e0179"
SLF4J_PATH = "org/slf4j/slf4j-api/1.8.0-beta4/slf4j-api-1.8.0-beta4.jar"
LIBRARY_PINS = {
    SLF4J_PATH:
        "602b712329c84b4a83c40464f4fdfd0fe4238c53ef397139a867064739dbf4e0",
    "org/ow2/asm/asm/9.3/asm-9.3.jar":
        "1263369b59e29c943918de11d6d6152e2ec6085ce63e5710516f8c67d368e4bc",
    "org/ow2/asm/asm-tree/9.3/asm-tree-9.3.jar":
        "ae629c2609f39681ef8d140a42a23800464a94f2d23e36d8f25cd10d5e4caff4",
}
SOURCE_PINS = {
    "SteamGuestJoinState": "fbe00ac90be23fe13b7954c2e230267f2cc5ccc1ca21b02e088d1752e4cac520",
    "SteamLobbyManager": "48d0e8d32232da5f1058965193223c180095ab641dd065a7490200a2b19bf9aa",
    "SteamRuntime": "42f9175032d784a907def8f7978155b696d74cccfe6106cde200b08a68b6f9ce",
}
PACKAGE = "link/e4steam/steam"
SOURCE_ROOT = ROOT / "source/e4steam/common/src/main/java" / PACKAGE
TRANSPLANT = ROOT / "tools/ForgeGuestTimeout.java"
CHANGED = [f"{PACKAGE}/{name}.class" for name in SOURCE_PINS]
RECEIPT = "build-receipt.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_pin(path: Path, expected: str) -> None:
    require(sha(path.read_bytes()) == expected, f"Unreviewed input bytes: {path}")


def run(command) -> str:
    return subprocess.check_output(list(map(str, command)), text=True, encoding="utf-8",
                                   stderr=subprocess.STDOUT, timeout=90)


def read_archive(stock: Path, artifact: Path) -> dict:
    require(stock.stat().st_size == STOCK_SIZE, "Wrong stock JAR size")
    check_pin(stock, STOCK_SHA)
    with zipfile.ZipFile(stock) as before, zipfile.ZipFile(artifact) as after:
        entries = before.namelist()
        require(after.namelist() == entries and len(set(entries)) == len(entries)
                and after.testzip() is None and before.comment == after.comment,
                "Archive entry order, identity or CRC differs")
        differences = {name for name in entries if before.read(name) != after.read(name)}
        require(differences == set(CHANGED), "Unexpected changed archive entries")
        pins = {}
        for name in CHANGED:
            data = after.read(name)
            require(data[:8] == bytes.fromhex("cafebabe0000003d"), f"Unexpected class target: {name}")
            pins[name] = sha(data)
        return {"build": {"fileName": artifact.name, "sizeBytes": artifact.stat().st_size,
                          "sha256": sha(artifact.read_bytes())},
                "changedEntries": CHANGED, "sourceBuiltClassSha256": pins,
                "byteIdenticalOtherEntries": len(entries) - len(CHANGED)}


def stage(stock: Path, libraries: Path, java_home: Path, out: Path) -> None:
    require(stock.stat().st_size == STOCK_SIZE, "Wrong stock JAR size")
    check_pin(stock, STOCK_SHA)
    game = libraries / GAME_PATH
    check_pin(game, GAME_SHA)
    for relative, pin in LIBRARY_PINS.items():
        check_pin(libraries / relative, pin)
    for name, pin in SOURCE_PINS.items():
        source = SOURCE_ROOT / f"{name}.java"
        require(sha(source.read_text(encoding="utf-8").encode()) == pin, f"Unreviewed source: {source}")
    java, javac = (java_home / "bin" / (tool + (".exe" if os.name == "nt" else ""))
                   for tool in ("java", "javac"))
    java_version = run([java, "-version"]).splitlines()[0]
    require(java_version.startswith('openjdk version "17.0.20.1"'), "Use the reviewed JDK 17.0.20.1")
    asm_path = os.pathsep.join(str(libraries / path) for path in LIBRARY_PINS if path.startswith("org/ow2/asm/"))
    compile_path = os.pathsep.join(map(str, (stock, game, libraries / SLF4J_PATH)))
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="forge-guest-build-", dir=out) as scratch:
        scratch = Path(scratch)
        compiled, patched = scratch / "compiled", scratch / "patched"
        run([javac, "-encoding", "UTF-8", "--release", "17", "-cp", compile_path, "-d", compiled,
             *(SOURCE_ROOT / f"{name}.java" for name in SOURCE_PINS)])
        run([java, "-cp", asm_path, TRANSPLANT, stock, compiled, patched])
        artifact = scratch / STOCK_NAME
        with zipfile.ZipFile(stock) as before, zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED,
                                                             compresslevel=9) as after:
            require(not any(name.upper().startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC"))
                            for name in before.namelist()), "Signed JAR requires a reviewed signing strategy")
            after.comment = before.comment
            for entry in before.infolist():
                data = ((patched / entry.filename).read_bytes() if entry.filename in CHANGED
                        else before.read(entry.filename))
                after.writestr(copy.copy(entry), data)
        receipt = read_archive(stock, artifact)
        receipt.update(schemaVersion=1, stockSha256=STOCK_SHA, forgeSrgSha256=GAME_SHA,
                       java=java_version, sourceSha256=SOURCE_PINS, transplantSha256=sha(TRANSPLANT.read_bytes()))
        (out / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8", newline="\n")
        artifact.replace(out / STOCK_NAME)
    print(receipt["build"]["sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--libraries", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        expected = json.loads((args.out / RECEIPT).read_bytes())
        observed = read_archive(args.stock, args.out / STOCK_NAME)
        require(all(expected[key] == value for key, value in observed.items()), "Build receipt differs from JAR")
        print(observed["build"]["sha256"])
    else:
        if not (args.libraries and args.java_home):
            parser.error("Staging requires --libraries and --java-home")
        stage(args.stock, args.libraries, args.java_home, args.out)


if __name__ == "__main__":
    main()
