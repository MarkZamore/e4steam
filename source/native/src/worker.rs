use crate::{
    Control, PeerIdentity, Shared, WorldOffer, lobby_address, parse_lobby_address, tunnel::Tunnel,
    valid_nickname, valid_steam_id, valid_world_title,
};
use std::{
    collections::HashMap,
    fmt::Write as _,
    io,
    net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream},
    sync::{
        Arc, Mutex,
        atomic::Ordering,
        mpsc::{self, Receiver, Sender, SyncSender},
    },
    thread,
    time::{Duration, Instant},
};
use steamworks::{
    AppId, Client, FriendFlags, GameLobbyJoinRequested, GameRichPresenceJoinRequested,
    LobbyDataUpdate, LobbyId, LobbyType, SteamId,
    networking_sockets::{ListenSocket, NetConnection},
    networking_types::{
        AppNetConnectionEnd, ListenSocketEvent, NetConnectionEnd, NetworkingConnectionState,
        NetworkingIdentity, SendFlags,
    },
};

const APP_ID: AppId = AppId(480);
const GAME_PORT: i32 = 481;
const MAX_PLAYERS: u32 = 32;
const POLL: Duration = Duration::from_millis(4);
const DISCOVER: Duration = Duration::from_secs(1);
const HANDSHAKE: Duration = Duration::from_secs(30);
const CONNECT_LOCAL: Duration = Duration::from_millis(250);
const LOBBY_PROPAGATION: Duration = Duration::from_millis(500);
const FORMAT_KEY: &str = "lanmc_native";
const FORMAT_VALUE: &str = "1";
const VARIANT_KEY: &str = "lanmc_native_variant";
const GENERATION_KEY: &str = "lanmc_native_generation";
const OWNER_KEY: &str = "lanmc_native_owner";
const DISCOVERY_TTL: Duration = Duration::from_secs(5);
const WORLD_KEY: &str = "lanmc_world";
const NICK_KEY: &str = "lanmc_player";
const PRESENCE_KEY: &str = "lanmc_native_lobby";
const HELLO: &[u8] = b"LANMC-NATIVE\x01";
const ACK: &[u8] = b"LANMC-READY\x01";
type Generation = [u8; 16];

pub(crate) enum Command {
    Publish {
        epoch: u64,
        local_port: u16,
        title: String,
        nickname: String,
    },
    InviteFriends,
    Join {
        lobby_id: u64,
        listener: TcpListener,
    },
}

enum Completion {
    Published(u64, Result<LobbyId, String>),
    Joined(u64, Result<LobbyId, ()>),
    LobbyData(LobbyDataUpdate),
    Invited(LobbyId, SteamId),
}

struct Worker {
    steam: Client,
    local_id: SteamId,
    variant: String,
    nickname: String,
    shared: Arc<Mutex<Shared>>,
    completion_tx: Sender<Completion>,
    completion_rx: Receiver<Completion>,
    next_action: u64,
    role: Role,
    discovered: HashMap<LobbyId, SteamId>,
    fresh_lobbies: HashMap<LobbyId, Instant>,
    pending_invite: Option<(LobbyId, SteamId, Instant)>,
    control: Arc<Control>,
    observed_epoch: u64,
}

enum Role {
    Idle,
    Publishing {
        action: u64,
        started: Instant,
        listener: ListenSocket,
        local_port: u16,
        title: String,
        generation: Generation,
    },
    Hosting(Host),
    Joining {
        action: u64,
        started: Instant,
        lobby: LobbyId,
        owner: SteamId,
        listener: TcpListener,
    },
    Guest(Guest),
}

struct Host {
    lobby: LobbyId,
    listener: ListenSocket,
    local_port: u16,
    generation: Generation,
    peers: HashMap<SteamId, HostPeer>,
}

struct HostPeer {
    deadline: Instant,
    connection: NetConnection,
    tunnel: Option<Tunnel>,
    claim_addr: Option<SocketAddr>,
}

