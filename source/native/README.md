# LANMinecraft native Steam bridge

This Apache-licensed Rust crate connects a native game to a Steam friends lobby over Valve's authenticated P2P networking sockets. A pack supplies the game listener, runtime variant and in-game controls. The launcher supplies the Steam account and nickname. The bridge compares the Steam API's active account with that launch identity before creating or joining any session.

The native lobby publishes the actual world title and launcher nickname. Discovery checks fresh metadata from Steam friends and filters by the exact runtime variant. Before dialing, the guest confirms that the actual lobby owner is the advertised friend. The host authorizes the Steam-authenticated remote account against current friends-lobby membership and a random sharing generation. The local game claims the bridge's loopback address once, before assigning that peer a portable identity. Bind the game listener to loopback and refuse login without a claim while Steam sharing is active.

The bridge uses Steam virtual port 481. The Java component continues using its own e4steam wire protocol and the launcher retains its world-transfer transport. Native game variants expose only mutually compatible worlds. When the world stops or the process exits, the bridge drops connections and closes its Steam lobby. Keep the bridge scoped to the game process and call `unpublish()` when leaving a hosted world.

The host advertises a copyable `<lobby-id>.steam` address in Steam's `connect` rich presence and can open Valve's invite picker with `invite_friends()`. Both the lobby and rich-presence join callbacks go through fresh friend-world discovery and exact variant validation before `take_join_request()` returns a lobby. Joining still verifies the actual owner and the existing authenticated connection handshake. The original `lanmc-steam:<lobby-id>` address remains accepted. This flow follows the Java e4steam component's `SteamLobbyManager` invitation lifecycle; the native pack uses Rust bindings and Valve APIs, not the Java JAR. Consuming games must poll join requests on their UI thread, save/leave any current world, and call the normal connection path. Expose host actions only for the currently published lobby so stale chat messages cannot control a later session.

## Building on Windows

Set `CARGO_TARGET_DIR` to the task's approved build directory. Build from the locked inputs with `cargo build --locked`. Place the verified Valve SDK DLL next to the consuming game's executable. Use `Get-VerifiedSteamDll.ps1` to locate and validate the exact DLL in the locked `steamworks-sys` dependency. Keep `STEAM_SDK_LOCATION` unset so the build uses the reviewed SDK.

For tests, add the directory containing the verified DLL to the command's `PATH` and run `cargo test --locked --all-targets` and `cargo clippy --locked --all-targets -- -D warnings`. These checks cover build/linking and validation of identities, publication metadata and the sharing-generation handshake. Steam discovery, relay, world persistence and in-game profiles require a separate two-account run against the compiled pack.

## Third-party components

- [steamworks-rs](https://github.com/Noxime/steamworks-rs), locked Rust bindings `steamworks` 0.13.1 and `steamworks-sys` 0.13.0 under MIT or Apache-2.0. Their Rust licensing is separate from Valve's SDK.
- [Valve Steamworks SDK redistributable](https://partner.steamgames.com/doc/sdk/api), SDK 1.64, shipped alongside the consuming Windows executable. The locked SDK member is `lib/steam/redistributable_bin/win64/steam_api64.dll` in [steamworks-sys revision bfb3326](https://github.com/Noxime/steamworks-rs/tree/bfb3326d13c7c6d773adbb1d7c731cc131c433c7/steamworks-sys). It is signed by Valve Corp. and contains 317,080 bytes. SHA256 is `eb17909a76668cf9ae0b92a618a34a50f6c73d3a6787cb4dd8ce36a8b10bfb75`.
