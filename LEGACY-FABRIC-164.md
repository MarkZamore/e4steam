# Legacy Fabric 1.6.4 source port

This downstream module targets Minecraft 1.6.4 / Fabric Loader 0.18.2 with
Legacy Fabric intermediary mappings. It is built from source; there is no
claimed author JAR for this previously unpublished platform. Shared Steam/TCP,
native loading, lobby authorization and connection ownership come from the
vendored Kamilhik/e4steam v0.3.4 source commit
`bdcea00e30ca519fa8190c0c5c04785d42b31dbc`. The nineteen existing delivery JARs
are retained byte for byte, with their original source and author provenance.

The isolated `source/e4steam/legacy-fabric-1.6.4` module owns version-specific
native symbols, client-thread dispatch, lifecycle, login, discovery and labels.
The build explicitly includes the neutral API/lobby/pacer source closure which
the upstream retro recipe does not include. Three neutral retro adapters are
extended with the matching current callbacks: loader pacing, optional native
login tracking, and join-timeout dispatch. Existing adapters opt out of native
login tracking unless their platform implements it.

## Ownership and native behavior

Remote identity is derived only from the authenticated live Steam bridge
owning the exact native TCP remote endpoint. Login rechecks the binding before
native player creation; admission checks again before native NBT loading.
An unknown loopback endpoint or an alias registry entry does not grant trust.
Duplicate account admission refuses the new connection before the native
duplicate-player kick path. The native name is `s` followed by thirteen
zero-padded unsigned base36 Steam ID digits, within the legacy username limit.

The local owner is proven through the actual integrated listener's paired
MemoryConnection and its native NetClientHandler/Minecraft owner objects.
Only that native local path may use the launcher's cached local profile while
Steam is unavailable. When the runtime knows the current Steam account it must
match that binding. This exception cannot authenticate TCP guests.

`minecraft.portable.legacy.registry` points at UTF-8 rows
`steamID|nativeName|displayNameBase64UTF8|portableUUID`. The local profile UUID
is the existing `minecraft.portable.identity.localPlayer` property. The
registry supplies labels and skin/profile IDs; it cannot create a live bridge.
Native storage, ownership, scoreboard keys and protocol names remain canonical.
Chat/entity display and tab labels use the display name. Single-token unique
online aliases work in native player lookups/completion. Ambiguous names and
historical names containing whitespace retain usable canonical command tokens;
the native command parser is not replaced.

The Open to LAN pause action initializes the actual native Share screen and
invokes its native Start action without displaying the intermediate form.
The module does not hardcode Nightmare settings or replace the pause menu.
Native/author callbacks, including Nightmare's no-escape restrictions, remain.
The successful Russian announcement uses the modern "Порт локального сервера:
%s" wording with the original bound port. Other languages and the failure
message use the native text. Once the integrated world is published, the same
pause slot opens a native notice explaining that player reports are unavailable
in Minecraft 1.6.4. Its Done button returns to the original pause screen.
The listener binds explicitly to IPv4 loopback, matching the common Steam
bridge. Shutdown closes the relay and local proof. Discovery adds transient
Steam friends' worlds to the real multiplayer list; stale synthetic addresses
are consumed and never sent to DNS. Friendship, lobby owner, protocol and exact
Minecraft compatibility are checked before the normal author join path.
The shared `lanminecraft_player`, `lanminecraft_world` and
`lanminecraft_display=1` lobby protocol supplies the verified launcher host
label and captured native world title. Publication captures client/server data
on their own ticks, then rechecks the current world and exact Steam hosting
generation before writing metadata. Steam persona names are not substituted.
Only the managed screen's automatic LAN collection is replaced; saved/manual
servers remain native. Synthetic rows show the world, host and Steam service,
and their internal DNS-shaped join keys are never drawn as addresses.

Log4j 2.19.0 remains the platform's explicitly declared dependency. The port
does not bundle Log4j classes or downgrade BTW's nested libraries. Steamworks4j
1.10.0 and the required desktop JNA/native subset are pinned by the recipe.
Mixin implementation classes stay in the mandatory Mixin configuration and
are excluded from direct helper preloading, as required by Knot.

## Historical v1/V3 reproduction and publication

Run the commands in this section from source-release commit
`112a3a188c8757fa9157826ecbf93c967f092320`. Current source uses the v2
recipe documented below.

Build with JDK 25.0.2, targeting Java 17:

```text
python -B tools/legacy_fabric_164.py --java-home C:/Tools/jdk-25.0.2
```

The build emits the deterministic JAR, source/class/dependency/recipe receipt
and runs ownership-negative policy checks. These checks do not claim a real
authenticated Steam session. Full client and native integration results belong
to the pack's QA report; two-account Steam gameplay requires actual accounts.
The receipt pins the committed LF NOTICE text and explicitly records its
deterministic CRLF materialization inside the JAR, independent of Git autocrlf.

