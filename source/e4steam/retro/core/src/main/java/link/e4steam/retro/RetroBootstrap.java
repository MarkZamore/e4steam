package link.e4steam.retro;

import link.e4steam.E4steamClient;
import link.e4steam.MinecraftVersion;
import link.e4steam.steam.SteamAccessMode;
import link.e4steam.steam.SteamLanMetadata;
import link.e4steam.steam.SteamOverlayRelauncher;
import link.e4steam.steam.SteamRuntime;
import link.e4steam.steam.SteamSession;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/** Shared idempotent lifecycle called by every branch-scoped retro loader adapter. */
public final class RetroBootstrap {
    private static final Object LOCK = new Object();
    private static final List<String> CLIENT_COMMANDS = Collections.unmodifiableList(Arrays.asList(
            "start", "stop", "restart", "invite", "doctor", "addon", "help"));
    private static int relayPort;
    private static int hostedPort;
    private static Publication publication;
    private static volatile SteamAccessMode selectedAccessMode = SteamAccessMode.FRIENDS_ONLY;
    private static volatile RetroPlatform installedPlatform;

    private RetroBootstrap() {
    }

    private static final class Publication {
        private String worldName;
        private String playerName;
        private Runnable closeRelay;

        private boolean confirmed() { return worldName != null; }
    }

    public static boolean launcherManagedLan() {
        return Boolean.getBoolean("link.e4steam.launcherManagedLan");
    }

    public static String launcherNickname(String fallback) {
        return System.getProperty("link.e4steam.launcherPlayerName", fallback);
    }

    /** Reserves one native publication attempt. No Steam task starts at HEAD. */
    public static boolean beginPublication() {
        if (!launcherManagedLan()) return true;
        synchronized (LOCK) {
            if (publication != null) return false;
            publication = new Publication();
            return true;
        }
    }

    public static Object relayTicket() {
        synchronized (LOCK) { return publication; }
    }

    public static void publishRelay(String worldName, String playerName) {
        if (!launcherManagedLan()) return;
        synchronized (LOCK) {
            if (publication == null || publication.confirmed()) return;
            publication.worldName = worldName == null ? "" : worldName;
            publication.playerName = playerName;
            replaceHostedSessionLocked(relayPort);
        }
    }

    public static void cancelPublication() {
        if (!launcherManagedLan()) return;
        synchronized (LOCK) {
            if (publication == null || publication.confirmed()) return;
            if (publication.closeRelay != null) publication.closeRelay.run();
            publication = null;
            relayPort = 0;
        }
    }

    public static void openReports() {
        SteamRuntime.get().openRecentPlayersOverlay().whenComplete((unused, failure) -> {
            if (failure != null) {
                showTranslated("text.e4steam_minecraft.overlayUnavailable",
                        "The Steam overlay is unavailable");
            }
        });
    }

    public static void install(String minecraftVersion, RetroPlatform platform) {
        // Forge 1.7-1.12 invokes this earlier from a core plugin. This call is
        // the idempotent fallback for Fabric and ModLauncher-era retro Forge.
        SteamOverlayRelauncher.relaunchIfNeeded();
        MinecraftVersion.install(minecraftVersion);
        installedPlatform = platform;
        E4steamClient.install(platform);
        SteamRuntime.preloadCompatibilityClasses();
        SteamRuntime.get().startAtGameLaunchAsync();
    }

    /** Publishes a loopback-only relay created by a version-specific Minecraft hook. */
    public static void relayBound(int port) {
        relayBound(port, null, null);
    }

    public static boolean relayBound(int port, Object ticket, Runnable close) {
        int normalized = normalizePort(port);
        synchronized (LOCK) {
            if (launcherManagedLan()) {
                if (normalized == 0 || publication == null || publication != ticket || relayPort != 0) return false;
                relayPort = normalized;
                publication.closeRelay = close;
                if (publication.confirmed()) replaceHostedSessionLocked(normalized);
                return true;
            }
            relayPort = normalized;
            replaceHostedSessionLocked(normalized);
            return normalized != 0;
        }
    }

    /** Stops Steam exposure when the corresponding Minecraft listener closes. */
    public static void relayClosed() {
        synchronized (LOCK) {
            publication = null;
            relayPort = 0;
            replaceHostedSessionLocked(0);
        }
    }

