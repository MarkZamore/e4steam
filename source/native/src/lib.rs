//! Native Steam game transport for LANMinecraft packs.
//!
//! Only this worker talks to the Steam API. A game's loopback listener may
//! accept the portable profile of a guest only by claiming its established
//! bridge connection here.

mod tunnel;
mod worker;

use std::{
    collections::HashMap,
    net::{Ipv4Addr, SocketAddr, TcpListener},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc::{self, SyncSender},
    },
    thread::{self, JoinHandle},
    time::Duration,
};

use worker::Command;

const START_TIMEOUT: Duration = Duration::from_secs(10);

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WorldOffer {
    pub lobby_id: u64,
    pub title: String,
    pub host: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PeerIdentity {
    pub steam_id: u64,
    pub nickname: String,
}

#[derive(Default)]
struct Shared {
    worlds: Vec<WorldOffer>,
    claims: HashMap<SocketAddr, PeerIdentity>,
    published: bool,
    published_lobby: Option<u64>,
    pending_join: Option<u64>,
    last_error: Option<String>,
}

#[derive(Default)]
struct Control {
    stop: AtomicBool,
    sharing_epoch: AtomicU64,
}

pub struct SteamBridge {
    commands: SyncSender<Command>,
    shared: Arc<Mutex<Shared>>,
    control: Arc<Control>,
    worker: Option<JoinHandle<()>>,
}

impl SteamBridge {
    pub fn start(expected_id: u64, variant: &str, nickname: &str) -> Result<Self, String> {
        if !valid_steam_id(expected_id) || !valid_variant(variant) || !valid_nickname(nickname) {
            return Err("Invalid native Steam launch identity or runtime variant.".into());
        }
        let (commands, pending) = mpsc::sync_channel(16);
        let (started, startup) = mpsc::sync_channel(1);
        let shared = Arc::new(Mutex::new(Shared::default()));
        let control = Arc::new(Control::default());
        let worker_shared = Arc::clone(&shared);
        let worker_control = Arc::clone(&control);
        let variant = variant.to_owned();
        let nickname = nickname.to_owned();
        let worker = thread::Builder::new()
            .name("lanmc-steam-game".into())
            .spawn(move || {
                worker::run(
                    expected_id,
                    variant,
                    nickname,
                    pending,
                    started,
                    worker_shared,
                    worker_control,
                );
            })
            .map_err(|error| error.to_string())?;
        let bridge = Self {
            commands,
            shared,
            control,
            worker: Some(worker),
        };
        startup
            .recv_timeout(START_TIMEOUT)
            .map_err(|_| "Native Steam worker did not initialize.".to_string())??;
        Ok(bridge)
    }

    pub fn publish(
        &self,
        local_port: u16,
        world_title: &str,
        nickname: &str,
    ) -> Result<(), String> {
        if local_port == 0 || !valid_world_title(world_title) || !valid_nickname(nickname) {
            return Err("Invalid world information for Steam sharing.".into());
        }
        // Serialize publication with unpublish: an older queued request must
        // never reopen a world after its owner has withdrawn it.
        let mut shared = self.shared.lock().unwrap();
        self.send(Command::Publish {
            epoch: self.control.sharing_epoch.load(Ordering::Acquire),
            local_port,
            title: world_title.to_owned(),
            nickname: nickname.to_owned(),
        })?;
        shared.last_error = None;
        Ok(())
    }

    pub fn unpublish(&self) {
        // Invalidate older queued requests and in-flight lobby callbacks without
        // waiting for space in the UI command queue. The worker observes this
        // independently on its next poll.
        let mut shared = self.shared.lock().unwrap();
        self.control.sharing_epoch.fetch_add(1, Ordering::AcqRel);
        shared.claims.clear();
        shared.published = false;
        shared.published_lobby = None;
    }

    pub fn worlds(&self) -> Vec<WorldOffer> {
        self.shared.lock().unwrap().worlds.clone()
    }

    pub fn is_published(&self) -> bool {
        self.shared.lock().unwrap().published
    }

    pub fn last_error(&self) -> Option<String> {
        self.shared.lock().unwrap().last_error.clone()
    }

    pub fn published_lobby(&self) -> Option<u64> {
        self.shared.lock().unwrap().published_lobby
    }

    /// A Steam overlay request, released only after normal discovery validation.
    pub fn take_join_request(&self) -> Option<u64> {
        self.shared.lock().unwrap().pending_join.take()
    }

    pub fn invite_friends(&self) -> Result<(), String> {
        self.send(Command::InviteFriends)
    }

    pub fn join(&self, lobby_id: u64) -> Result<SocketAddr, String> {
        if !self
            .shared
            .lock()
            .unwrap()
            .worlds
            .iter()
            .any(|world| world.lobby_id == lobby_id)
        {
            return Err("The Steam world is no longer available.".into());
        }
        let listener =
            TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).map_err(|error| error.to_string())?;
        let address = listener.local_addr().map_err(|error| error.to_string())?;
        listener
            .set_nonblocking(true)
            .map_err(|error| error.to_string())?;
        self.send(Command::Join { lobby_id, listener })?;
        Ok(address)
    }

    pub fn claim_guest(&self, remote_addr: SocketAddr) -> Option<PeerIdentity> {
        if !remote_addr.ip().is_loopback() {
            return None;
        }
        self.shared.lock().unwrap().claims.remove(&remote_addr)
    }

    fn send(&self, command: Command) -> Result<(), String> {
        self.commands
            .try_send(command)
            .map_err(|_| "Native Steam worker is unavailable or busy.".into())
    }
}

