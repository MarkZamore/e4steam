package link.e4steam.retro;

import link.e4steam.E4steamClient;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

public class RetroManagedLanTest {
    private static final String MANAGED_PROPERTY = "link.e4steam.launcherManagedLan";
    private String original;

    @Before public void enablePolicy() {
        original = System.setProperty(MANAGED_PROPERTY, "true");
    }

    @After public void resetPolicy() {
        RetroBootstrap.relayClosed();
        if (original == null) System.clearProperty(MANAGED_PROPERTY);
        else System.setProperty(MANAGED_PROPERTY, original);
    }

    @Test public void failedNativePublicationDoesNotStartSteamAndReleasesRelay() {
        assertTrue(RetroBootstrap.beginPublication());
        Object failed = RetroBootstrap.relayTicket();
        assertNotNull(failed);
        assertFalse(RetroBootstrap.beginPublication());
        AtomicInteger closed = new AtomicInteger();
        assertTrue(RetroBootstrap.relayBound(32600, failed, closed::incrementAndGet));
        assertNull(E4steamClient.session);

        RetroBootstrap.cancelPublication();

        assertEquals(1, closed.get());
        assertNull(RetroBootstrap.relayTicket());
        assertFalse(RetroBootstrap.relayBound(32601, failed, closed::incrementAndGet));
        assertNull(E4steamClient.session);
    }

    @Test public void closingAndReopeningRejectsThePreviousNativeRelay() {
        assertTrue(RetroBootstrap.beginPublication());
        Object first = RetroBootstrap.relayTicket();
        RetroBootstrap.publishRelay("Author world", "Launcher user");
        RetroBootstrap.cancelPublication();
        assertSame(first, RetroBootstrap.relayTicket());
        assertNull(E4steamClient.session);
        RetroBootstrap.relayClosed();

        assertTrue(RetroBootstrap.beginPublication());
        Object next = RetroBootstrap.relayTicket();
        assertNotSame(first, next);
        assertFalse(RetroBootstrap.relayBound(32602, first, () -> { }));
        assertNull(E4steamClient.session);
    }
}