    /**
     * Fallback for loaders where the listener mixin is not applied reliably.
     * A real listener hook always wins and may replace this port later.
     */
    public static boolean relayBoundFallback(int port) {
        int normalized = normalizePort(port);
        if (normalized == 0) return false;
        synchronized (LOCK) {
            if (relayPort != 0) return relayPort == normalized;
            relayPort = normalized;
            replaceHostedSessionLocked(normalized);
            return true;
        }
    }

    /** Stops sharing only when the fallback still owns the observed LAN port. */
    public static void relayClosedFallback(int port) {
        int normalized = normalizePort(port);
        if (normalized == 0) return;
        synchronized (LOCK) {
            if (relayPort != normalized) return;
            relayPort = 0;
            replaceHostedSessionLocked(0);
        }
    }

    /** Compatibility entry point retained for older loader hooks. */
    public static void updateHostedPort(int port) {
        if (normalizePort(port) == 0) relayClosed();
        else relayBound(port);
    }

    private static int normalizePort(int port) {
        return port > 0 && port <= 65535 ? port : 0;
    }

    private static void replaceHostedSessionLocked(int port) {
        SteamSession current = E4steamClient.session;
        if (port == hostedPort && (port == 0 || isActive(current))) {
            return;
        }
        if (current != null) {
            E4steamClient.session = null;
            current.stop();
        }
        hostedPort = 0;
        if (port > 0 && selectedAccessMode != SteamAccessMode.LOCAL_ONLY) {
            SteamSession replacement = newHostedSession(port);
            E4steamClient.session = replacement;
            hostedPort = port;
            replacement.startAsync();
        }
    }

    private static boolean isActive(SteamSession session) {
        if (session == null) return false;
        SteamSession.State state = session.state();
        return state != SteamSession.State.STOPPED
                && state != SteamSession.State.STOPPING
                && state != SteamSession.State.UNHEALTHY;
    }

    private static boolean startSharing(boolean forceRestart) {
        synchronized (LOCK) {
            SteamSession current = E4steamClient.session;
            if (relayPort == 0 || selectedAccessMode == SteamAccessMode.LOCAL_ONLY
                    || launcherManagedLan() && (publication == null || !publication.confirmed())) {
                return false;
            }
            if (!forceRestart && isActive(current)) {
                return false;
            }
            if (current != null) {
                E4steamClient.session = null;
                current.stop();
            }
            hostedPort = 0;
            SteamSession replacement = newHostedSession(relayPort);
            E4steamClient.session = replacement;
            hostedPort = relayPort;
            replacement.startAsync();
            return true;
        }
    }

    private static SteamSession newHostedSession(int port) {
        SteamSession session = new SteamSession(port, selectedAccessMode);
        if (publication != null && publication.confirmed()) {
            SteamLanMetadata.describe(session, publication.worldName, publication.playerName);
        }
        return session;
    }

    private static boolean stopSharing() {
        synchronized (LOCK) {
            SteamSession current = E4steamClient.session;
            if (!isActive(current)) return false;
            E4steamClient.session = null;
            hostedPort = 0;
            current.stop();
            return true;
        }
    }

    public static SteamAccessMode selectedAccessMode() {
        return selectedAccessMode;
    }

    public static SteamAccessMode cycleAccessMode() {
        SteamAccessMode current = selectedAccessMode;
        SteamAccessMode next;
        if (current == SteamAccessMode.LOCAL_ONLY) next = SteamAccessMode.FRIENDS_ONLY;
        else if (current == SteamAccessMode.FRIENDS_ONLY) next = SteamAccessMode.INVITE_ONLY;
        else next = SteamAccessMode.LOCAL_ONLY;
        selectedAccessMode = next;
        return next;
    }

    /** Command names exposed to version-specific completion implementations. */
    public static List<String> clientCommandNames() {
        return CLIENT_COMMANDS;
    }

