"""核验当前清单与实际文件；不做文字识别、包装验真或用户采用判断。"""
from pathlib import Path
import argparse
import hashlib
import json
import re
from PIL import Image
from common import load_delivery, safe_path

FIRST = {f'square{i:02}' for i in range(1, 6)} | {
    'basic_white', 'basic_transparent', 'basic_scene', 'basic_scene_long'}
STATUSES = {'generated', 'file_verified', 'reviewed', 'adopted'}


def verify(root, phase):
    data = load_delivery(root)
    errors, checks = [], []
    seen_roles, seen_paths = set(), set()
    for row in data['images']:
        role = row['role']
        item = {'role': role, 'path': row['path'], 'errors': []}
        err = item['errors']
        if role in seen_roles:
            err.append('同一图位重复，清单只能列当前版本')
        seen_roles.add(role)
        p = safe_path(root, row['path'])
        if p in seen_paths:
            err.append('不同图位指向同一文件')
        seen_paths.add(p)
        if row.get('status') not in STATUSES:
            err.append('status 缺失或无效')
        if len(p.name) > 46:
            err.append('文件名超过46字符的内部规范')
        if not p.is_file():
            err.append('文件不存在')
        else:
            try:
                with Image.open(p) as im:
                    im.load()
                    w, h = im.size
                    item.update(size=[w, h], format=im.format, bytes=p.stat().st_size,
                                sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                    expected_format = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG'}.get(p.suffix.lower())
                    if expected_format is None or im.format != expected_format:
                        err.append('扩展名与真实PNG/JPG编码不符')
                    if role.startswith('square') or role in {'basic_white', 'basic_transparent', 'basic_scene'}:
                        if w != h:
                            err.append('要求1:1画幅')
                    if role.startswith('vertical') or role == 'basic_scene_long' or row.get('type') in {'detail', 'disclaimer'}:
                        if w * 3 != h * 2:
                            err.append('要求2:3画幅')
                    if role.startswith('basic_'):
                        target = (800, 1200) if role == 'basic_scene_long' else (800, 800)
                        if im.size != target:
                            err.append('基础素材实际尺寸不符')
                        if role != 'basic_scene_long':
                            dpi = im.info.get('dpi')
                            item['dpi'] = dpi
                            if not dpi or len(dpi) != 2 or any(abs(float(v) - 72) > .1 for v in dpi):
                                err.append('基础素材缺少约72dpi元数据')
                        if role in {'basic_white', 'basic_transparent', 'basic_scene_long'} and p.stat().st_size >= 3_000_000:
                            err.append('文件须小于3MB')
                        if role == 'basic_scene_long' and im.format != 'JPEG':
                            err.append('场景长图须真实JPG编码')
                        if role == 'basic_transparent':
                            if im.format != 'PNG' or 'A' not in im.getbands():
                                err.append('透明图须带alpha通道的PNG')
                            else:
                                extrema = im.getchannel('A').getextrema()
                                item['alpha_range'] = list(extrema)
                                if extrema != (0, 255):
                                    err.append('须同时含全透明背景和不透明商品像素')
                        if role == 'basic_white':
                            rgb = im.convert('RGB')
                            edges = [(x, y) for x in range(w) for y in (0, h - 1)]
                            edges += [(x, y) for y in range(h) for x in (0, w - 1)]
                            item['white_edge_pass'] = all(rgb.getpixel(pt) == (255, 255, 255) for pt in edges)
                            if not item['white_edge_pass']:
                                err.append('白底外缘含非纯白像素')
                            if 'A' in im.getbands() and im.getchannel('A').getextrema()[0] != 255:
                                err.append('白底图不能含透明背景')
            except Exception as ex:
                err.append('无法解码/核验：' + type(ex).__name__)
        if err:
            errors.extend(f'{role}: {v}' for v in err)
        checks.append(item)
    required = set(FIRST)
    if phase == 'full':
        required |= {f'vertical{i:02}' for i in range(1, 6)}
        details = [r for r in data['images'] if r.get('type') in {'detail', 'report', 'introduction', 'disclaimer'}]
        count = data['plan'].get('detail_count')
        if type(count) is not int or count < 1 or len(details) != count:
            errors.append('详情实际页数须与plan.detail_count正整数一致')
        orders = [r.get('order') for r in details]
        if any(type(x) is not int for x in orders) or sorted(orders) != list(range(1, len(details) + 1)):
            errors.append('详情order须从1连续且唯一')
        else:
            ordered = sorted(details, key=lambda r: r['order'])
            disclaimers = [r for r in ordered if r.get('type') == 'disclaimer']
            if len(disclaimers) != 1 or ordered[-1].get('type') != 'disclaimer':
                errors.append('特别说明须有且仅有一页，并在最后')
            introductions = [r for r in ordered if r.get('type') == 'introduction']
            if data['plan'].get('include_introduction'):
                if len(introductions) != 1 or len(ordered) < 2 or ordered[-2].get('type') != 'introduction':
                    errors.append('有自有介绍页时须唯一且处于倒数第二')
            elif introductions:
                errors.append('plan未启用介绍页，清单却含介绍页')
    for role in sorted(required - seen_roles):
        errors.append('缺少图位：' + role)
    valid_role = re.compile(r'(square|vertical)0[1-5]$|detail\d{2,}$|report\d{2,}$|introduction$|disclaimer$')
    for row in data['images']:
        role = row['role']
        if role not in FIRST and not valid_role.fullmatch(role):
            errors.append('未知图位：' + role)
        if role.startswith('detail') and row.get('type') not in {'detail', 'report', 'introduction', 'disclaimer'}:
            errors.append(role + ': 缺少有效详情type')
    return {'phase': phase, 'file_checks_pass': not errors, 'image_count': len(checks),
            'errors': errors, 'files': checks,
            'not_verified': ['商品事实', '包装与文字保真', '画面满意度', '白底保护区外全部像素',
                             '商品轮廓与透明边缘', '渠道接受', '用户采用或真实发布']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('product', type=Path)
    ap.add_argument('--phase', choices=['first', 'full'], default='first')
    args = ap.parse_args()
    try:
        result = verify(args.product.resolve(), args.phase)
    except (ValueError, OSError, json.JSONDecodeError) as ex:
        result = {'file_checks_pass': False, 'errors': [str(ex)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['file_checks_pass'] else 1)


if __name__ == '__main__':
    main()