struct Guest {
    lobby: LobbyId,
    owner: SteamId,
    generation: Generation,
    listener: Option<TcpListener>,
    connection: Option<NetConnection>,
    next_dial: Instant,
    tunnel: Option<Tunnel>,
    deadline: Instant,
    hello_sent: bool,
    ready: bool,
}

pub(crate) fn run(
    expected_id: u64,
    variant: String,
    nickname: String,
    commands: Receiver<Command>,
    started: SyncSender<Result<(), String>>,
    shared: Arc<Mutex<Shared>>,
    control: Arc<Control>,
) {
    let initialized = Client::init_app(APP_ID)
        .map_err(|error| format!("Steam game transport initialization failed ({error})."))
        .and_then(|steam| {
            if steam.user().steam_id().raw() != expected_id {
                return Err("The active Steam account changed before game startup.".into());
            }
            steam.networking_utils().init_relay_network_access();
            Ok(steam)
        });
    let steam = match initialized {
        Ok(steam) => steam,
        Err(error) => {
            started.send(Err(error)).ok();
            return;
        }
    };
    let (completion_tx, completion_rx) = mpsc::channel();
    let lobby_data = completion_tx.clone();
    let _lobby_updates = steam.register_callback(move |update: LobbyDataUpdate| {
        lobby_data.send(Completion::LobbyData(update)).ok();
    });
    let invitations = completion_tx.clone();
    let _lobby_invites = steam.register_callback(move |invite: GameLobbyJoinRequested| {
        invitations
            .send(Completion::Invited(
                invite.lobby_steam_id,
                invite.friend_steam_id,
            ))
            .ok();
    });
    let invitations = completion_tx.clone();
    let _presence_invites =
        steam.register_callback(move |invite: GameRichPresenceJoinRequested| {
            if let Some(lobby) = parse_lobby_address(&invite.connect) {
                invitations
                    .send(Completion::Invited(
                        LobbyId::from_raw(lobby),
                        invite.friend_steam_id,
                    ))
                    .ok();
            }
        });
    let mut worker = Worker {
        steam,
        local_id: SteamId::from_raw(expected_id),
        variant,
        nickname,
        shared,
        completion_tx,
        completion_rx,
        next_action: 0,
        role: Role::Idle,
        discovered: HashMap::new(),
        fresh_lobbies: HashMap::new(),
        pending_invite: None,
        control,
        observed_epoch: 0,
    };
    if started.send(Ok(())).is_err() {
        return;
    }
    let mut next_discovery = Instant::now();
    while !worker.control.stop.load(Ordering::Acquire) {
        worker.sync_sharing();
        worker.steam.run_callbacks();
        while let Ok(command) = commands.try_recv() {
            if let Err(error) = worker.command(command) {
                worker.error(&error);
            }
        }
        while let Ok(completion) = worker.completion_rx.try_recv() {
            worker.complete(completion);
        }
        if Instant::now() >= next_discovery {
            worker.discover();
            next_discovery = Instant::now() + DISCOVER;
        }
        worker.poll();
        worker.poll_invite();
        thread::sleep(POLL);
    }
    worker.close_role();
}

