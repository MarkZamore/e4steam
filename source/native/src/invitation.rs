//! One-shot handoff from a verified Steam invitation to the game's normal join.
//!
//! An accepted overlay callback is an explicit join action, independent of the
//! periodically refreshed friends directory. Store only the already-verified
//! lobby/owner pair while the frontend saves and leaves its current world.
use std::time::{Duration, Instant};

#[derive(Default)]
pub(crate) struct InvitationHandoff {
    authorized: Option<(u64, u64, Instant)>,
}

impl InvitationHandoff {
    /// Call only after checking fresh lobby metadata, exact variant and the
    /// immediate friend's advertised ownership. Joining must recheck ownership.
    pub(crate) fn authorize(&mut self, lobby: u64, owner: u64, now: Instant) {
        self.authorized = Some((lobby, owner, now));
    }

    pub(crate) fn clear(&mut self) {
        self.authorized = None;
    }

    /// Any explicit join consumes the old intent, including a different target.
    /// This prevents a stale overlay action authorizing a later manual retry.
    pub(crate) fn take_owner(
        &mut self,
        lobby: u64,
        now: Instant,
        max_age: Duration,
    ) -> Option<u64> {
        let (authorized_lobby, owner, since) = self.authorized.take()?;
        (authorized_lobby == lobby && now.checked_duration_since(since)? <= max_age)
            .then_some(owner)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MAX_AGE: Duration = Duration::from_secs(30);

    #[test]
    fn verified_invitation_reaches_join_without_a_directory_entry_only_once() {
        let now = Instant::now();
        let mut handoff = InvitationHandoff::default();
        handoff.authorize(17, 31, now);
        // A frontend may spend time saving a world while discovery is refreshed.
        assert_eq!(
            handoff.take_owner(17, now + Duration::from_secs(4), MAX_AGE),
            Some(31)
        );
        assert_eq!(handoff.take_owner(17, now, MAX_AGE), None);
    }

    #[test]
    fn different_join_and_new_invitation_replace_old_intent() {
        let now = Instant::now();
        let mut handoff = InvitationHandoff::default();
        handoff.authorize(17, 31, now);
        assert_eq!(handoff.take_owner(23, now, MAX_AGE), None);
        assert_eq!(handoff.take_owner(17, now, MAX_AGE), None);
        handoff.authorize(17, 31, now);
        handoff.authorize(23, 37, now);
        assert_eq!(handoff.take_owner(23, now, MAX_AGE), Some(37));
    }

    #[test]
    fn expired_or_cleared_invitation_cannot_authorize_a_join() {
        let now = Instant::now();
        let mut handoff = InvitationHandoff::default();
        handoff.authorize(17, 31, now);
        assert_eq!(
            handoff.take_owner(17, now + MAX_AGE + Duration::from_millis(1), MAX_AGE),
            None
        );
        handoff.authorize(17, 31, now);
        handoff.clear();
        assert_eq!(handoff.take_owner(17, now, MAX_AGE), None);
    }
}
