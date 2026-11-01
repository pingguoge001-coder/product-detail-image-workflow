"""只用临时合成像素验证工具行为，不包含商品或个人图片。"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from common import safe_path
from verify_delivery import verify
from build_preview import build


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.data = {'product': '<商品A>', 'plan': {'detail_count': 0, 'include_introduction': False}, 'images': []}
        for i in range(1, 6):
            self.add(f'square{i:02}', (80, 80))
        self.add('basic_white', (800, 800))
        self.add('basic_transparent', (800, 800), transparent=True)
        self.add('basic_scene', (800, 800))
        self.add('basic_scene_long', (800, 1200), jpeg=True)
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, role, size, transparent=False, jpeg=False, kind=None, order=None):
        filename = role + ('.jpg' if jpeg else '.png')
        im = Image.new('RGBA' if transparent else 'RGB', size, (0, 0, 0, 0) if transparent else 'white')
        if transparent:
            im.putpixel((20, 20), (10, 20, 30, 255))
        im.save(self.root / filename, dpi=(72, 72))
        row = {'role': role, 'path': filename, 'status': 'generated'}
        if kind:
            row.update(type=kind, order=order)
        self.data['images'].append(row)

    def save(self):
        (self.root / 'delivery.json').write_text(json.dumps(self.data), encoding='utf-8')

    def test_valid_first_and_missing_role(self):
        self.assertTrue(verify(self.root, 'first')['file_checks_pass'])
        self.data['images'].pop()
        self.save()
        self.assertFalse(verify(self.root, 'first')['file_checks_pass'])

    def test_fake_transparency_and_near_white_fail(self):
        Image.new('RGB', (800, 800), 'white').save(self.root / 'basic_transparent.png', dpi=(72, 72))
        Image.new('RGB', (800, 800), (254, 254, 254)).save(self.root / 'basic_white.png', dpi=(72, 72))
        result = verify(self.root, 'first')
        self.assertFalse(result['file_checks_pass'])
        self.assertTrue(any('alpha' in s for s in result['errors']))
        self.assertTrue(any('纯白' in s for s in result['errors']))

    def test_unsafe_paths_rejected(self):
        for value in ('../outside.png', '/outside.png', 'Z:/outside.png', '..\\outside.png'):
            with self.assertRaises(ValueError):
                safe_path(self.root, value)

    def test_duplicate_and_encoding_mismatch(self):
        self.data['images'].append(dict(self.data['images'][0]))
        self.save()
        Image.new('RGB', (80, 80), 'white').save(self.root / 'square01.png', format='JPEG')
        result = verify(self.root, 'first')
        self.assertFalse(result['file_checks_pass'])
        self.assertTrue(any('重复' in s for s in result['errors']))
        self.assertTrue(any('编码' in s for s in result['errors']))

    def test_full_order_and_gapless_preview(self):
        for i in range(1, 6):
            self.add(f'vertical{i:02}', (80, 120))
        self.add('detail01', (80, 120), kind='detail', order=1)
        self.add('detail02', (80, 120), kind='introduction', order=2)
        self.add('detail03', (80, 120), kind='disclaimer', order=3)
        self.data['plan'] = {'detail_count': 3, 'include_introduction': True}
        self.save()
        self.assertTrue(verify(self.root, 'full')['file_checks_pass'])
        preview = build(self.root)
        html = preview.read_text(encoding='utf-8')
        self.assertIn('&lt;商品A&gt;', html)
        sequence = html.split('<div class="sequence">')[1].split('</div>')[0]
        self.assertEqual(sequence.count('<img '), 3)
        self.assertNotIn('<h2', sequence)
        self.assertLess(sequence.index('detail01.png'), sequence.index('detail03.png'))
        self.assertNotEqual(build(self.root), preview)
        self.data['images'][-1]['order'] = 1
        self.save()
        self.assertFalse(verify(self.root, 'full')['file_checks_pass'])
        with self.assertRaises(ValueError):
            build(self.root)

    def test_new_product_refuses_overwrite(self):
        command = [sys.executable, str(ROOT / 'tools/new_product.py'), '--root', str(self.root), '--slug', 'product-a', '--name', '商品A']
        first = subprocess.run(command, capture_output=True)
        self.assertEqual(first.returncode, 0)
        before = (self.root / 'product-a/facts.md').read_bytes()
        second = subprocess.run(command, capture_output=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(before, (self.root / 'product-a/facts.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