impl Worker {
    fn command(&mut self, command: Command) -> Result<(), String> {
        match command {
            Command::Publish {
                epoch,
                local_port,
                title,
                nickname,
            } => {
                self.sync_sharing();
                if epoch != self.observed_epoch {
                    return Ok(());
                }
                if nickname != self.nickname {
                    return Err(
                        "Steam publication nickname does not match the launch profile.".into(),
                    );
                }
                if matches!(&self.role, Role::Hosting(host) if host.local_port == local_port) {
                    return Ok(());
                }
                if !matches!(self.role, Role::Idle) {
                    return Err("Another Steam session is active.".into());
                }
                let mut generation = [0; 16];
                getrandom::fill(&mut generation).map_err(|_| {
                    "Could not create a fresh Steam sharing generation.".to_string()
                })?;
                let listener = self
                    .steam
                    .networking_sockets()
                    .create_listen_socket_p2p(GAME_PORT, [])
                    .map_err(|_| "Could not open a Steam game listener.".to_string())?;
                let action = self.action();
                let completions = self.completion_tx.clone();
                self.steam.matchmaking().create_lobby(
                    LobbyType::FriendsOnly,
                    MAX_PLAYERS,
                    move |lobby| {
                        completions
                            .send(Completion::Published(
                                action,
                                lobby.map_err(|error| error.to_string()),
                            ))
                            .ok();
                    },
                );
                self.role = Role::Publishing {
                    action,
                    started: Instant::now(),
                    listener,
                    local_port,
                    title,
                    generation,
                };
                self.clear_error();
            }
            Command::InviteFriends => {
                let Role::Hosting(host) = &self.role else {
                    return Err("The Steam world is not ready for invitations.".into());
                };
                if !self.steam.utils().is_overlay_enabled() {
                    return Err("The Steam overlay is unavailable.".into());
                }
                self.steam.friends().activate_invite_dialog(host.lobby);
            }
            Command::Join { lobby_id, listener } => {
                if matches!(self.role, Role::Guest(_)) {
                    self.close_role();
                }
                if !matches!(self.role, Role::Idle) {
                    return Err("Another Steam session is active.".into());
                }
                let lobby = LobbyId::from_raw(lobby_id);
                let owner = self
                    .discovered
                    .get(&lobby)
                    .copied()
                    .filter(|owner| self.world_offer(lobby, *owner).is_some())
                    .ok_or_else(|| "The Steam world is no longer available.".to_string())?;
                let action = self.action();
                let completions = self.completion_tx.clone();
                self.steam.matchmaking().join_lobby(lobby, move |result| {
                    completions.send(Completion::Joined(action, result)).ok();
                });
                self.role = Role::Joining {
                    action,
                    started: Instant::now(),
                    lobby,
                    owner,
                    listener,
                };
                self.clear_error();
            }
        }
        Ok(())
    }

