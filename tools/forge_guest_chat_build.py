"""Build the Forge guest timeout and optional LAN chat confirmation fixes together."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import zipfile

import forge_guest_timeout_build as guest

ROOT = guest.ROOT
GUEST_SHA = "0d907d5b24c6b28b1872926849c5cb363f79aac9071e485caa02b35e5ffd5e55"
COMBINED_SHA = "6739b9feec81bc49e77bcb3e7e5ed58edec37ef50c64c5a3d88d432ee29bf179"
MIRROR_CLASS = "link/e4steam/Mirror.class"
MIRROR_PIN = "079d726686f5c9b02d601a4743d286ed2deeff930e4516cc03b7dc319cc426bc"
MIRROR_SOURCE = ROOT / "source/e4steam/common/src/main/java/link/e4steam/Mirror.java"
MIRROR_SOURCE_PIN = "74930c9abb52401ae7dcc4ae09604fc80d236111c833ee852afd598a71ad929d"
RECIPE = ROOT / "tools/ForgeChatMirror.java"
GAME_PINS = {
    "1.18.2": "c6cb2530269663ed0d4b9b53815abc521e26b4cc895aef58257763e1ae87a12f",
    "1.19.2": guest.GAME_SHA,
    "1.20.1": "e2e940fe7ca0a9fba5a5c11ad2cf3e2f7df91bbf51d12af22cdde7af18adc344",
    "1.20.2": "16c4b658503655b8a8f207bde28ab3bb5d1d3d842b4388c65dde457a280f19f6",
}
CHAT_MEMBERS = [
    "net/minecraft/client/Minecraft.execute(Ljava/lang/Runnable;)V",
    "net/minecraft/client/Minecraft.f_91065_Lnet/minecraft/client/gui/Gui;",
    "net/minecraft/client/Minecraft.m_91087_()Lnet/minecraft/client/Minecraft;",
    "net/minecraft/client/gui/Gui.m_93076_()Lnet/minecraft/client/gui/components/ChatComponent;",
    "net/minecraft/client/gui/components/ChatComponent.m_93785_(Lnet/minecraft/network/chat/Component;)V",
]
LINKAGE = {version: {"srgSha256": pin, "resolvedMembers": CHAT_MEMBERS}
           for version, pin in GAME_PINS.items()}
LIBRARY_PINS = {
    **guest.LIBRARY_PINS,
    "com/mojang/authlib/3.11.49/authlib-3.11.49.jar":
        "866d5b4c844ce698552ec4eb04c47cc7760ef71e3fa2be5f9f32ddac677d6e1a",
    "com/mojang/brigadier/1.0.18/brigadier-1.0.18.jar":
        "edc4926aa4b49010f6e7ac46efd623fb38f9517344d26f6251d79a26a9738c0b",
}
SRG_NAMES = {
    "Minecraft.getInstance()": "Minecraft.m_91087_()",
    "player.getGameProfile()": "player.m_36316_()",
    "HoverEvent.Action.SHOW_TEXT": "HoverEvent.Action.f_130831_",
}


def verify(stock: Path, guest_only: Path, combined: Path) -> dict:
    guest.check_pin(guest_only, GUEST_SHA)
    guest.check_pin(combined, COMBINED_SHA)
    previous = guest.read_archive(stock, guest_only)
    with zipfile.ZipFile(guest_only) as old, zipfile.ZipFile(combined) as new:
        names = old.namelist()
        guest.require(names == new.namelist() and new.testzip() is None and old.comment == new.comment,
                      "Combined archive member order, CRC or comment differs")
        guest.require([name for name in names if old.read(name) != new.read(name)] == [MIRROR_CLASS],
                      "Combined archive must only add the chat fix to the guest fix")
        mirror = new.read(MIRROR_CLASS)
    guest.require(guest.sha(mirror) == MIRROR_PIN and mirror[:8] == bytes.fromhex("cafebabe0000003d"),
                  "Combined archive must contain the reviewed Java 17 chat fix")
    return {
        "schemaVersion": 1,
        "stockSha256": guest.STOCK_SHA,
        "guestOnlySha256": GUEST_SHA,
        "build": {"fileName": combined.name, "sha256": COMBINED_SHA, "sizeBytes": combined.stat().st_size},
        "changedEntries": sorted([*guest.CHANGED, MIRROR_CLASS]),
        "changedEntriesFromGuestOnly": [MIRROR_CLASS],
        "sourceBuiltClassSha256": {**previous["sourceBuiltClassSha256"], MIRROR_CLASS: MIRROR_PIN},
        "byteIdenticalOtherEntries": previous["byteIdenticalOtherEntries"] - 1,
        "mirrorSourceSha256": MIRROR_SOURCE_PIN,
        "forgeChatSourceRecipeSha256": guest.sha(RECIPE.read_bytes()),
        "gameLinkage": LINKAGE,
    }


def stage(stock: Path, guest_only: Path, libraries: Path, java_home: Path,
          srg: dict[str, Path], out: Path) -> None:
    guest.check_pin(guest_only, GUEST_SHA)
    guest.read_archive(stock, guest_only)
    guest.require(srg.keys() == GAME_PINS.keys(), "Supply all four reviewed Forge SRG inputs")
    for version, pin in GAME_PINS.items():
        guest.check_pin(srg[version], pin)
    for relative, pin in LIBRARY_PINS.items():
        guest.check_pin(libraries / relative, pin)
    source = MIRROR_SOURCE.read_text(encoding="utf-8")
    guest.require(guest.sha(source.encode()) == MIRROR_SOURCE_PIN, "Unreviewed Mirror source")
    for named, mapped in SRG_NAMES.items():
        guest.require(named in source, f"Missing reviewed SRG reference: {named}")
        source = source.replace(named, mapped)
    java, javac = (java_home / "bin" / (tool + (".exe" if os.name == "nt" else ""))
                   for tool in ("java", "javac"))
    java_version = guest.run([java, "-version"]).splitlines()[0]
    guest.require(java_version.startswith('openjdk version "17.0.20.1"'), "Use the reviewed JDK 17.0.20.1")
    asm_path = os.pathsep.join(str(libraries / path) for path in LIBRARY_PINS if path.startswith("org/ow2/asm/"))
    compile_path = os.pathsep.join(map(str, (guest_only, srg["1.19.2"], *(libraries / path for path in LIBRARY_PINS))))
    out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="forge-guest-chat-", dir=out) as temp:
        temp = Path(temp)
        java_source = temp / "Mirror.java"
        java_source.write_text(source, encoding="utf-8", newline="\n")
        guest.run([javac, "-encoding", "UTF-8", "--release", "17", "-cp", compile_path, "-d", temp, java_source])
        original_class, replacement = temp / "original.class", temp / "replacement.class"
        with zipfile.ZipFile(guest_only) as before:
            original_class.write_bytes(before.read(MIRROR_CLASS))
        recipe = [java, "-cp", asm_path, RECIPE]
        guest.run([*recipe, "merge", original_class, temp / MIRROR_CLASS, replacement])
        guest.check_pin(replacement, MIRROR_PIN)
        artifact = temp / guest.STOCK_NAME
        with zipfile.ZipFile(guest_only) as before, zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED,
                                                                  compresslevel=9) as after:
            after.comment = before.comment
            for member in before.infolist():
                data = replacement.read_bytes() if member.filename == MIRROR_CLASS else before.read(member.filename)
                after.writestr(copy.copy(member), data)
        receipt = verify(stock, guest_only, artifact)
        for version, game in srg.items():
            observed = guest.run([*recipe, "link", artifact, game]).splitlines()
            guest.require(observed == CHAT_MEMBERS, f"Unexpected Minecraft chat symbol set on Forge {version}")
        receipt["java"] = java_version
        (out / guest.RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8", newline="\n")
        artifact.replace(out / guest.STOCK_NAME)
    print(COMBINED_SHA)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--guest-only", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--libraries", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--srg", action="append", metavar="VERSION=JAR")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        observed = verify(args.stock, args.guest_only, args.out / guest.STOCK_NAME)
        receipt = json.loads((args.out / guest.RECEIPT).read_bytes())
        guest.require(all(receipt[key] == value for key, value in observed.items()), "Build receipt differs from JAR")
        print(COMBINED_SHA)
        return
    if not (args.libraries and args.java_home and args.srg):
        parser.error("Staging requires --libraries, --java-home and four --srg inputs")
    pairs = [entry.split("=", 1) for entry in args.srg]
    guest.require(all(len(pair) == 2 for pair in pairs), "Expected VERSION=JAR")
    srg = {version: Path(jar) for version, jar in pairs}
    guest.require(len(srg) == len(pairs), "Duplicate Forge game input")
    stage(args.stock, args.guest_only, args.libraries, args.java_home, srg, args.out)


if __name__ == "__main__":
    main()