    public static boolean handleClientCommand(String command) {
        if (command == null) {
            return false;
        }
        String normalized = command.trim();
        if (normalized.startsWith("/")) normalized = normalized.substring(1);
        String[] arguments = normalized.split("\\s+");
        if (arguments.length == 0 || !"e4steam".equalsIgnoreCase(arguments[0])) {
            return false;
        }
        if (arguments.length == 1) {
            showHelp();
            return true;
        }
        if (arguments.length != 2) {
            showHelp();
            return true;
        }

        String action = arguments[1].toLowerCase(Locale.ROOT);
        if ("copy".equals(action)) {
            final SteamSession current = E4steamClient.session;
            if (current != null && current.address() != null) {
                final String address = current.address().inviteString();
                final RetroPlatform platform = installedPlatform;
                if (platform != null) {
                    platform.execute(new Runnable() {
                        @Override public void run() {
                            if (platform.copyToClipboard(address)) {
                                platform.showTranslatedMessage(
                                        "text.e4steam_minecraft.addressCopied",
                                        "Steam address copied");
                            } else {
                                platform.showTranslatedMessage(
                                        "text.e4steam_minecraft.addressCopyFailed",
                                        "Could not copy the Steam address");
                            }
                        }
                    });
                }
            }
            return true;
        }
        if ("invite".equals(action)) {
            SteamSession current = E4steamClient.session;
            if (current == null || current.state() != SteamSession.State.STARTED) {
                showTranslated("text.e4steam_minecraft.serverAlreadyClosed",
                        "This world is not being shared through Steam");
            } else {
                current.openInviteOverlayAsync().whenComplete((ignored, failure) -> {
                    if (failure != null) {
                        showTranslated("text.e4steam_minecraft.overlayUnavailable",
                                "The Steam invitation window is unavailable");
                    }
                });
            }
            return true;
        }
        if ("stop".equals(action)) {
            if (stopSharing()) {
                showTranslated("text.e4steam_minecraft.closeServer", "Steam sharing stopped");
            } else {
                showTranslated("text.e4steam_minecraft.serverAlreadyClosed",
                        "This world is not being shared through Steam");
            }
            return true;
        }
        if ("start".equals(action)) {
            if (startSharing(false)) {
                showTranslated("text.e4steam_minecraft.startSharing", "Starting Steam sharing");
            } else if (isActive(E4steamClient.session)) {
                showTranslated("text.e4steam_minecraft.serverAlreadyStarted",
                        "This world is already being shared through Steam");
            } else {
                showTranslated("text.e4steam_minecraft.serverAlreadyClosed",
                        "Open this world to LAN before starting Steam sharing");
            }
            return true;
        }
        if ("restart".equals(action)) {
            if (startSharing(true)) {
                showTranslated("text.e4steam_minecraft.startSharing", "Restarting Steam sharing");
            } else {
                showTranslated("text.e4steam_minecraft.serverAlreadyClosed",
                        "Open this world to LAN before restarting Steam sharing");
            }
            return true;
        }
        if ("doctor".equals(action)) {
            showDoctor();
            return true;
        }
        if ("addon".equals(action)) {
            showTranslated("text.e4steam_minecraft.command.addon.none",
                    "e4steam addons: no addons loaded");
            return true;
        }
        if ("help".equals(action)) {
            showHelp();
            return true;
        }
        showHelp();
        return true;
    }

    private static void showDoctor() {
        SteamSession current = E4steamClient.session;
        String session = current == null ? "STOPPED" : current.state().name();
        SteamRuntime runtime = SteamRuntime.get();
        showMessage("e4steam doctor: Steam=" + runtime.safeStatusCode()
                + ", session=" + session
                + ", LAN=" + (relayPort > 0 ? "READY" : "CLOSED"));
        String failure = runtime.safeFailureCategory();
        if (failure != null && !failure.isEmpty()) {
            showMessage("e4steam doctor: failure=" + failure);
        }
    }

    private static void showHelp() {
        showMessage("/e4steam <start|stop|restart|invite|doctor|addon|help>");
    }

    private static void showMessage(final String message) {
        final RetroPlatform platform = installedPlatform;
        if (platform == null) return;
        platform.execute(new Runnable() {
            @Override public void run() { platform.showMessage(message); }
        });
    }

    private static void showTranslated(final String key, final String fallback) {
        final RetroPlatform platform = installedPlatform;
        if (platform == null) return;
        platform.execute(new Runnable() {
            @Override public void run() { platform.showTranslatedMessage(key, fallback); }
        });
    }
}
