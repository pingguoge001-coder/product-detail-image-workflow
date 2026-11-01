"""从空白模板创建本品目录；存在目标时拒绝覆盖。"""
from pathlib import Path
import argparse
import json
import re
import shutil


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--slug', required=True)
    ap.add_argument('--name', required=True)
    args = ap.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,23}', args.slug):
        ap.error('slug 用1—24位小写字母、数字和连接号，开头为字母或数字')
    target = args.root.resolve() / args.slug
    if target.exists():
        ap.error('目标已存在，拒绝覆盖')
    template = Path(__file__).resolve().parents[1] / 'templates' / 'product'
    shutil.copytree(template, target)
    for folder in ('source', '对标图片', 'prompts', 'plans', 'receipts',
                   'output/square', 'output/vertical', 'output/details',
                   'output/basic', 'output/originals', 'output/history'):
        (target / folder).mkdir(parents=True, exist_ok=True)
    data = json.loads((target / 'delivery.json').read_text(encoding='utf-8'))
    data['product'] = args.name
    (target / 'delivery.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'created': str(target), 'next': '填写 facts.md、references.md 与本轮停止点'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