    fn complete(&mut self, completion: Completion) {
        self.sync_sharing();
        match completion {
            Completion::Invited(lobby, friend) => {
                if valid_steam_id(friend.raw())
                    && friend != self.local_id
                    && lobby.raw() != 0
                    && self
                        .steam
                        .friends()
                        .get_friend(friend)
                        .has_friend(FriendFlags::IMMEDIATE)
                {
                    request_lobby_data(lobby);
                    self.pending_invite = Some((lobby, friend, Instant::now()));
                }
            }
            Completion::LobbyData(update) => {
                if update.member.raw() == update.lobby.raw() {
                    if update.success {
                        self.fresh_lobbies.insert(update.lobby, Instant::now());
                    } else {
                        self.fresh_lobbies.remove(&update.lobby);
                    }
                }
            }
            Completion::Published(action, result) => {
                if !matches!(self.role, Role::Publishing { action: pending, .. } if pending == action)
                {
                    if let Ok(lobby) = result {
                        self.steam.matchmaking().leave_lobby(lobby);
                    }
                    return;
                }
                let Role::Publishing {
                    listener,
                    local_port,
                    title,
                    generation,
                    ..
                } = std::mem::replace(&mut self.role, Role::Idle)
                else {
                    unreachable!()
                };
                let lobby = match result {
                    Ok(lobby) => lobby,
                    Err(error) => {
                        self.error(&format!(
                            "Steam could not create a friends lobby ({error})."
                        ));
                        return;
                    }
                };
                let matchmaking = self.steam.matchmaking();
                let generation_text = encode_generation(&generation);
                let published = matchmaking.lobby_owner(lobby) == self.local_id
                    && matchmaking.set_lobby_data(lobby, VARIANT_KEY, &self.variant)
                    && matchmaking.set_lobby_data(
                        lobby,
                        OWNER_KEY,
                        &self.local_id.raw().to_string(),
                    )
                    && matchmaking.set_lobby_data(lobby, WORLD_KEY, &title)
                    && matchmaking.set_lobby_data(lobby, NICK_KEY, &self.nickname)
                    && matchmaking.set_lobby_data(lobby, GENERATION_KEY, &generation_text)
                    && matchmaking.set_lobby_data(lobby, FORMAT_KEY, FORMAT_VALUE);
                if !published {
                    matchmaking.leave_lobby(lobby);
                    self.error("Could not publish the Steam world details.");
                    return;
                }
                let lobby_id = lobby.raw().to_string();
                self.steam
                    .friends()
                    .set_rich_presence(PRESENCE_KEY, Some(&lobby_id));
                self.steam
                    .friends()
                    .set_rich_presence("connect", Some(&lobby_address(lobby.raw())));
                let mut shared = self.shared.lock().unwrap();
                if self.control.sharing_epoch.load(Ordering::Acquire) != self.observed_epoch {
                    matchmaking.delete_lobby_data(lobby, FORMAT_KEY);
                    matchmaking.set_lobby_joinable(lobby, false);
                    matchmaking.leave_lobby(lobby);
                    self.steam.friends().set_rich_presence(PRESENCE_KEY, None);
                    self.steam.friends().set_rich_presence("connect", None);
                    return;
                }
                self.role = Role::Hosting(Host {
                    lobby,
                    listener,
                    local_port,
                    generation,
                    peers: HashMap::new(),
                });
                shared.published = true;
                shared.published_lobby = Some(lobby.raw());
                eprintln!("[LANMinecraft Steam] World published to Steam friends.");
            }
            Completion::Joined(action, result) => {
                if !matches!(self.role, Role::Joining { action: pending, .. } if pending == action)
                {
                    if let Ok(lobby) = result {
                        let active = matches!(&self.role, Role::Joining { lobby: pending, .. } if *pending == lobby)
                            || matches!(&self.role, Role::Guest(guest) if guest.lobby == lobby);
                        if !active {
                            self.steam.matchmaking().leave_lobby(lobby);
                        }
                    }
                    return;
                }
                let Role::Joining {
                    lobby,
                    owner,
                    listener,
                    ..
                } = std::mem::replace(&mut self.role, Role::Idle)
                else {
                    unreachable!()
                };
                if result != Ok(lobby) {
                    self.error("Steam refused entry to the friends lobby.");
                    return;
                }
                match self.open_guest(lobby, owner, listener) {
                    Ok(guest) => self.role = Role::Guest(guest),
                    Err(error) => {
                        self.steam.matchmaking().leave_lobby(lobby);
                        self.error(&error);
                    }
                }
            }
        }
    }

    fn open_guest(
        &self,
        lobby: LobbyId,
        owner: SteamId,
        listener: TcpListener,
    ) -> Result<Guest, String> {
        let matchmaking = self.steam.matchmaking();
        if matchmaking.lobby_owner(lobby) != owner
            || !matchmaking.lobby_members(lobby).contains(&self.local_id)
            || self.world_offer(lobby, owner).is_none()
        {
            return Err("The Steam lobby changed before the connection opened.".into());
        }
        let generation = matchmaking
            .lobby_data(lobby, GENERATION_KEY)
            .as_deref()
            .and_then(decode_generation)
            .ok_or_else(|| "The Steam lobby has no verified sharing generation.".to_string())?;
        Ok(Guest {
            lobby,
            owner,
            generation,
            listener: Some(listener),
            connection: None,
            next_dial: Instant::now() + LOBBY_PROPAGATION,
            tunnel: None,
            deadline: Instant::now() + HANDSHAKE,
            hello_sent: false,
            ready: false,
        })
    }

