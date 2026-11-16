import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import active_profile as active
import components
import forge_guest_profile as guest
import legacy_fabric_164 as build


class ActiveProfileDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'profiles').mkdir()
        (self.root/'releases'/active.V3_TAG).mkdir(parents=True)
        for name in (active.V2,active.V3):
            (self.root/'profiles'/f'{name}.json').write_bytes((active.ROOT/'profiles'/f'{name}.json').read_bytes())
        receipt='releases/'+active.V3_TAG+'/build-receipt.json'
        (self.root/receipt).write_bytes((active.ROOT/receipt).read_bytes())

    def tearDown(self):self.temp.cleanup()

    def select(self,profile):
        data=(self.root/'profiles'/f'{profile}.json').read_bytes()
        (self.root/'components.json').write_bytes(data)
        document=json.loads(data)
        self.write_checksums(document)
        return document

    def write_checksums(self, document):
        rows = guest.all_rows(document) if document['profile'] in active.FORGE_GUEST_PROFILES else document['builds']
        (self.root/'SHA256SUMS.txt').write_bytes(components.checksums(rows).encode())

    def rewrite_frozen_and_active(self,document):
        payload=(json.dumps(document,indent=2,sort_keys=True)+'\n').encode()
        (self.root/'profiles'/f'{document["profile"]}.json').write_bytes(payload)
        (self.root/'components.json').write_bytes(payload)
        self.write_checksums(document)

    def test_v2_dispatch_retains_historical_builder_provenance_checks(self):
        document=self.select(active.V2)
        with mock.patch.object(active.native_ui_v2,'verify_active',return_value=document) as verifier:
            self.assertEqual(document,active.verify_active(self.root))
        verifier.assert_called_once_with()
        with mock.patch.object(active.native_ui_v2,'verify_active',side_effect=ValueError('historical provenance failed')):
            with self.assertRaisesRegex(ValueError,'historical provenance'):active.verify_active(self.root)

    def test_v3_is_verified_without_calling_v2_active_selector(self):
        self.select(active.V3)
        with mock.patch.object(active.native_ui_v2,'verify_active',side_effect=AssertionError('V2 cannot select V3')):
            document=active.verify_active(self.root)
        self.assertEqual(20,len(document['builds']))

    def assert_new_legacy_revision(self, profile, revision):
        previous = self.select(active.V3)
        candidate = json.loads((self.root/'components.json').read_bytes())
        candidate['profile'] = profile
        candidate['sourceCommit'] = '1' * 40
        for row in candidate['builds']:
            row['profile'] = profile
        legacy = next(row for row in candidate['builds'] if row['loaders'] == ['LegacyFabric'])
        prior_legacy = next(row for row in previous['builds'] if row['loaders'] == ['LegacyFabric'])
        receipt = json.loads((self.root/'releases'/active.V3_TAG/'build-receipt.json').read_bytes())
        filename=f'e4steam-legacy-fabric-mc1.6.4-v0.3.4-lf164.{revision}.jar'
        tag=f'legacy-fabric-164-v{revision}'
        receipt.update(fileName=filename, sizeBytes=receipt['sizeBytes'] + 1, sha256='2' * 64)
        release_dir = self.root/'releases'/tag
        release_dir.mkdir()
        receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()
        (release_dir/'build-receipt.json').write_bytes(receipt_bytes)
        url = f'https://github.com/MarkZamore/e4steam/releases/download/{tag}/'
        legacy.update(fileName=filename, sizeBytes=receipt['sizeBytes'], sha256=receipt['sha256'],
                      deliveryTag=tag, downloadUrl=url + filename)
        legacy['derivation'].update(
            sourceCommit=candidate['sourceCommit'],
            sourceBuildReceipt=dict(fileName='build-receipt.json', sizeBytes=len(receipt_bytes),
                                    sha256=hashlib.sha256(receipt_bytes).hexdigest(),
                                    downloadUrl=url + 'build-receipt.json'),
        )
        self.rewrite_frozen_and_active(candidate)
        if profile == active.V6:
            active.verify_legacy_profile(self.root, candidate)
        else:
            self.assertEqual(candidate, active.verify_active(self.root))
        self.assertEqual(previous, json.loads((self.root/'profiles'/f'{active.V3}.json').read_bytes()))
        legacy['deliveryTag'] = prior_legacy['deliveryTag']
        self.rewrite_frozen_and_active(candidate)
        with self.assertRaisesRegex(ValueError, 'immutable legacy delivery'):
            if profile == active.V6:
                active.verify_legacy_profile(self.root, candidate)
            else:
                active.verify_active(self.root)

    def test_v5_only_replaces_the_legacy_artifact(self):
        self.assert_new_legacy_revision(active.V5,3)

    def test_v6_only_replaces_the_legacy_artifact(self):
        self.assert_new_legacy_revision(active.V6,4)

    def select_published_v6(self):
        snapshot = Path('profiles') / f'{guest.BASE_SNAPSHOT}.json'
        receipt = Path('releases/legacy-fabric-164-v4/build-receipt.json')
        (self.root / receipt).parent.mkdir(parents=True)
        for path in (snapshot, receipt):
            (self.root / path).write_bytes((active.ROOT / path).read_bytes())
        return self.select(guest.BASE_SNAPSHOT)

    def test_published_v6_preserves_both_optional_java8_selections(self):
        document = self.select_published_v6()
        self.assertEqual(2, len(active.verify_active(self.root)['java8Builds']))
        document['java8Builds'].pop()
        (self.root / 'components.json').write_text(json.dumps(document), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'index bytes'):
            active.verify_active(self.root)

    def test_guest_profile_only_changes_the_modern_forge_artifact(self):
        baseline = self.select_published_v6()
        receipt_dir = self.root / 'releases' / guest.TAG
        receipt_dir.mkdir()
        receipt_data = json.dumps({
            'schemaVersion': 1, 'stockSha256': guest.STOCK_SHA256,
            'build': {'fileName': guest.FILE, 'sizeBytes': 10, 'sha256': '3' * 64},
            'changedEntries': sorted(guest.GUEST_CLASSES),
            'sourceBuiltClassSha256': {path: '4' * 64 for path in guest.GUEST_CLASSES},
        }).encode()
        (receipt_dir / guest.RECEIPT).write_bytes(receipt_data)
        document = guest.candidate_index(baseline, receipt_data, '1' * 40)
        self.rewrite_frozen_and_active(document)
        self.assertEqual(document, active.verify_active(self.root))
        self.assertEqual(22, len(guest.all_rows(document)))
        for previous, current in zip(guest.all_rows(baseline), guest.all_rows(document)):
            if previous['fileName'] != guest.FILE:
                self.assertEqual({**previous, 'profile': guest.PROFILE}, current)
        document['java8Builds'][0]['sha256'] = '5' * 64
        self.rewrite_frozen_and_active(document)
        with self.assertRaisesRegex(ValueError, 'single-row update'):
            active.verify_active(self.root)

    def test_guest_receipt_cannot_include_an_unrelated_class(self):
        classes = {path: '4' * 64 for path in guest.GUEST_CLASSES}
        classes['link/e4steam/Mirror.class'] = '5' * 64
        receipt = {
            'schemaVersion': 1, 'stockSha256': guest.STOCK_SHA256,
            'build': {'fileName': guest.FILE, 'sizeBytes': 10, 'sha256': '3' * 64},
            'changedEntries': sorted(classes),
            'sourceBuiltClassSha256': classes,
        }
        with self.assertRaisesRegex(ValueError, 'exactly three'):
            guest.read_receipt(json.dumps(receipt).encode())

    def test_guest_chat_extends_only_the_published_forge_row(self):
        self.select_published_v6()
        snapshot = Path('profiles') / f'{guest.PROFILE}.json'
        previous_receipt = Path('releases') / guest.TAG / guest.RECEIPT
        (self.root / previous_receipt).parent.mkdir(parents=True)
        for path in (snapshot, previous_receipt):
            (self.root / path).write_bytes((active.ROOT / path).read_bytes())
        base = guest.read_guest_only(self.root)
        target = next(row for row in base['builds'] if row['fileName'] == guest.FILE)
        classes = {name: target['derivation']['sourceBuiltClassSha256'][name] for name in guest.GUEST_CLASSES}
        classes[guest.CHAT_CLASS] = '5' * 64
        receipt = {
            'schemaVersion': 1, 'stockSha256': guest.STOCK_SHA256,
            'build': {'fileName': guest.FILE, 'sizeBytes': 10, 'sha256': '3' * 64},
            'changedEntries': sorted(classes), 'sourceBuiltClassSha256': classes,
            'guestOnlySha256': guest.GUEST_ONLY_SHA256,
            'changedEntriesFromGuestOnly': [guest.CHAT_CLASS],
        }
        receipt_data = json.dumps(receipt).encode()
        current_receipt = self.root / 'releases' / guest.TAG_WITH_CHAT / guest.RECEIPT
        current_receipt.parent.mkdir(parents=True)
        current_receipt.write_bytes(receipt_data)
        document, _ = guest.candidate_with_chat(self.root, base, receipt_data, '2' * 40)
        self.rewrite_frozen_and_active(document)
        self.assertEqual(document, active.verify_active(self.root))
        for previous, current in zip(guest.all_rows(base), guest.all_rows(document)):
            if previous['fileName'] != guest.FILE:
                self.assertEqual({**previous, 'profile': guest.PROFILE_WITH_CHAT}, current)
        classes[next(iter(guest.GUEST_CLASSES))] = '6' * 64
        with self.assertRaisesRegex(ValueError, 'changes the verified guest timeout'):
            guest.candidate_with_chat(self.root, base, json.dumps(receipt).encode(), '2' * 40)
        with (self.root / snapshot).open('ab') as handle:
            handle.write(b'\n')
        with self.assertRaisesRegex(ValueError, 'Frozen V7 selection'):
            active.verify_active(self.root)

    def test_semantically_equal_but_byte_different_active_index_is_rejected(self):
        self.select(active.V3)
        with (self.root/'components.json').open('ab') as handle:handle.write(b'\n')
        with self.assertRaisesRegex(ValueError,'index bytes'):active.verify_active(self.root)

    def test_corrupt_or_noncanonical_checksum_inventory_is_rejected(self):
        self.select(active.V3)
        path=self.root/'SHA256SUMS.txt';path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n'))
        with self.assertRaisesRegex(ValueError,'checksum bytes'):active.verify_active(self.root)

    def test_changed_old_target_cannot_be_hidden_in_a_new_frozen_profile(self):
        document=self.select(active.V3)
        row=next(row for row in document['builds'] if row['loaders']!=['LegacyFabric'])
        row['sha256']='0'*64;self.rewrite_frozen_and_active(document)
        with self.assertRaisesRegex(ValueError,'existing target'):active.verify_active(self.root)

    def test_corrupt_frozen_receipt_is_rejected(self):
        self.select(active.V3)
        path=self.root/'releases'/active.V3_TAG/'build-receipt.json';path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'receipt pin'):active.verify_active(self.root)

    def test_legacy_source_port_cannot_claim_a_nonexistent_author_jar(self):
        document=self.select(active.V3)
        row=next(row for row in document['builds'] if row['loaders']==['LegacyFabric'])
        row['authorFileName']='nonexistent-author.jar';self.rewrite_frozen_and_active(document)
        with self.assertRaisesRegex(ValueError,'invent an author'):active.verify_active(self.root)

    def test_unknown_profile_cannot_select_author_fallback(self):
        (self.root/'components.json').write_bytes(b'{"profile":"author-latest"}')
        with self.assertRaisesRegex(ValueError,'author fallback'):active.verify_active(self.root)

    def test_source_path_order_is_posix_ordinal_on_every_host(self):
        relative=['z.java','a.java','Z-dir/file.java','Alpha.java']
        paths=[build.ROOT/name for name in relative]
        self.assertEqual(sorted(relative),[path.relative_to(build.ROOT).as_posix() for path in build.ordered_paths(paths)])

    def test_cold_source_dependency_identifies_request_and_verifies_pinned_bytes(self):
        payload=b'fixture dependency bytes';cache=self.root/'cache';cache.mkdir()
        row=('org.spongepowered','mixin','fixture',hashlib.sha256(payload).hexdigest(),False)
        requests=[]
        def response(request,timeout):
            requests.append(request)
            self.assertEqual('LANMinecraft-source-reproduction/1.0',request.get_header('User-agent'))
            return io.BytesIO(payload)
        with mock.patch.object(build.Path,'home',return_value=self.root),mock.patch.object(build.urllib.request,'urlopen',side_effect=response):
            path=build.dependency(row,cache)
        self.assertEqual(payload,path.read_bytes());self.assertEqual(1,len(requests))
        self.assertTrue(requests[0].full_url.startswith('https://repo.spongepowered.org/'))

    def test_cold_dependency_digest_failure_does_not_leave_trusted_cache_file(self):
        cache=self.root/'cache';cache.mkdir()
        row=('org.spongepowered','mixin','fixture','0'*64,False)
        with mock.patch.object(build.Path,'home',return_value=self.root),mock.patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong bytes')):
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):build.dependency(row,cache)
        self.assertFalse((cache/'mixin-fixture.jar').exists())


if __name__=='__main__':unittest.main()