After committing the reviewed source, stage the new frozen twenty-target
profile without changing the active index or publishing:

```text
python -B tools/legacy_fabric_164_profile.py --source-commit <full40commit>
```

The staging command verifies that every build input exists byte for byte in
that commit, verifies the class pins, and retains all nineteen prior payload
and provenance fields. Only their active profile label advances to V3.
The new target uses the immutable `legacy-fabric-164-v1` delivery tag; its
receipt has its own size/SHA. Publish payload and receipt before the index.
Do not activate the profile or the pack card merely because compilation passed.

CI keeps the existing modern Java 21 Linux/Windows build matrix and its V1/V2
reproduction steps. `tools/active_profile.py` dispatches historical V2 validation
to the unchanged V2 verifier and checks V3 against exact frozen index/checksum
bytes and receipt provenance. A separate Linux/Windows job uses Microsoft JDK
25.0.2 and Python 3.12.10, builds into a fresh directory, and runs:

```text
python -B tools/legacy_fabric_164_profile.py --out <fresh-build-output> --verify-frozen
```

ZIP host metadata, compression level, POSIX source ordering and JSON key order
are explicit. The published JAR remains the same `a35e...` artifact; canonical
receipt/profile bytes also have to match across both CI operating systems.
V3 publication requires a successful exact-commit run covering all four matrix
jobs. The historical V2 publisher retains its original two-job release guard
and is not the V3 publication entrypoint.

## Observed validation, 4 November 2026

Source/recipe revision `204ed62ccb832f2756512c30026b812352a57d1b` produces
`e4steam-legacy-fabric-mc1.6.4-v0.3.4-lf164.1.jar`, 2,281,194 bytes,
SHA256 `a35e616ee93e4cb9f6a9c2f0e9a06a36648e89639a07a6c47780b30c1b0c394e`.
The source and policy suite passed 36 assertions, including untrusted socket
denial, no registry-derived authentication, duplicate-account side effects,
ambiguous labels, strict UTF-8, display-marker rejection, manual-server
preservation and consumption of stale synthetic join keys.
The native Java source is unchanged from `a6c9580b00106035586e7dc0ed828202c0ff76e8`;
the later recipe revision fixes canonical LF/JSON ordering and cross-host ZIP
metadata without changing the JAR. The local source-tool suite passes 45 tests.
The exact source-release commit `112a3a188c8757fa9157826ecbf93c967f092320`
passed all four jobs in GitHub run `41890737109`: the existing modern matrix
and both pinned Legacy Fabric reproduction jobs. This proves Linux/Windows
source reproduction, not Linux/macOS game runtime or two-account Steam play.

The pack's independent `final-native-05` full client used that exact port JAR
with BTW CE 3.1.1 and Nightmare 1.1.6. It entered the QA world, accepted the
canonical native local host, published through the actual pause button without
the intermediate Share form, and saved/quit normally with exit code 0. The
actual own-account Steam lobby supplied matching owner/generation/native port
and the three exact launcher-host/native-world description fields. A plain TCP
protocol-78 login without an authenticated Steam bridge was denied and the
native player count remained one. Native shutdown returned the transport to
NONE and emptied the publication/task registries.

The real lazy-loaded multiplayer/slot renderer and FontRenderer observed
world, host and Steam labels for an explicitly synthetic UI fixture. The
automatic LAN insertion gate and stale-join cancellation were also exercised.
This is native rendering-path evidence, not a second friend's discovered world
or an authenticated peer connection. No internal `.invalid` address was drawn.

This component owns presentation labels, not player meshes, cape rendering or
the pack's selected-skin bridge. The separate pack helper has its own native
skin/title evidence. No cape or remote-player visual PASS is claimed here;
canonical protocol names also require separate exact-caller compatibility for
legacy nickname-triggered rendering/game rules. Two-account Steam P2P, guest
gameplay and a real change of host between two people remain **NOT RUN** because
only one PC/account was available. They must not be inferred from the host,
negative-login, source, or synthetic-renderer checks above.

On 5 November 2026, the four immutable public port release assets were fetched
into a fresh verification directory and compared byte for byte with the frozen
selection. All twenty selected delivery JARs were independently streamed and
matched by exact size/SHA256, totalling 64,761,382 bytes. The sanitized public
inventory is recorded in `profiles/native-lan-ui-v3-public-verification.json`.
The canonical active index and checksum inventory now match frozen V3 bytes;
no published payload or build recipe was changed for activation.

## Immutable Legacy Fabric v3 delivery

The v3 port retains the v2 dependencies and platform range. Its native 1.6.4
chat now shows a localized ready heading, green copyable Steam address, blue
invitation control and red stop control. Controls use native font widths,
wrapping, chat scale and scroll coordinates. Only launcher-owned local chat
IDs belonging to the current exact hosting session can dispatch an action;
copied server text and stale session rows cannot dispatch local commands.
Minecraft 1.6.4 lacks modern rich chat events, so the adapter implements this
at the native chat hit-test boundary rather than browser links.