    fn discover(&mut self) {
        let friends = self.steam.friends();
        let mut worlds = Vec::new();
        self.discovered.clear();
        self.fresh_lobbies
            .retain(|_, verified| verified.elapsed() <= DISCOVERY_TTL);
        for friend in friends.get_friends(FriendFlags::IMMEDIATE) {
            let owner = friend.id();
            if !valid_steam_id(owner.raw()) {
                continue;
            }
            let from_presence = friend
                .rich_presence(PRESENCE_KEY)
                .and_then(|value| value.parse::<u64>().ok());
            let lobby = from_presence.filter(|id| *id != 0).or_else(|| {
                friend
                    .game_played()
                    .map(|game| game.lobby.raw())
                    .filter(|id| *id != 0)
            });
            let Some(lobby) = lobby.map(LobbyId::from_raw) else {
                continue;
            };
            request_lobby_data(lobby);
            if self.fresh_lobbies.contains_key(&lobby)
                && let Some(offer) = self.world_offer(lobby, owner)
            {
                self.discovered.insert(lobby, owner);
                worlds.push(offer);
            }
        }
        worlds.sort_by(|left, right| {
            left.title
                .cmp(&right.title)
                .then(left.lobby_id.cmp(&right.lobby_id))
        });
        self.shared.lock().unwrap().worlds = worlds;
    }

    fn poll_invite(&mut self) {
        let Some((lobby, friend, since)) = self.pending_invite else {
            return;
        };
        if since.elapsed() > HANDSHAKE {
            self.pending_invite = None;
            self.error("The invited Steam world is no longer available.");
        } else if self
            .fresh_lobbies
            .get(&lobby)
            .is_some_and(|time| time.elapsed() <= DISCOVERY_TTL)
            && self.discovered.get(&lobby) == Some(&friend)
            && self.world_offer(lobby, friend).is_some()
        {
            self.pending_invite = None;
            self.shared.lock().unwrap().pending_join = Some(lobby.raw());
        }
    }

    fn world_offer(&self, lobby: LobbyId, owner: SteamId) -> Option<WorldOffer> {
        let matchmaking = self.steam.matchmaking();
        // Steam exposes GetLobbyOwner only once joined. Here the matching
        // friend advertises the lobby and its metadata states the same owner.
        // open_guest independently rechecks ownership after joining.
        let advertised_owner = matchmaking
            .lobby_data(lobby, OWNER_KEY)
            .and_then(|value| value.parse::<u64>().ok());
        if owner == self.local_id
            || advertised_owner != Some(owner.raw())
            || matchmaking.lobby_data(lobby, FORMAT_KEY).as_deref() != Some(FORMAT_VALUE)
            || matchmaking.lobby_data(lobby, VARIANT_KEY).as_deref() != Some(self.variant.as_str())
            || !self
                .steam
                .friends()
                .get_friend(owner)
                .has_friend(FriendFlags::IMMEDIATE)
        {
            return None;
        }
        let title = matchmaking
            .lobby_data(lobby, WORLD_KEY)
            .filter(|name| valid_world_title(name))?;
        let host = matchmaking
            .lobby_data(lobby, NICK_KEY)
            .filter(|name| valid_nickname(name))?;
        Some(WorldOffer {
            lobby_id: lobby.raw(),
            title: title.to_owned(),
            host: host.to_owned(),
        })
    }

    fn poll(&mut self) {
        let result = match &mut self.role {
            Role::Idle => Ok(true),
            Role::Publishing { started, .. } | Role::Joining { started, .. } => {
                if started.elapsed() > HANDSHAKE {
                    Err("Steam did not complete the lobby operation in time.".into())
                } else {
                    Ok(true)
                }
            }
            Role::Hosting(host) => host.poll(&self.steam, self.local_id, &self.shared),
            Role::Guest(guest) => guest.poll(&self.steam, &self.nickname),
        };
        match result {
            Ok(true) => {}
            Ok(false) => self.close_role(),
            Err(error) => {
                self.close_role();
                self.error(&error);
            }
        }
    }

    fn sync_sharing(&mut self) {
        let epoch = self.control.sharing_epoch.load(Ordering::Acquire);
        if epoch != self.observed_epoch {
            self.observed_epoch = epoch;
            if matches!(self.role, Role::Hosting(_) | Role::Publishing { .. }) {
                self.close_role();
            }
        }
    }

