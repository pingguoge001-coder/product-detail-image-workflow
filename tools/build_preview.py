"""按清单生成离线预览；只引用本品当前版本，不改变图片。"""
from pathlib import Path
import argparse
from datetime import date
from html import escape
from urllib.parse import quote
from common import load_delivery, safe_path


def build(root):
    data = load_delivery(root)
    groups = {'方形主图': [], '竖形主图': [], '基础素材': []}
    details = []
    roles = set()
    for row in data['images']:
        if row['role'] in roles:
            raise ValueError('清单有重复图位，请先明确当前版本')
        roles.add(row['role'])
        path = safe_path(root, row['path'])
        if not path.is_file():
            raise ValueError('清单引用文件不存在：' + row['path'])
        uri = quote(row['path'], safe='/')
        tag = f'<a href="{uri}" target="_blank"><img src="{uri}" alt="{escape(row["role"], quote=True)}"></a>'
        if row.get('type') in {'detail', 'report', 'introduction', 'disclaimer'}:
            details.append((row.get('order'), tag))
        elif row['role'].startswith('square'):
            groups['方形主图'].append(tag)
        elif row['role'].startswith('vertical'):
            groups['竖形主图'].append(tag)
        elif row['role'].startswith('basic_'):
            groups['基础素材'].append(tag)
        else:
            raise ValueError('未知图位或缺少详情type：' + row['role'])
    orders = [r[0] for r in details]
    if any(type(v) is not int for v in orders) or sorted(orders) != list(range(1, len(details) + 1)):
        raise ValueError('详情order必须从1连续且唯一')
    body = ''.join(f'<section><h2>{name}</h2><div class="grid">{"".join(tags)}</div></section>'
                   for name, tags in groups.items() if tags)
    sequence = ''.join(tag for _, tag in sorted(details))
    title = escape(str(data.get('product', '商品预览')))
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>商品图片预览</title><style>
body{margin:0;background:#f4f4f1;color:#202822;font:22px/1.7 system-ui,sans-serif}
header,section,footer{max-width:1100px;margin:24px auto;padding:20px}
h1{font-size:34px}h2{font-size:27px}p{margin:12px 0}.note{font-size:18px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.grid img{display:block;width:100%;height:auto}
.sequence{max-width:790px;margin:0 auto;line-height:0;background:white}
.sequence a,.sequence img{display:block;width:100%;height:auto;margin:0;padding:0;border:0}
@media(max-width:650px){body{font-size:20px}.grid{grid-template-columns:1fr}header,section,footer{padding:16px}}
@media print{body{background:white}header,section,footer{margin:0 auto}.grid{grid-template-columns:1fr 1fr}}
</style><header><h1>''' + title + '''</h1><p>''' + str(date.today()) + ''' · 待查看</p>
<p>本页显示当前清单所列图片。文件存在和预览可打开，不代表本人采用或平台通过。</p>
<p>实际图片：''' + str(len(data['images'])) + '''张；其中详情：''' + str(len(details)) + '''页。</p>
<p class="note"><a href="progress.md">进度与问题</a> · <a href="references.md">参考记录</a> · <a href="delivery.json">当前清单</a></p>
</header>''' + body + '''<section><h2>连续详情</h2><p>以下按清单顺序连续显示，点击任意图片打开原图。</p></section>
<div class="sequence">''' + sequence + '''</div><footer><p class="note">方案、提示词与核验回执保存在本品工作目录。待处理问题见进度记录。</p></footer></html>'''
    target = root / 'preview.html'
    version = 2
    while target.exists():
        target = root / f'preview-v{version}.html'
        version += 1
    target.write_text(html, encoding='utf-8')
    return target


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('product', type=Path)
    args = ap.parse_args()
    try:
        print(build(args.product.resolve()))
    except (ValueError, OSError) as ex:
        ap.exit(1, str(ex) + '\n')
