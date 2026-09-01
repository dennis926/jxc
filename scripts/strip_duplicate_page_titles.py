"""清除页内与顶栏重复的 h4 标题

背景
----
base.html 顶栏已通过 app.py 的 PAGE_TITLES 自动显示精确的页面标题，
但各业务模板在内容区顶部还各自写了一个 <h4>标题</h4>，形成上下重复。

难点
----
这些 h4 通常位于 `<div class="d-flex justify-content-between align-items-center mb-4">`
容器内，与右侧操作按钮并排。若只删 h4，flex 容器里只剩按钮组，
justify-content-between 会让按钮塌到左边，破坏原有右对齐布局。

处理策略
--------
1. h4 独占一行、且所在 flex 容器内还有其它兄弟元素（按钮组）
   -> 删除 h4，并把容器的 justify-content-between 改为 flex-end，保持按钮右对齐
2. h4 独占一行、容器内没有其它内容
   -> 连同空的 flex 容器一起删除
3. h4 不是页面主标题（如统计数字 <h4>{{ total }}</h4>、打印单据内的居中标题）
   -> 跳过，不动

只处理"内容区第一屏的模块主标题"，判定条件：
- h4 出现在 {% block content %} 之后 25 行内
- h4 内部文本是静态中文标题（不含 Jinja 表达式 {{ }}）

用法
----
    python scripts/strip_duplicate_page_titles.py --dry-run   # 预览
    python scripts/strip_duplicate_page_titles.py             # 实际执行
"""

import argparse
import re
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'templates'

# 这些目录/文件不处理：
#   errors/  独立错误页，标题是页面主体内容
#   *print*  打印单据，居中标题是单据正式抬头，必须保留
SKIP_PATTERNS = ('errors/', 'print_', '/print')

# 单行 h4 主标题：<h4 ...>[图标]静态文本</h4>
H4_LINE = re.compile(
    r'^(?P<indent>\s*)<h4(?P<attrs>[^>]*)>'
    r'(?P<inner>(?:\s*<i[^>]*></i>)?\s*[^<{}]+?)'
    r'</h4>\s*$'
)

FLEX_BETWEEN = 'justify-content-between'


def is_main_title(inner: str) -> bool:
    """判断 h4 内容是否为静态页面主标题（排除数据展示用的 h4）"""
    text = re.sub(r'<[^>]+>', '', inner).strip()
    if not text:
        return False
    # 含 Jinja 表达式的是数据，不是标题
    if '{{' in inner or '{%' in inner:
        return False
    # 纯数字/符号（如 +2858、32.07）不是标题
    if re.fullmatch(r'[\d\s+\-.,:%¥]+', text):
        return False
    # 主标题应含中文
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def find_content_block(lines):
    """返回 {% block content %} 所在行号，找不到返回 None"""
    for i, line in enumerate(lines):
        if 'block content' in line and '{%' in line:
            return i
    return None


def process(path: Path, dry_run: bool):
    rel = str(path.relative_to(TEMPLATES_DIR))
    if any(p in rel or p in path.name for p in SKIP_PATTERNS):
        return None

    original = path.read_text(encoding='utf-8')
    lines = original.split('\n')

    start = find_content_block(lines)
    if start is None:
        return None

    # 只在 content 块开头附近寻找主标题
    for idx in range(start, min(start + 25, len(lines))):
        m = H4_LINE.match(lines[idx])
        if not m or not is_main_title(m.group('inner')):
            continue

        title_text = re.sub(r'<[^>]+>', '', m.group('inner')).strip()

        # 向上找包裹它的 flex 容器（最多回溯 3 行）
        wrapper_idx = None
        for back in range(1, 4):
            j = idx - back
            if j < start:
                break
            if '<div' in lines[j] and 'd-flex' in lines[j]:
                wrapper_idx = j
                break

        new_lines = list(lines)

        if wrapper_idx is None:
            # 裸 h4，直接删除该行
            del new_lines[idx]
            action = f'删除裸标题'
        else:
            # 找容器结束的 </div>，判断容器内除 h4 外还有无内容
            depth = 0
            end_idx = None
            for k in range(wrapper_idx, len(new_lines)):
                depth += new_lines[k].count('<div')
                depth -= new_lines[k].count('</div>')
                if depth <= 0 and k > wrapper_idx:
                    end_idx = k
                    break
            if end_idx is None:
                continue

            body = [new_lines[k] for k in range(wrapper_idx + 1, end_idx) if k != idx]
            has_siblings = any(s.strip() for s in body)

            if has_siblings:
                # 保留容器，删标题，按钮组改为右对齐
                del new_lines[idx]
                w = new_lines[wrapper_idx]
                if FLEX_BETWEEN in w:
                    new_lines[wrapper_idx] = w.replace(FLEX_BETWEEN, 'justify-content-end')
                action = '删标题并改为右对齐'
            else:
                # 容器内只有标题，整块删掉
                del new_lines[wrapper_idx:end_idx + 1]
                action = '删除标题及空容器'

        new_text = '\n'.join(new_lines)
        if new_text != original and not dry_run:
            path.write_text(new_text, encoding='utf-8')
        return (rel, title_text, action)

    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='只预览不写入')
    args = ap.parse_args()

    results = []
    for path in sorted(TEMPLATES_DIR.rglob('*.html')):
        r = process(path, args.dry_run)
        if r:
            results.append(r)

    mode = '预览' if args.dry_run else '已修改'
    print(f'{mode} {len(results)} 个模板\n')
    for rel, title, action in results:
        print(f'  {rel:45s} 「{title}」  {action}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
