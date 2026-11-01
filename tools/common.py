"""清单读取和路径保护；不读取商品目录之外的素材。"""
from pathlib import Path, PureWindowsPath
import json


def safe_path(root, value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('path 必须是非空、正斜线分隔的相对路径')
    p = Path(value)
    if p.is_absolute() or PureWindowsPath(value).drive:
        raise ValueError('不接受绝对路径')
    target = (root / p).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('路径超出本品目录')
    return target


def load_delivery(root):
    data = json.loads((root / 'delivery.json').read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not isinstance(data.get('images'), list):
        raise ValueError('delivery.json 必须包含 images 数组')
    if not isinstance(data.get('plan'), dict):
        raise ValueError('缺少 plan 对象')
    for row in data['images']:
        if not isinstance(row, dict) or not isinstance(row.get('role'), str):
            raise ValueError('每行必须包含 role 和 path')
        safe_path(root, row.get('path'))
    return data
