#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Host-only kernel preparation tests; Git patch operations are mocked."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('prepare.sh')
KERNEL = None


class KernelPreparation(unittest.TestCase):
    def execute(self, ready=None, source=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        device = root / 'device/lenovo/X606X'
        (device / 'tools').mkdir(parents=True)
        (device / 'prebuilt').mkdir()
        shutil.copyfile(SCRIPT, device / 'tools/prepare.sh')
        target = device / 'prebuilt/x606x_Image.gz'
        if ready == 'valid':
            shutil.copyfile(KERNEL, target)
        elif ready == 'invalid':
            target.write_bytes(b'wrong kernel')
        mock_bin = root / 'mock-bin'
        mock_bin.mkdir()
        git = mock_bin / 'git'
        git.write_text('#!/bin/sh\nprintf "called\\n" >> "$MOCK_GIT_LOG"\nexit 0\n')
        git.chmod(0o755)
        source_path = root / 'input-kernel'
        if source == 'valid':
            shutil.copyfile(KERNEL, source_path)
        elif source == 'invalid':
            source_path.write_bytes(b'wrong source')
        env = dict(os.environ, PATH=str(mock_bin) + ':' + os.environ['PATH'],
                   KERNEL_SOURCE=str(source_path), MOCK_GIT_LOG=str(root / 'git.log'))
        result = subprocess.run(['bash', str(device / 'tools/prepare.sh'), str(root / 'missing-lineage')],
                                env=env, capture_output=True, text=True)
        return root, target, result

    def test_ready_kernel_needs_no_lineage_checkout(self):
        _, target, result = self.execute(ready='valid')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), KERNEL.read_bytes())

    def test_explicit_valid_kernel_is_imported(self):
        _, target, result = self.execute(source='valid')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), KERNEL.read_bytes())

    def test_invalid_ready_kernel_fails_before_git(self):
        root, _, result = self.execute(ready='invalid', source='valid')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / 'git.log').exists())

    def test_invalid_input_fails_before_git_or_copy(self):
        root, target, result = self.execute(source='invalid')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertFalse((root / 'git.log').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    args = parser.parse_args()
    KERNEL = args.kernel.resolve(strict=True)
    unittest.main(argv=['test_prepare.py'])