Native `commands.*` translation arguments display registered player labels.
Only whole known canonical player tokens are substituted, on a cloned argument
array. Command parsing, permission keys, stored profiles and unknown names retain
their original values. No content mechanics or external libraries were updated.

The V5 frozen profile replaces only the Legacy Fabric row of the exact V4
selection (SHA256 `399842903aaa1cad641e703cc06ec38417fbefdc6fbdf9a89f62d447d64be50e`).
Historical v1/V3 and v2/V4 tags, JARs and receipts remain immutable. The staging,
four-job CI and public-byte verification procedure below applies using
`legacy-fabric-164-v3`, `native-lan-ui-v5` and the `lf164.3` JAR name.

Native candidate acceptance: 47 policy assertions and 46 source-tool tests;
Minecraft 1.6.4 / Java 17 full-client save/reentry with the exact v3 candidate.
The native chat hit-test dispatched copy/invite/stop and rejected a stale row;
the actual command translation displayed two synthetic registered names while
preserving the original arguments. This fixture suppressed Steam startup and
command execution, used no physical mouse input and did not use personal worlds.
It does not prove a real invitation, clipboard transfer, or two-account Steam
gameplay. The pack records its own difficulty/Creative command changes separately.

## Staged immutable Legacy Fabric v4 delivery

The v4 candidate (`0.3.4-lf164.4`, `legacy-fabric-164-v4`, profile V6) also covers
native operator feedback. `ServerCommandManager` (`class_765.method_2767`)
constructs `chat.type.admin` with the sender's canonical name and a nested
command-result component. Only the first argument of that exact two-argument
shape is mapped to a registered display name. The body, original argument array,
ordinary chat, unknown senders, command parsing and permission checks retain
their native values. No storage identity, author JAR, external library or
content mechanic changes are part of this port update.

V6 starts from the exact V5 profile SHA256
`c718ce3b1b817b63faadc11745057d008c10e5ad6f3852c1cfb8b666b31295f9`
and replaces only its Legacy Fabric row. All nineteen other delivery pins and
historical v1/V3, v2/V4 and v3/V5 receipts remain unchanged. The same four-job
CI, native acceptance, payload-before-index publication and all-target public
byte verification gates apply with the new v4/V6 names. The root active index
remains V5 until the candidate is accepted and its immutable public bytes pass
verification. Source policy coverage is 55 assertions, including native admin
sender mapping, nested-body preservation and unknown/malformed negatives.

## Historical immutable Legacy Fabric v2 delivery

The current build recipe emits `e4steam-legacy-fabric-mc1.6.4-v0.3.4-lf164.2.jar`.
Its Fabric author version and platform range stay compatible. Historical v1/V3
bytes and receipts remain frozen. To reproduce v1, use its original source-release
commit above. A new twenty-target V4 selection starts from the exact published
V3 bytes and replaces only the Legacy Fabric row. The nineteen other payloads,
URLs, checksums and per-row source provenance remain as published.

Build with the pinned Microsoft JDK 25.0.2 and Python 3.12.10 into the assigned
task staging directory. Run native acceptance against that exact JAR. Commit
the reviewed code and recipe, then stage the release profile from that commit:

```powershell
python -B tools/legacy_fabric_164.py --java-home $env:JAVA_HOME --out $candidate
python -B tools/legacy_fabric_164_profile.py --out $candidate --source-commit (git rev-parse HEAD)
```

Commit the staged `native-lan-ui-v4.json` under `profiles/` and
`build-receipt.json` under `releases/legacy-fabric-164-v2/`. Keep the root
`components.json` and `SHA256SUMS.txt` on V3 until public verification. The
Linux and Windows legacy CI jobs rebuild and compare the v2 frozen bytes even
while the active index is V3. Both modern matrix jobs still run.

After all four jobs pass for the clean frozen-profile commit, check the exact
CI run with `python -B tools/legacy_fabric_164_profile.py --verify-ci <run-id>`.
Create a **new** draft GitHub release `legacy-fabric-164-v2` targeting that
commit. Upload the JAR, receipt and checksum inventory before `components.json`.
An existing asset with different bytes is a release conflict. Publish the
draft only once the four assets are ready, without replacing any historical
tag or asset. Then run:

```powershell
python -B tools/legacy_fabric_164_profile.py --verify-public
```

This verifies the API digests and streams all twenty selected public JARs and
three metadata files against their size and SHA256 pins. Save the small proof
and exact CI run reference with the activation commit. Only then copy the frozen
V4 profile and its checksum inventory to the root active files. Check with
`python -B tools/active_profile.py` before pushing activation. Compatible
launchers use the verified network selection at their next startup and keep
their embedded V3 fallback and previous exact-hash retirement pins.