    fn close_role(&mut self) {
        let role = std::mem::replace(&mut self.role, Role::Idle);
        let matchmaking = self.steam.matchmaking();
        match role {
            Role::Hosting(host) => {
                matchmaking.delete_lobby_data(host.lobby, FORMAT_KEY);
                matchmaking.set_lobby_joinable(host.lobby, false);
                matchmaking.leave_lobby(host.lobby);
                self.steam.friends().set_rich_presence(PRESENCE_KEY, None);
                self.steam.friends().set_rich_presence("connect", None);
            }
            Role::Guest(guest) => matchmaking.leave_lobby(guest.lobby),
            _ => {}
        }
        let mut shared = self.shared.lock().unwrap();
        shared.claims.clear();
        shared.published = false;
        shared.published_lobby = None;
        shared.pending_join = None;
    }

    fn action(&mut self) -> u64 {
        self.next_action += 1;
        self.next_action
    }

    fn error(&self, error: &str) {
        eprintln!("[LANMinecraft Steam] {error}");
        self.shared.lock().unwrap().last_error = Some(error.to_owned());
    }

    fn clear_error(&self) {
        self.shared.lock().unwrap().last_error = None;
    }
}

impl Host {
    fn poll(
        &mut self,
        steam: &Client,
        local_id: SteamId,
        shared: &Mutex<Shared>,
    ) -> Result<bool, String> {
        let matchmaking = steam.matchmaking();
        if matchmaking.lobby_owner(self.lobby) != local_id {
            return Err("Steam removed the host from the friends lobby.".into());
        }
        let members = matchmaking.lobby_members(self.lobby);
        let friends = steam.friends();
        let admitted = |peer: SteamId| {
            peer != local_id
                && valid_steam_id(peer.raw())
                && members.contains(&peer)
                && friends.get_friend(peer).has_friend(FriendFlags::IMMEDIATE)
        };
        while let Some(event) = self.listener.try_receive_event() {
            match event {
                ListenSocketEvent::Connecting(request) => {
                    if request
                        .remote()
                        .steam_id()
                        .is_some_and(|peer| admitted(peer) && !self.peers.contains_key(&peer))
                    {
                        request.accept().ok();
                    } else {
                        request.reject(
                            NetConnectionEnd::App(AppNetConnectionEnd::generic_normal()),
                            Some("Not a Steam lobby member"),
                        );
                    }
                }
                ListenSocketEvent::Connected(event) => {
                    if let Some(peer) = event.remote().steam_id().filter(|peer| admitted(*peer)) {
                        self.peers.entry(peer).or_insert_with(|| HostPeer {
                            deadline: Instant::now() + HANDSHAKE,
                            connection: event.take_connection(),
                            tunnel: None,
                            claim_addr: None,
                        });
                    }
                }
                // A disconnected duplicate must not remove the accepted
                // connection for this Steam user. Poll each owned handle.
                ListenSocketEvent::Disconnected(_) => {}
            }
        }
        self.peers.retain(|peer, connection| {
            let alive = admitted(*peer)
                && connection
                    .poll(*peer, self.local_port, &self.generation, shared)
                    .unwrap_or_else(|error| {
                        network_failure(&error);
                        false
                    });
            if !alive {
                connection.clear_claim(shared);
            }
            alive
        });
        Ok(true)
    }
}

impl HostPeer {
    fn poll(
        &mut self,
        peer: SteamId,
        port: u16,
        generation: &Generation,
        shared: &Mutex<Shared>,
    ) -> io::Result<bool> {
        let state = self
            .connection
            .info()
            .ok()
            .and_then(|info| info.state().ok());
        if state != Some(NetworkingConnectionState::Connected) {
            return Ok(false);
        }
        if let Some(tunnel) = &mut self.tunnel {
            return tunnel.pump(&mut self.connection);
        }
        if Instant::now() > self.deadline {
            return Ok(false);
        }
        let Some(message) = self
            .connection
            .receive_messages(1)
            .map_err(io::Error::other)?
            .pop()
        else {
            return Ok(true);
        };
        let Some(nickname) = read_hello(message.data(), generation) else {
            return Ok(false);
        };
        let local = TcpStream::connect_timeout(
            &SocketAddr::from((Ipv4Addr::LOCALHOST, port)),
            CONNECT_LOCAL,
        )?;
        let address = local.local_addr()?;
        let tunnel = Tunnel::new(local)?;
        ready_guest(
            shared,
            address,
            PeerIdentity {
                steam_id: peer.raw(),
                nickname: nickname.to_owned(),
            },
            || {
                self.connection
                    .send_message(ACK, SendFlags::RELIABLE)
                    .map_err(io::Error::other)
            },
        )?;
        self.claim_addr = Some(address);
        self.tunnel = Some(tunnel);
        Ok(true)
    }

