import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import subprocess
import zipfile

import native_ui as prior
import native_ui_v2 as ui


class NativeLanAuthPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original, self.built, self.target = [self.root / name for name in ['author.jar', 'built.jar', 'candidate.jar']]
        self.header = b'\xca\xfe\xba\xbe\x00\x00\x00\x3d'
        self.pause = self.header + b'openInviteOverlayAsync text.e4steam_minecraft.inviteFriends'
        self.config = {'client': ['PauseScreenMixin', 'IntegratedServerLanMixin', 'ShareToLanScreenMixin',
                                  'MultiplayerOptionsScreenMixin', 'WorldOptionsScreenMixin'],
                       'mixins': ['ExactAuthenticationMixin'], 'injectors': {'defaultRequire': 1}}
        self.entries = {prior.PAUSE: self.pause + b' LanSettingsScreen',
                        prior.MIXINS: json.dumps(self.config).encode(),
                        ui.MIXIN: self.header + b'author integrated hooks',
                        ui.APPLIER: self.header + b'author settings applier',
                        'link/e4steam/Config.class': b'EXACT SAVED CONFIG',
                        'link/e4steam/steam/SteamMinecraftAuthentication.class': b'EXACT STEAM AUTH',
                        'link/e4steam/steam/SteamRuntime.class': b'EXACT STEAM TRANSPORT',
                        'META-INF/LICENSE-e4steam.txt': b'AUTHOR LICENSE',
                        'native/steam_api64.dll': b'EXACT NATIVE LIBRARY'}
        self.compiled = {prior.PAUSE: self.pause, prior.MIXINS: prior.without_redirects(self.entries[prior.MIXINS]),
                         ui.MIXIN: self.header + b'e4steam$applyPublishOnlineMode applyOnlineMode lanOnlineMode '
                                  b'/^(publishServer|method_3763|m_7386_|func_195457_a)$/',
                         ui.APPLIER: self.header + b'applyOnlineMode setUsesAuthentication method_3864 m_129985_'}
        self.source = {'sourcePatches': [{'sha256': '0' * 64}, {'sha256': '1' * 64}]}
        self.write(self.original, self.entries)
        self.write(self.built, self.compiled)
        self.author_sha = hashlib.sha256(self.original.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, entries):
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data)

    def derive(self):
        return ui.derive(self.original, self.built, self.target, self.author_sha, self.source)

    def test_only_four_declared_entries_change_preserving_steam_auth_transport_config_and_notices(self):
        proof = self.derive()
        self.assertEqual(ui.CHANGED, set(proof['changedEntries']))
        self.assertTrue(proof['allOtherEntriesByteIdentical'])
        with zipfile.ZipFile(self.target) as archive:
            for name, data in self.entries.items():
                if name not in ui.CHANGED:
                    self.assertEqual(data, archive.read(name))
            actual = json.loads(archive.read(prior.MIXINS))
            self.assertEqual(self.config['mixins'], actual['mixins'])
            self.assertEqual(self.config['injectors'], actual['injectors'])
            self.assertIn('IntegratedServerLanMixin', actual['client'])

    def test_missing_publish_hook_is_rejected_before_output(self):
        self.compiled[ui.MIXIN] = self.header + b'old hook'
        self.write(self.built, self.compiled)
        with self.assertRaisesRegex(ValueError, 'publish online-mode hook'):
            self.derive()
        self.assertFalse(self.target.exists())

    def test_missing_setter_bridge_is_rejected(self):
        self.compiled[ui.APPLIER] = self.header + b'applyOnlineMode'
        self.write(self.built, self.compiled)
        with self.assertRaisesRegex(ValueError, 'setter bridge'):
            self.derive()

    def test_different_jvm_target_is_rejected(self):
        self.compiled[ui.MIXIN] = self.compiled[ui.MIXIN][:7] + b'\x3e' + self.compiled[ui.MIXIN][8:]
        self.write(self.built, self.compiled)
        with self.assertRaisesRegex(ValueError, 'JVM target'):
            self.derive()

    def test_unrelated_transport_modification_is_rejected(self):
        self.derive()
        with zipfile.ZipFile(self.target) as archive:
            data = {name: archive.read(name) for name in archive.namelist()}
        data['link/e4steam/steam/SteamRuntime.class'] = b'CHANGED'
        self.write(self.target, data)
        with self.assertRaisesRegex(ValueError, 'exactly four'):
            ui.verify_derivative(self.original, self.built, self.target, self.author_sha, self.source)

    def test_missing_native_mixin_registration_is_rejected(self):
        self.config['client'].remove('IntegratedServerLanMixin')
        self.entries[prior.MIXINS] = json.dumps(self.config).encode()
        self.write(self.original, self.entries)
        self.author_sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'not registered'):
            self.derive()

    def test_repeated_derivation_is_identical(self):
        self.derive()
        first = self.target.read_bytes()
        self.derive()
        self.assertEqual(first, self.target.read_bytes())

    def test_changed_author_pin_stops_before_output(self):
        with self.assertRaisesRegex(ValueError, 'Original SHA256'):
            ui.derive(self.original, self.built, self.target, '0' * 64, self.source)
        self.assertFalse(self.target.exists())

    def metadata_fixture(self):
        def pin(name):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            return {'path': name, 'sizeBytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        document = {'profile': ui.PROFILE, 'upstreamCommit': prior.SOURCE_COMMIT,
                    'requiredFeatures': ui.FEATURES,
                    'sourcePatches': [pin('source/ui.patch'), pin('source/auth.patch')],
                    'sourceFiles': [pin('source/online.java')],
                    'authorInventory': [pin(name) for name in ['author-components.json', 'releases/v0.3.2.json', 'releases/v0.3.4.json']]}
        path = self.root / ui.META
        path.write_text(json.dumps(document), encoding='utf-8')
        return path, document

    def test_future_author_inventory_changes_require_rebase_before_staging(self):
        self.metadata_fixture()
        (self.root / 'author-components.json').write_bytes(b'new author release')
        with mock.patch.object(ui, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'source changed'):
            ui.metadata()

    def test_dropping_either_retained_feature_is_rejected(self):
        path, document = self.metadata_fixture()
        document['requiredFeatures'] = {**ui.FEATURES, 'configuredOnlineModeAtNativePublish': False}
        path.write_text(json.dumps(document), encoding='utf-8')
        with mock.patch.object(ui, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'behavior is not retained'):
            ui.metadata()

    def test_active_unpatched_or_previous_profile_cannot_replace_reviewed_selection(self):
        folder = self.root / 'profiles'; folder.mkdir()
        (folder / (ui.PROFILE + '.json')).write_text(json.dumps({'profile': ui.PROFILE}), encoding='utf-8')
        (self.root / 'components.json').write_text(json.dumps({'profile': 'native-lan-ui-v1'}), encoding='utf-8')
        with mock.patch.object(ui, 'ROOT', self.root), mock.patch.object(ui, 'metadata'), \
                self.assertRaisesRegex(ValueError, 'author fallback is forbidden'):
            ui.verify_active()

    def test_failed_profile_validation_prevents_ci_and_all_remote_mutations(self):
        with mock.patch.object(ui, 'verify_profile', side_effect=ValueError('changed native behavior')), \
                mock.patch.object(ui, 'require_ci') as ci, mock.patch.object(ui.subprocess, 'run') as probe, \
                mock.patch.object(ui.components, 'gh') as github:
            with self.assertRaisesRegex(ValueError, 'native behavior'):
                ui.publish(self.root, self.root, self.root, '1')
            ci.assert_not_called(); probe.assert_not_called(); github.assert_not_called()

    def test_failed_exact_ci_prevents_all_remote_mutations(self):
        with mock.patch.object(ui, 'verify_profile'), \
                mock.patch.object(ui, 'require_ci', side_effect=ValueError('exact CI failed')), \
                mock.patch.object(ui.subprocess, 'run') as probe, mock.patch.object(ui.components, 'gh') as github:
            with self.assertRaisesRegex(ValueError, 'exact CI'):
                ui.publish(self.root, self.root, self.root, '1')
            probe.assert_not_called(); github.assert_not_called()

    def publication_fixture(self):
        output = self.root / 'publish'; output.mkdir()
        for name in ['one-lanmc-native-ui.2.jar', 'native-ui.patch', 'native-lan-auth-v2.patch',
                     'native-lan-auth-v2.json', 'SHA256SUMS.txt', 'components.json']:
            (output / name).write_bytes(name.encode())
        return output

    def test_immutable_conflict_is_checked_before_any_upload(self):
        output = self.publication_fixture()
        probe = subprocess.CompletedProcess([], 0, json.dumps({'assets': [{'name': 'one-lanmc-native-ui.2.jar',
            'size': 1, 'digest': 'sha256:' + '0' * 64}]}), '')
        with mock.patch.object(ui, 'verify_profile'), mock.patch.object(ui, 'require_ci', return_value='head'), \
                mock.patch.object(ui.subprocess, 'run', return_value=probe), mock.patch.object(ui.components, 'gh') as github:
            with self.assertRaisesRegex(ValueError, 'Conflicting immutable'):
                ui.publish(self.root, self.root, output, '1')
            github.assert_not_called()

    def test_publication_uploads_verified_payloads_first_manifest_last_without_overwrite(self):
        output = self.publication_fixture(); calls = []
        probe = subprocess.CompletedProcess([], 0, json.dumps({'assets': []}), '')
        with mock.patch.object(ui, 'verify_profile'), mock.patch.object(ui, 'require_ci', return_value='head'), \
                mock.patch.object(ui.subprocess, 'run', return_value=probe), \
                mock.patch.object(ui.components, 'gh', side_effect=lambda *args: calls.append(args)):
            ui.publish(self.root, self.root, output, '1')
        self.assertEqual('components.json', calls[-1][3].name)
        self.assertTrue(calls[0][3].name.endswith('.jar'))
        self.assertTrue(all('--clobber' not in call and 'delete' not in call for call in calls))

    def test_a_different_ci_revision_cannot_authorize_publication(self):
        run = {'head_sha': 'different', 'conclusion': 'success', 'path': '.github/workflows/native-ui.yml'}
        with mock.patch.object(ui.subprocess, 'check_output', side_effect=['head', '']), \
                mock.patch.object(ui.components, 'gh', return_value=json.dumps(run)), \
                self.assertRaisesRegex(ValueError, 'Exact source'):
            ui.require_ci('1')


if __name__ == '__main__':
    unittest.main()
