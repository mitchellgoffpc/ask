import unittest
from pathlib import Path
from ask.edit import apply_section_edit, apply_udiff_edit, print_diff

class TestEdit(unittest.TestCase):
    def test_section_edit(self):
        for subdir in (Path(__file__).parent / 'test-cases').iterdir():
            if subdir.is_dir():
                with self.subTest(subdir=subdir):
                    original = (subdir / 'original.txt').read_text()
                    patch = (subdir / 'section.patch').read_text()
                    expected_result = (subdir / 'result.txt').read_text()
                    actual_result = apply_section_edit(original, patch)
                    try:
                        self.assertEqual(expected_result, actual_result)
                    except AssertionError:
                        print(f"Mismatch in {subdir}:")
                        print_diff(expected_result, actual_result, file_path=subdir)
                        raise

    def test_udiff_edit(self):
        for subdir in (Path(__file__).parent / 'test-cases').iterdir():
            if subdir.is_dir():
                with self.subTest(subdir=subdir):
                    original = (subdir / 'original.txt').read_text()
                    patch = (subdir / 'udiff.patch').read_text()
                    expected_result = (subdir / 'result.txt').read_text()
                    actual_result = apply_udiff_edit(original, patch)
                    try:
                        self.assertEqual(expected_result, actual_result)
                    except AssertionError:
                        print(f"Mismatch in {subdir}:")
                        print_diff(expected_result, actual_result, file_path=subdir)
                        raise


if __name__ == '__main__':
    unittest.main()