    fn clear_claim(&mut self, shared: &Mutex<Shared>) {
        if let Some(address) = self.claim_addr.take() {
            shared.lock().unwrap().claims.remove(&address);
        }
    }
}

impl Guest {
    fn poll(&mut self, steam: &Client, nickname: &str) -> Result<bool, String> {
        let matchmaking = steam.matchmaking();
        if matchmaking.lobby_owner(self.lobby) != self.owner {
            return Err("The Steam host has closed or left the world.".into());
        }
        if !self.ready && Instant::now() > self.deadline {
            return Err("The Steam game bridge did not open in time.".into());
        }
        if self.connection.is_none() && Instant::now() >= self.next_dial {
            // The lobby enter result may reach the guest before Steam sends
            // the updated membership to the host. Retry only before READY.
            self.connection = steam
                .networking_sockets()
                .connect_p2p(NetworkingIdentity::new_steam_id(self.owner), GAME_PORT, [])
                .ok();
            self.next_dial = Instant::now() + LOBBY_PROPAGATION;
        }
        let Some(connection) = &mut self.connection else {
            return Ok(true);
        };
        let info = connection.info().ok();
        let state = info.as_ref().and_then(|info| info.state().ok());
        if !matches!(
            state,
            Some(
                NetworkingConnectionState::Connecting
                    | NetworkingConnectionState::FindingRoute
                    | NetworkingConnectionState::Connected
            )
        ) {
            if self.ready {
                return Err("The Steam game connection ended.".into());
            }
            self.connection = None;
            self.hello_sent = false;
            return Ok(true);
        }
        if info
            .and_then(|info| info.identity_remote())
            .and_then(|identity| identity.steam_id())
            != Some(self.owner)
        {
            return Err(
                "The Steam connection's authenticated host did not match the lobby owner.".into(),
            );
        }
        if self.ready {
            return self
                .tunnel
                .as_mut()
                .expect("ready Steam tunnel")
                .pump(connection)
                .map_err(|error| format!("Steam game tunnel: {error}"));
        }
        if let Some(listener) = &self.listener {
            match listener.accept() {
                Ok((stream, _)) => {
                    self.tunnel = Some(Tunnel::new(stream).map_err(|error| error.to_string())?);
                    self.listener = None;
                }
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => {}
                Err(error) => {
                    return Err(format!(
                        "Could not accept the local game connection ({error})."
                    ));
                }
            }
        }
        if state != Some(NetworkingConnectionState::Connected) || self.tunnel.is_none() {
            return Ok(true);
        }
        if !self.hello_sent {
            let hello = make_hello(&self.generation, nickname);
            connection
                .send_message(&hello, SendFlags::RELIABLE)
                .map_err(|error| {
                    format!("Could not open the authenticated Steam bridge ({error}).")
                })?;
            self.hello_sent = true;
        }
        if let Some(message) = connection
            .receive_messages(1)
            .map_err(|_| "Steam bridge connection closed.")?
            .pop()
        {
            if message.data() != ACK {
                return Err("The Steam host refused the current sharing generation.".into());
            }
            self.ready = true;
        }
        Ok(true)
    }
}

