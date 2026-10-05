import csv
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from core import scan, export_csv


class Tests(unittest.TestCase):
    def test_sizes_groups_and_top_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'nested').mkdir()
            (root / 'small.TXT').write_bytes(b'ab')
            (root / 'nested' / 'large.bin').write_bytes(b'x' * 30)
            (root / 'empty').write_bytes(b'')
            result = scan(root, limit=1)
            self.assertEqual((result.count, result.total), (3, 32))
            self.assertEqual(result.extensions['.txt'], [2, 1])
            self.assertEqual(result.folders['./nested'], [30, 1])
            self.assertEqual(result.largest, [(30, str((root / 'nested' / 'large.bin').resolve()))])
            out = root / 'report.csv'
            export_csv(result, out)
            with out.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[1][2:4], ['32', '3'])

    def test_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = threading.Event()
            event.set()
            result = scan(tmp, event)
            self.assertTrue(result.cancelled)
            self.assertEqual(result.count, 0)

    def test_permission_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('core.os.scandir', side_effect=PermissionError('denied')):
                result = scan(tmp)
            self.assertEqual(result.errors, 1)
            self.assertIn('denied', result.error_details[0])

    def test_symlink_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'file').write_bytes(b'123')
            try:
                (root / 'link').symlink_to(root / 'file')
            except OSError:
                self.skipTest('Symlink creation needs Windows Developer Mode or privilege')
            result = scan(root)
            self.assertEqual((result.count, result.skipped), (1, 1))

    def test_invalid_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                scan(Path(tmp) / 'missing')

    def test_windows_reparse_entry_skipped_without_privileges(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        import stat
        entry = MagicMock()
        entry.stat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        entries = MagicMock()
        entries.__enter__.return_value = iter([entry])
        with tempfile.TemporaryDirectory() as tmp, patch('core.os.scandir', return_value=entries):
            result = scan(tmp)
        self.assertEqual((result.count, result.skipped), (0, 1))
