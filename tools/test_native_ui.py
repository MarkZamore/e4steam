import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import subprocess
import zipfile

import native_ui as ui


class NativeUiDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = self.root / "author.jar"
        self.built = self.root / "source-built.jar"
        self.candidate = self.root / "derivative.jar"
        self.config = {"required": True, "mixins": ["AuthenticationMixin"],
                       "client": ["PauseScreenMixin", "ShareToLanScreenMixin", "MultiplayerOptionsScreenMixin",
                                  "WorldOptionsScreenMixin", "SteamTransportMixin"], "injectors": {"defaultRequire": 1}}
        self.header = b"\xca\xfe\xba\xbe\x00\x00\x00\x3d"
        self.pause = self.header + b"openInviteOverlayAsync text.e4steam_minecraft.inviteFriends"
        self.entries = {ui.PAUSE: self.pause + b" LanSettingsScreen text.e4steam_minecraft.lan.settings",
                        ui.MIXINS: json.dumps(self.config).encode(), "network/SteamSession.class": b"exact network bytes",
                        "native/steam_api64.dll": b"exact native bytes", "META-INF/LICENSE-e4steam.txt": b"author license",
                        "META-INF/NOTICE-e4steam.txt": b"author notice", "META-INF/mods.toml": b"original mod metadata"}
        self.write(self.original, self.entries)
        self.write(self.built, {ui.PAUSE: self.pause, ui.MIXINS: ui.without_redirects(self.entries[ui.MIXINS])})
        self.original_sha = hashlib.sha256(self.original.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, entries):
        with zipfile.ZipFile(path, "w") as z:
            for name, data in entries.items():
                z.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data)

    def derive(self):
        return ui.derive(self.original, self.built, self.candidate, self.original_sha)

    def test_only_declared_ui_entries_change_and_steam_authentication_invites_and_notices_survive(self):
        proof = self.derive()
        self.assertTrue(proof["allOtherEntriesByteIdentical"])
        with zipfile.ZipFile(self.candidate) as z:
            for name, data in self.entries.items():
                if name not in {ui.PAUSE, ui.MIXINS}:
                    self.assertEqual(data, z.read(name))
            updated = json.loads(z.read(ui.MIXINS))
            self.assertEqual(self.config["mixins"], updated["mixins"])
            self.assertEqual(self.config["injectors"], updated["injectors"])
            self.assertEqual(["PauseScreenMixin", "SteamTransportMixin"], updated["client"])
            self.assertEqual(self.pause, z.read(ui.PAUSE))
            self.assertIn(self.original_sha.encode(), z.read(ui.NOTICE))

    def test_repeated_preparation_produces_identical_derivative_bytes(self):
        self.derive()
        first = self.candidate.read_bytes()
        self.derive()
        self.assertEqual(first, self.candidate.read_bytes())

    def test_corrupted_author_pin_stops_before_creating_output(self):
        with self.assertRaisesRegex(ValueError, "Original SHA256"):
            ui.derive(self.original, self.built, self.candidate, "0" * 64)
        self.assertFalse(self.candidate.exists())

    def test_keeping_extra_ui_in_the_source_built_class_is_rejected(self):
        self.write(self.built, {ui.PAUSE: self.pause + b"LanSettingsScreen", ui.MIXINS: b'{"client":[]}'})
        with self.assertRaisesRegex(ValueError, "extra LAN settings"):
            self.derive()
        self.assertFalse(self.candidate.exists())

    def test_removing_steam_invite_functionality_is_rejected(self):
        self.write(self.built, {ui.PAUSE: self.header + b"no invitations", ui.MIXINS: b'{"client":[]}'})
        with self.assertRaisesRegex(ValueError, "Steam invitation"):
            self.derive()

    def test_different_jvm_target_is_rejected(self):
        self.write(self.built, {ui.PAUSE: self.pause[:7] + b"\x3e" + self.pause[8:], ui.MIXINS: b'{"client":[]}'})
        with self.assertRaisesRegex(ValueError, "JVM target"):
            self.derive()

    def test_source_built_form_redirect_is_rejected(self):
        self.write(self.built, {ui.PAUSE: self.pause, ui.MIXINS: self.entries[ui.MIXINS]})
        with self.assertRaisesRegex(ValueError, "still enables"):
            self.derive()

    def test_unrelated_transport_change_is_rejected_on_reverification(self):
        self.derive()
        with zipfile.ZipFile(self.candidate) as z:
            entries = {name: z.read(name) for name in z.namelist()}
        entries["network/SteamSession.class"] = b"tampered network"
        self.write(self.candidate, entries)
        with self.assertRaisesRegex(ValueError, "Unrelated author entry"):
            ui.verify_derivative(self.original, self.built, self.candidate, self.original_sha)

    def test_signature_metadata_is_not_silently_stripped(self):
        self.entries["META-INF/AUTHOR.SF"] = b"signature metadata"
        self.write(self.original, self.entries)
        self.original_sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "Signed author artifact"):
            self.derive()
        self.assertFalse(self.candidate.exists())

    def test_no_ui_retro_artifact_is_classified_without_changing_bytes(self):
        self.write(self.original, {"RetroTransport.class": b"unchanged native Steam", "NOTICE": b"author notice"})
        before = self.original.read_bytes()
        with zipfile.ZipFile(self.original) as z:
            self.assertFalse(ui.has_extra_ui(z))
        self.assertEqual(before, self.original.read_bytes())

    def test_failed_exact_byte_validation_prevents_all_remote_mutations(self):
        with mock.patch.object(ui, "verify_profile", side_effect=ValueError("unrelated transport mutation")), \
                mock.patch.object(ui.subprocess, "run") as probe, mock.patch.object(ui.components, "gh") as github:
            with self.assertRaisesRegex(ValueError, "transport mutation"):
                ui.publish(self.root, self.root, self.root)
            probe.assert_not_called()
            github.assert_not_called()

    def test_profile_publication_keeps_existing_assets_immutable_and_manifest_last(self):
        output = self.root / "publish"
        output.mkdir()
        files = ["one-lanmc-native-ui.1.jar", "native-ui.patch", "UPSTREAM.json", "SHA256SUMS.txt", "components.json"]
        for name in files:
            (output / name).write_bytes(name.encode())
        calls = []
        result = subprocess.CompletedProcess([], 0, json.dumps({"assets": []}), "")
        with mock.patch.object(ui, "verify_profile"), mock.patch.object(ui.subprocess, "run", return_value=result), \
                mock.patch.object(ui.components, "gh", side_effect=lambda *args: calls.append(args) or ""):
            ui.publish(self.root, self.root, output)
        uploads = [call for call in calls if call[:2] == ("release", "upload")]
        self.assertEqual(files, [call[3].name for call in uploads])
        self.assertTrue(all("--clobber" not in call and "delete" not in call for call in calls))

    def test_conflicting_existing_profile_asset_stops_before_any_upload(self):
        (self.root / "one-lanmc-native-ui.1.jar").write_bytes(b"candidate")
        result = subprocess.CompletedProcess([], 0, json.dumps({"assets": [
            {"name": "one-lanmc-native-ui.1.jar", "size": 9, "digest": "sha256:" + "0" * 64}]}), "")
        with mock.patch.object(ui, "verify_profile"), mock.patch.object(ui.subprocess, "run", return_value=result), \
                mock.patch.object(ui.components, "gh") as github:
            with self.assertRaisesRegex(ValueError, "Conflicting immutable"):
                ui.publish(self.root, self.root, self.root)
            github.assert_not_called()


if __name__ == "__main__":
    unittest.main()
