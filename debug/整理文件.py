"""整理 d:\stock 目录下的文件到子文件夹"""
import os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'd:\stock'

# ── 文件分类规则 ──────────────────────────────────────────────
# 格式：目标文件夹名 -> [文件名列表]
LAYOUT = {
    '选股策略': [
        '选股-大涨缩量回调MA5.py',
        '选股-回调再突破.py',
        '选股-主力建仓洗盘突破.py',
        '选股-突破30日均线.py',
        '选股-突破30日均线V2.py',
        '选股-起爆点分析.py',
    ],
    '打印工具': [
        'print_results.py',
        'print_回调再突破.py',
        'print_大涨缩量.py',
        'print_起爆点.py',
        '生成清单.py',
        '列出信号个股.py',
    ],
    '调试分析': [
        'kline_check2.py',
        'kline_detail.py',
        '查个股状态.py',
        '分析形态差异.py',
        '复盘002826.py',
        '查002923排名.py',
        '调试002923.py',
        '调试起爆点002826.py',
    ],
    '输出结果': [
        'MA5止损回测结果.txt',
        'MA5止损回测结果_1月.txt',
        '个股清单输出.txt',
        '选股结果-起爆点.json',
    ],
}

# 根目录保留的文件（不移动）
KEEP_IN_ROOT = {'README.md', '整理文件.py'}

moved   = []
missing = []
skipped = []

for folder, files in LAYOUT.items():
    target_dir = os.path.join(ROOT, folder)
    os.makedirs(target_dir, exist_ok=True)
    for fname in files:
        src = os.path.join(ROOT, fname)
        dst = os.path.join(target_dir, fname)
        if os.path.exists(src):
            shutil.move(src, dst)
            moved.append(f'  {fname}  →  {folder}/')
        elif os.path.exists(dst):
            skipped.append(f'  {fname}  （已在 {folder}/，跳过）')
        else:
            missing.append(f'  {fname}  （未找到）')

print('=' * 60)
print(f'  整理完成！')
print('=' * 60)
print(f'\n✓ 已移动 {len(moved)} 个文件：')
for m in moved: print(m)

if skipped:
    print(f'\n→ 已跳过 {len(skipped)} 个（已在目标位置）：')
    for s in skipped: print(s)

if missing:
    print(f'\n✗ 未找到 {len(missing)} 个：')
    for m in missing: print(m)

# 列出整理后根目录的文件
print(f'\n── 根目录剩余文件 ──')
for f in sorted(os.listdir(ROOT)):
    full = os.path.join(ROOT, f)
    tag = '[文件夹]' if os.path.isdir(full) else '[文件]'
    print(f'  {tag}  {f}')
