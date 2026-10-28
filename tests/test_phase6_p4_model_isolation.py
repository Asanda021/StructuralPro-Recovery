import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.ai.gguf_runtime_v1 import GGUFProductionRuntime


class ModelIsolationTests(unittest.TestCase):
    def test_manifest_cannot_authorize_artifact_outside_model_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models = root / 'models'
            models.mkdir()
            outside = root / 'outside.gguf'
            outside.write_bytes(b'GGUF-test-artifact-only')
            manifest = models / 'manifest.json'
            manifest.write_text(json.dumps({
                'format': 'gguf', 'internet_required': False,
                'model_files': [{
                    'name': 'test-only', 'path': '../outside.gguf',
                    'sha256': hashlib.sha256(outside.read_bytes()).hexdigest(),
                    'license': 'test-fixture-not-a-production-license',
                    'commercial_use': True,
                }],
            }))
            with self.assertRaisesRegex(ValueError, 'model root'):
                GGUFProductionRuntime(manifest).verify_artifact()


if __name__ == '__main__':
    unittest.main()
