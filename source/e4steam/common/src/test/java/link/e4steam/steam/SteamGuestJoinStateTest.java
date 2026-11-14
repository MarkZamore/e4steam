package link.e4steam.steam;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class SteamGuestJoinStateTest {
    @Test
    void canceledInvitationCannotBeClaimedOrConnected() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        state.cancel();
        assertFalse(state.claim());
        assertFalse(state.beginConnect(200));
        assertEquals(SteamGuestJoinState.Phase.CANCELED, state.phase());
    }

    @Test
    void connectingInvitationExpiresButConfirmationDoesNot() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertFalse(state.expired(Long.MAX_VALUE - 1));
        assertTrue(state.beginConnect(200));
        assertFalse(state.expired(199));
        assertTrue(state.expired(200));
    }

    @Test
    void lostLobbyCannotBecomeConnected() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.beginConnect(200));
        Object bridge = new Object();
        state.bridgeOpened(bridge);
        state.loseLobby();
        assertFalse(state.connected(bridge));
        assertEquals(SteamGuestJoinState.Phase.LOST, state.phase());
    }

    @Test
    void closingWorldWhileConnectingCancelsTheJoin() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.beginConnect(200));
        Object bridge = new Object();
        state.bridgeOpened(bridge);
        state.cancel();
        assertFalse(state.connected(bridge));
        assertEquals(SteamGuestJoinState.Phase.CANCELED, state.phase());
    }

    @Test
    void successfulJoinMovesToConnected() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.claim());
        assertTrue(state.beginConnect(200));
        Object bridge = new Object();
        state.bridgeOpened(bridge);
        assertTrue(state.connected(bridge));
        assertTrue(state.isConnected());
    }
    @Test
    void lateLoginFromCanceledAttemptDoesNotBlockNextInvitation() {
        SteamGuestJoinState previous = new SteamGuestJoinState(100);
        previous.waitForConfirmation();
        assertTrue(previous.beginConnect(200));
        Object previousBridge = new Object();
        previous.bridgeOpened(previousBridge);
        previous.cancel();

        SteamGuestJoinState retry = new SteamGuestJoinState(300);
        retry.waitForConfirmation();
        assertTrue(retry.claim());
        assertTrue(retry.beginConnect(400));
        assertFalse(previous.connected(previousBridge));
        assertFalse(retry.connected(previousBridge));
        assertFalse(previous.isConnected());
        assertEquals(SteamGuestJoinState.Phase.CONNECTING, retry.phase());
        assertTrue(retry.expired(400));
        Object nextBridge = new Object();
        retry.bridgeOpened(nextBridge);
        assertTrue(retry.connected(nextBridge));
        assertTrue(retry.isConnected());
        assertFalse(retry.expired(Long.MAX_VALUE - 1));
    }
    @Test
    void openingBridgeKeepsMinecraftLoginDeadline() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.beginConnect(200));
        Object bridge = new Object();
        state.bridgeOpened(bridge);
        assertFalse(state.isConnected());
        assertTrue(state.expired(200));
    }

    @Test
    void canceledBridgeCannotBeMistakenForRetryBridge() {
        Object oldBridge = new Object();
        SteamGuestJoinState previous = new SteamGuestJoinState(100);
        previous.waitForConfirmation();
        previous.beginConnect(200);
        previous.bridgeOpened(oldBridge);
        previous.cancel();
        assertFalse(previous.connected(oldBridge));
        previous.bridgeOpened(oldBridge);
        assertFalse(previous.connected(oldBridge));

        SteamGuestJoinState retry = new SteamGuestJoinState(300);
        retry.waitForConfirmation();
        retry.beginConnect(400);
        Object newBridge = new Object();
        retry.bridgeOpened(newBridge);
        assertFalse(retry.connected(oldBridge));
        assertTrue(retry.connected(newBridge));
    }

    @Test
    void statusProbeDoesNotReplaceTheEarlierLoginBridge() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.beginConnect(120_000));
        Object login = new Object();
        Object probe = new Object();
        state.bridgeOpened(login);
        state.bridgeOpened(probe);

        assertTrue(state.connected(login));
        assertFalse(state.expired(120_000));
        assertFalse(state.connected(probe));
        assertFalse(state.bridgeClosed(probe));
        assertTrue(state.bridgeClosed(login));
    }

    @Test
    void closedStatusProbeCannotCompleteOrCancelThePendingLogin() {
        SteamGuestJoinState state = new SteamGuestJoinState(100);
        state.waitForConfirmation();
        assertTrue(state.beginConnect(200));
        Object probe = new Object();
        state.bridgeOpened(probe);
        assertFalse(state.bridgeClosed(probe));
        assertFalse(state.connected(probe));
        assertTrue(state.expired(200));

        Object login = new Object();
        state.bridgeOpened(login);
        assertTrue(state.connected(login));
        Object laterProbe = new Object();
        state.bridgeOpened(laterProbe);
        assertFalse(state.connected(laterProbe));
        assertTrue(state.bridgeClosed(login));
    }
}
