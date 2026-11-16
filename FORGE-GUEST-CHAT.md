# Forge guest timeout and LAN chat confirmation

The modern Forge release combines the guest connection fix with a guard around
the optional message that a Steam world is ready. The notification callback logs
runtime and linkage failures raised while displaying the message. The hosting
condition and the native server publication remain outside that guard.

Build with Python 3.12.10 and Temurin 17.0.20.1. Download the original
`native-lan-ui-v2` and `forge-modern-guest-v1` artifacts using the same basename,
`e4steam-forge-mc1.18.2-1.20.2-v0.3.4-lanmc-native-ui.2.jar`. The build checks both
archives against their respective release pins.

```powershell
python -B tools/forge_guest_chat_build.py --stock <original-jar> --guest-only <guest-v1-jar> --out <new-output-directory> --libraries <shared-libraries> --java-home <JDK-17.0.20.1> --srg 1.18.2=<jar> --srg 1.19.2=<jar> --srg 1.20.1=<jar> --srg 1.20.2=<jar>
python -B tools/forge_guest_chat_build.py --stock <original-jar> --guest-only <guest-v1-jar> --out <output-directory> --verify-only
```

Use the launcher's installed SRG client JARs for the first three versions and the
Forge 48.1.0 AT-patched merged SRG JAR from Architectury Loom for 1.20.2. The build
verifies these inputs by SHA256, compiles `Mirror.java`, transplants the
chat callback methods and checks the exact target symbols on all four versions.
It verifies that `Mirror.class` is the sole archive change relative to the
guest-only release. That release's three guest lifecycle classes are retained
byte for byte. The resulting build SHA256 is
`6739b9feec81bc49e77bcb3e7e5ed58edec37ef50c64c5a3d88d432ee29bf179`.
