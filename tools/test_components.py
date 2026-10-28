import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

import components


class SharedComponentPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.output = self.root / 'dist'
        self.name = 'e4steam-test-v0.3.4.jar'
        self.jar = self.cache / self.name
        with zipfile.ZipFile(self.jar, 'w') as archive:
            archive.writestr('META-INF/LICENSE-e4steam.txt', 'retained author license')
            archive.writestr('META-INF/NOTICE-e4steam.txt', 'retained author notice')
        self.build = dict(fileName=self.name, version='0.3.4', sizeBytes=self.jar.stat().st_size,
                          sha256=hashlib.sha256(self.jar.read_bytes()).hexdigest())
        self.document = dict(schemaVersion=1, componentId='e4steam', builds=[self.build])
        self.index = mock.patch.object(components, 'load_index', return_value=self.document)
        self.index.start()
        components.stage(self.output, self.cache)

    def tearDown(self):
        self.index.stop()
        self.temp.cleanup()

    def release_probe(self, assets):
        return mock.patch.object(components.subprocess, 'run', return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({'assets': assets}), stderr=''))

    def test_changed_jar_stops_before_any_github_mutation(self):
        (self.output / 'v0.3.4' / self.name).write_bytes(b'corrupt replacement')
        with mock.patch.object(components, 'gh') as github:
            with self.assertRaisesRegex(ValueError, 'Size/SHA-256'):
                components.publish(self.output)
            github.assert_not_called()

    def test_payload_and_checksums_publish_before_manifest_without_clobber(self):
        calls = []
        with self.release_probe([]), mock.patch.object(components, 'gh', side_effect=lambda *args: calls.append(args) or ''):
            components.publish(self.output)
        uploads = [call for call in calls if call[:2] == ('release', 'upload')]
        self.assertEqual([self.name, 'SHA256SUMS.txt', 'components.json'], [pathlib.Path(call[3]).name for call in uploads])
        self.assertTrue(all('--clobber' not in call and 'delete' not in call for call in calls))

    def test_conflicting_existing_versioned_asset_is_never_overwritten(self):
        existing = dict(name=self.name, size=self.build['sizeBytes'], digest='sha256:' + '0' * 64)
        with self.release_probe([existing]), mock.patch.object(components, 'gh') as github:
            with self.assertRaisesRegex(ValueError, 'Conflicting immutable'):
                components.publish(self.output)
            github.assert_not_called()


if __name__ == '__main__':
    unittest.main()
