package link.e4steam.steam;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;

/** Testable guest invitation and lobby lifecycle, independent of native callbacks. */
final class SteamGuestJoinState {
    enum Phase {
        RESOLVING,
        WAITING_FOR_CONFIRMATION,
        CONNECTING,
        CONNECTED,
        CANCELED,
        LOST
    }

    private Phase phase = Phase.RESOLVING;
    private long deadlineMillis;
    private boolean claimed;
    private final Set<Object> pendingBridges = Collections.newSetFromMap(new IdentityHashMap<>());
    private Object connectedBridge;

    SteamGuestJoinState(long deadlineMillis) {
        this.deadlineMillis = deadlineMillis;
    }

    void waitForConfirmation() {
        if (phase == Phase.RESOLVING) {
            phase = Phase.WAITING_FOR_CONFIRMATION;
            deadlineMillis = Long.MAX_VALUE;
        }
    }

    boolean claim() {
        if (claimed || phase != Phase.WAITING_FOR_CONFIRMATION) {
            return false;
        }
        claimed = true;
        return true;
    }

    boolean beginConnect(long deadlineMillis) {
        if (phase != Phase.WAITING_FOR_CONFIRMATION) {
            return false;
        }
        claimed = true;
        phase = Phase.CONNECTING;
        this.deadlineMillis = deadlineMillis;
        return true;
    }

    void bridgeOpened(Object bridge) {
        if (phase == Phase.CONNECTING) pendingBridges.add(bridge);
    }

    /** Returns true only when the Minecraft connection that completed login closes. */
    boolean bridgeClosed(Object bridge) {
        pendingBridges.remove(bridge);
        return phase == Phase.CONNECTED && connectedBridge == bridge;
    }

    boolean connected(Object bridge) {
        if (phase != Phase.CONNECTING || !pendingBridges.contains(bridge)) return false;

        // Multiplayer status probes can open more bridges while Forge is logging in.
        // Only the bridge that Minecraft actually used for login owns the session.
        pendingBridges.clear();
        connectedBridge = bridge;
        phase = Phase.CONNECTED;
        deadlineMillis = Long.MAX_VALUE;
        return true;
    }

    boolean expired(long nowMillis) {
        return (phase == Phase.RESOLVING || phase == Phase.CONNECTING)
                && deadlineMillis <= nowMillis;
    }

    boolean isConnected() {
        return phase == Phase.CONNECTED;
    }

    void cancel() {
        if (phase != Phase.LOST) {
            phase = Phase.CANCELED;
            pendingBridges.clear();
            connectedBridge = null;
            deadlineMillis = Long.MIN_VALUE;
        }
    }

    void loseLobby() {
        phase = Phase.LOST;
        pendingBridges.clear();
        connectedBridge = null;
        deadlineMillis = Long.MIN_VALUE;
    }

    Phase phase() {
        return phase;
    }
}