impl Drop for SteamBridge {
    fn drop(&mut self) {
        self.control.stop.store(true, Ordering::Release);
        if let Some(worker) = self.worker.take() {
            worker.join().ok();
        }
    }
}

fn valid_steam_id(id: u64) -> bool {
    // Individual, public-universe, desktop Steam account.
    id >> 32 == 0x0110_0001 && id as u32 != 0
}

pub fn lobby_address(lobby: u64) -> String {
    format!("{lobby}.steam")
}

/// Accept the original native address as well as the copyable DNS-shaped form.
pub fn parse_lobby_address(address: &str) -> Option<u64> {
    let id = address
        .strip_prefix("lanmc-steam:")
        .or_else(|| address.strip_suffix(".steam"))?;
    if id.is_empty() || !id.bytes().all(|byte| byte.is_ascii_digit()) {
        return None;
    }
    id.parse().ok().filter(|id| *id != 0)
}

fn valid_variant(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 96
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'))
}

fn valid_nickname(value: &str) -> bool {
    use unicode_general_category::{GeneralCategory, get_general_category};

    (1..=16).contains(&value.encode_utf16().count())
        && value.trim() == value
        && !value.chars().any(|c| match get_general_category(c) {
            GeneralCategory::Control
            | GeneralCategory::LineSeparator
            | GeneralCategory::ParagraphSeparator => true,
            GeneralCategory::Format => !matches!(c, '\u{200c}' | '\u{200d}'),
            _ => false,
        })
}

