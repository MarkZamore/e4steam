import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import active_profile as active
import components
import legacy_fabric_164 as build


class ActiveProfileDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'profiles').mkdir()
        (self.root/'releases'/active.TAG).mkdir(parents=True)
        for name in (active.V2,active.V3):
            (self.root/'profiles'/f'{name}.json').write_bytes((active.ROOT/'profiles'/f'{name}.json').read_bytes())
        receipt='releases/'+active.TAG+'/build-receipt.json'
        (self.root/receipt).write_bytes((active.ROOT/receipt).read_bytes())

    def tearDown(self):self.temp.cleanup()

    def select(self,profile):
        data=(self.root/'profiles'/f'{profile}.json').read_bytes()
        (self.root/'components.json').write_bytes(data)
        document=json.loads(data)
        (self.root/'SHA256SUMS.txt').write_bytes(components.checksums(document['builds']).encode())
        return document

    def rewrite_frozen_and_active(self,document):
        payload=(json.dumps(document,indent=2,sort_keys=True)+'\n').encode()
        (self.root/'profiles'/f'{document["profile"]}.json').write_bytes(payload)
        (self.root/'components.json').write_bytes(payload)
        (self.root/'SHA256SUMS.txt').write_bytes(components.checksums(document['builds']).encode())

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
        path=self.root/'releases'/active.TAG/'build-receipt.json';path.write_bytes(path.read_bytes()+b'\n')
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
