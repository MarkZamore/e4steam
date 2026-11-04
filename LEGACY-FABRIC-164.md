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

## Reproduction and publication

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

## Observed validation, 4 November 2026

Source revision `a6c9580b00106035586e7dc0ed828202c0ff76e8` produces
`e4steam-legacy-fabric-mc1.6.4-v0.3.4-lf164.1.jar`, 2,281,194 bytes,
SHA256 `a35e616ee93e4cb9f6a9c2f0e9a06a36648e89639a07a6c47780b30c1b0c394e`.
The source and policy suite passed 36 assertions, including untrusted socket
denial, no registry-derived authentication, duplicate-account side effects,
ambiguous labels, strict UTF-8, display-marker rejection, manual-server
preservation and consumption of stale synthetic join keys.

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