/// READY releases the guest's game bytes. Install its one-use identity first,
/// so a fast peer cannot reach the local login before its claim is visible.
fn ready_guest<T>(
    shared: &Mutex<Shared>,
    address: SocketAddr,
    identity: PeerIdentity,
    ready: impl FnOnce() -> io::Result<T>,
) -> io::Result<()> {
    shared.lock().unwrap().claims.insert(address, identity);
    if let Err(error) = ready() {
        shared.lock().unwrap().claims.remove(&address);
        return Err(error);
    }
    Ok(())
}

fn network_failure(error: &io::Error) {
    eprintln!(
        "[LANMinecraft Steam] Network error: {error}\n{}",
        std::backtrace::Backtrace::force_capture()
    );
}

fn request_lobby_data(lobby: LobbyId) {
    // steamworks-rs does not expose RequestLobbyData. This worker owns a live
    // client and calls it only for nonzero lobbies observed on Steam friends.
    unsafe {
        let matchmaking = steamworks_sys::SteamAPI_SteamMatchmaking_v009();
        if !matchmaking.is_null() {
            steamworks_sys::SteamAPI_ISteamMatchmaking_RequestLobbyData(matchmaking, lobby.raw());
        }
    }
}

fn encode_generation(generation: &Generation) -> String {
    let mut encoded = String::with_capacity(generation.len() * 2);
    for value in generation {
        write!(&mut encoded, "{value:02x}").expect("writing to String");
    }
    encoded
}

fn decode_generation(value: &str) -> Option<Generation> {
    if value.len() != 32 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return None;
    }
    let mut generation = [0; 16];
    for (index, byte) in generation.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16).ok()?;
    }
    Some(generation)
}

fn make_hello(generation: &Generation, nickname: &str) -> Vec<u8> {
    let mut hello = Vec::with_capacity(HELLO.len() + generation.len() + nickname.len());
    hello.extend_from_slice(HELLO);
    hello.extend_from_slice(generation);
    hello.extend_from_slice(nickname.as_bytes());
    hello
}

fn read_hello<'a>(hello: &'a [u8], generation: &Generation) -> Option<&'a str> {
    let name = hello
        .strip_prefix(HELLO)?
        .strip_prefix(generation.as_slice())?;
    std::str::from_utf8(name)
        .ok()
        .filter(|name| valid_nickname(name))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ready_observes_the_identity_claim_and_failed_ack_rolls_it_back() {
        let shared = Mutex::new(Shared::default());
        let address = SocketAddr::from((Ipv4Addr::LOCALHOST, 12345));
        let identity = PeerIdentity {
            steam_id: 0x0110_0001_1234_5678,
            nickname: "Player".into(),
        };
        ready_guest(&shared, address, identity.clone(), || {
            assert_eq!(shared.lock().unwrap().claims.get(&address), Some(&identity));
            Ok(())
        })
        .unwrap();
        assert_eq!(
            shared.lock().unwrap().claims.remove(&address),
            Some(identity.clone())
        );
        let error = ready_guest(&shared, address, identity.clone(), || {
            assert_eq!(shared.lock().unwrap().claims.get(&address), Some(&identity));
            Err::<(), _>(io::Error::from(io::ErrorKind::BrokenPipe))
        })
        .unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::BrokenPipe);
        assert!(shared.lock().unwrap().claims.is_empty());
    }

    #[test]
    fn only_the_current_sharing_generation_and_valid_nickname_are_accepted() {
        let generation = [0x23; 16];
        let hello = make_hello(&generation, "Игрок");
        assert_eq!(read_hello(&hello, &generation), Some("Игрок"));
        assert!(read_hello(&hello, &[0x24; 16]).is_none());
        assert!(read_hello(&hello[..HELLO.len() + 15], &generation).is_none());
        assert!(read_hello(&make_hello(&generation, "Name\0"), &generation).is_none());
    }

    #[test]
    fn generation_is_fixed_width_ascii_hex() {
        let generation = [0x08; 16];
        assert_eq!(
            decode_generation(&encode_generation(&generation)),
            Some(generation)
        );
        assert_eq!(decode_generation("not a generation"), None);
        assert_eq!(decode_generation(&"é".repeat(16)), None);
    }
}