fn valid_world_title(value: &str) -> bool {
    !value.trim().is_empty() && value.len() <= 1024 && !value.chars().any(char::is_control)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn overlay_join_is_consumed_once_and_unpublish_invalidates_the_lobby() {
        let (commands, pending) = mpsc::sync_channel(2);
        let bridge = SteamBridge {
            commands,
            shared: Arc::new(Mutex::new(Shared {
                published: true,
                published_lobby: Some(17),
                pending_join: Some(23),
                ..Shared::default()
            })),
            control: Arc::new(Control::default()),
            worker: None,
        };
        assert_eq!(bridge.take_join_request(), Some(23));
        assert_eq!(bridge.take_join_request(), None);
        assert_eq!(bridge.published_lobby(), Some(17));
        bridge.invite_friends().unwrap();
        assert!(matches!(pending.try_recv(), Ok(Command::InviteFriends)));
        bridge.unpublish();
        assert!(!bridge.is_published());
        assert_eq!(bridge.published_lobby(), None);
        assert!(matches!(pending.try_recv(), Err(mpsc::TryRecvError::Empty)));
    }

    #[test]
    fn unpublish_bypasses_full_queue_and_invalidates_queued_publication() {
        let (commands, pending) = mpsc::sync_channel(1);
        let bridge = SteamBridge {
            commands,
            shared: Arc::new(Mutex::new(Shared::default())),
            control: Arc::new(Control::default()),
            worker: None,
        };
        bridge.publish(25565, "Old world", "Player").unwrap();
        bridge.unpublish();
        assert_eq!(bridge.control.sharing_epoch.load(Ordering::Acquire), 1);
        let old = pending.try_recv().unwrap();
        assert!(matches!(old, Command::Publish { epoch: 0, .. }));
        bridge.publish(25566, "New world", "Player").unwrap();
        assert!(matches!(
            pending.try_recv(),
            Ok(Command::Publish { epoch: 1, .. })
        ));
    }

    #[test]
    fn invitation_addresses_accept_only_nonzero_lobbies_and_keep_legacy_addresses() {
        assert_eq!(
            parse_lobby_address(&lobby_address(109775241234567890)),
            Some(109775241234567890)
        );
        assert_eq!(
            parse_lobby_address("lanmc-steam:109775241234567890"),
            Some(109775241234567890)
        );
        for invalid in [
            "0.steam",
            "-1.steam",
            "1.steam/command",
            "https://1.steam",
            "lanmc-steam:",
            "18446744073709551616.steam",
            "host.example",
        ] {
            assert_eq!(parse_lobby_address(invalid), None, "{invalid}");
        }
    }

    #[test]
    fn publication_retry_clears_the_previous_error_only_when_queued() {
        let (commands, pending) = mpsc::sync_channel(1);
        let bridge = SteamBridge {
            commands,
            shared: Arc::new(Mutex::new(Shared::default())),
            control: Arc::new(Control::default()),
            worker: None,
        };
        bridge.send(Command::InviteFriends).unwrap();
        bridge.shared.lock().unwrap().last_error = Some("previous error".into());

        assert!(bridge.publish(25565, "Test World", "Player").is_err());
        assert_eq!(bridge.last_error().as_deref(), Some("previous error"));

        assert!(matches!(pending.try_recv(), Ok(Command::InviteFriends)));
        assert!(bridge.publish(0, "Test World", "Player").is_err());
        assert_eq!(bridge.last_error().as_deref(), Some("previous error"));

        bridge.publish(25565, "Test World", "Player").unwrap();
        assert!(matches!(
            pending.try_recv(),
            Ok(Command::Publish {
                local_port: 25565,
                ..
            })
        ));
        assert_eq!(bridge.last_error(), None);
    }

    #[test]
    fn guest_identity_is_claimed_once_and_only_for_loopback_connections() {
        let (commands, _pending) = mpsc::sync_channel(1);
        let bridge = SteamBridge {
            commands,
            shared: Arc::new(Mutex::new(Shared::default())),
            control: Arc::new(Control::default()),
            worker: None,
        };
        let identity = PeerIdentity {
            steam_id: 0x0110_0001_1234_5678,
            nickname: "Player".into(),
        };
        let local = SocketAddr::from((Ipv4Addr::LOCALHOST, 12345));
        let remote = SocketAddr::from((Ipv4Addr::new(192, 0, 2, 1), 12345));
        bridge
            .shared
            .lock()
            .unwrap()
            .claims
            .insert(local, identity.clone());
        bridge
            .shared
            .lock()
            .unwrap()
            .claims
            .insert(remote, identity.clone());
        assert_eq!(bridge.claim_guest(remote), None);
        assert_eq!(bridge.claim_guest(local), Some(identity));
        assert_eq!(bridge.claim_guest(local), None);
    }

    #[test]
    fn public_account_validation_rejects_lobby_and_empty_account_ids() {
        assert!(valid_steam_id(0x0110_0001_1234_5678));
        assert!(!valid_steam_id(0x0186_0000_1234_5678));
        assert!(!valid_steam_id(0x0110_0001_0000_0000));
    }

    #[test]
    fn public_metadata_rejects_control_characters_and_oversize_values() {
        assert!(valid_world_title("Мой мир"));
        assert!(!valid_world_title("A\0B"));
        assert!(!valid_world_title(&"х".repeat(600)));
        assert!(valid_nickname("Игрок"));
        assert!(!valid_nickname("Игрок\n"));
        assert!(valid_nickname("Player Name"));
        assert!(!valid_nickname("Play\u{202e}er"));
    }
}
