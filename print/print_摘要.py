"""打印两个策略前20名详细摘要，写入 output/摘要_日期.txt"""
import json, sys, os, glob
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')

def latest(prefix):
    files = sorted(glob.glob(os.path.join(OUT_DIR, f'{prefix}_*.json')))
    return files[-1] if files else None

def load(prefix):
    f = latest(prefix)
    if not f:
        return None, None
    with open(f, encoding='utf-8') as fh:
        return json.load(fh), os.path.basename(f)

lines = []

def add(s=''):
    lines.append(s)
    print(s)

# ── 起爆点 Top20 ──────────────────────────────────────────────
data1, fname1 = load('起爆点')
if data1:
    stocks = data1['stocks'][:20]
    add('=' * 80)
    add(f'【起爆点分析】Top {len(stocks)}   来源：{fname1}')
    add(f'扫描区间：{data1["scan_range"]}  共找到：{data1["total_found"]} 只  '
        f'扫描时间：{data1["scan_time"]}')
    add('=' * 80)
    add(f'  {"排":>2}  {"代码":<10} {"评分":>5}  {"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
        f'{"洗盘":>4} {"建仓涨":>6} {"缩量":>5}  {"粘合":>5}  {"状态":<6}  {"回踩→企稳"}')
    add('  ' + '─' * 78)
    for s in stocks:
        hold  = '✓守住' if s['hold_breakout_close'] else '跌破'
        mc    = s.get('ma_convergence', 99)
        mc_s  = f'{mc:.1f}%{"★" if mc < 2 else ("+" if mc < 3.5 else " ")}'
        ptype = '强' if s['pattern_type'] == 'strong' else '稳'

        if s['hold_breakout_close']:
            trail = '未回踩（强势上行）'
        elif s['restable_date']:
            trail = f'回踩{s["pullback_date"][5:]}→企稳{s["restable_date"][5:]}'
        elif s['pullback_date']:
            trail = f'回踩{s["pullback_date"][5:]}→待企稳'
        else:
            trail = '—'

        add(
            f'  {s["rank"]:>2}  {s["code"]:<10} {s["score"]:>5}  '
            f'{s["break_date"]:<12} {s["break_close"]:>7.2f} {s["break_pct"]:>+5.1f}%  '
            f'{s["wash_days"]:>3}天 {s["surge_pct"]:>+5.0f}% {s["shrink_ratio"]:>5.2f}x  '
            f'{mc_s:>6}  [{ptype}]{hold:<6}  {trail}'
        )
    add()
    add('  粘合度★<2%极致 +<3.5%优质  缩量=洗盘均量/建仓均量  超MA30=突破日收盘偏离MA30')
    add()

# ── 回调再突破 Top20 ──────────────────────────────────────────
data2, fname2 = load('回调再突破')
if data2:
    stocks = data2['stocks'][:20]
    add('=' * 80)
    add(f'【回调再突破】Top {len(stocks)}   来源：{fname2}')
    p = data2['params']
    add(f'扫描区间：{data2["scan_range"]}  共找到：{data2["total_found"]} 只  '
        f'扫描时间：{data2["scan_time"]}')
    add('=' * 80)
    add(f'  {"排":>2}  {"代码":<10} {"评分":>5}  {"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
        f'{"主升涨":>6}/{"天":>2}  {"回调":>5}/{"天":>2}  {"斐波":>5} {"缩量":>5}  {"状态":<6}  {"回踩→企稳"}')
    add('  ' + '─' * 88)
    for s in stocks:
        hold  = '✓守住' if s['hold_break'] else '跌破'
        bull  = '多头' if s['bull_ma'] else '    '
        fib   = f"{s['retrace_ratio']*100:.0f}%" if s['retrace_ratio'] else '  -'

        if s['hold_break']:
            trail = '未回踩（强势上行）'
        elif s['restable_date']:
            trail = f'回踩{s["pullback_date"][5:]}→企稳{s["restable_date"][5:]}'
        elif s['pullback_date']:
            trail = f'回踩{s["pullback_date"][5:]}→待企稳'
        else:
            trail = '—'

        add(
            f'  {s["rank"]:>2}  {s["code"]:<10} {s["score"]:>5}  '
            f'{s["break_date"]:<12} {s["break_close"]:>7.2f} {s["break_pct"]:>+5.1f}%  '
            f'{s["surge_pct"]:>5.0f}%/{s["surge_days"]:>2}天  '
            f'{s["pb_pct"]:>4.0f}%/{s["pullback_days"]:>2}天  '
            f'{fib:>5} {s["shrink_ratio"]:>5.2f}x  '
            f'[{bull}]{hold:<6}  {trail}'
        )
    add()
    add('  主升涨=建仓起点到峰值涨幅  回调=从峰值回落幅度  斐波=回调占主升的比例')
    add('  缩量=回调期均量/主升期均量  多头=突破日MA5>MA20>MA60')
    add()

# 写文件
ts       = datetime.now().strftime('%Y%m%d_%H%M')
out_path = os.path.join(OUT_DIR, f'摘要_{ts}.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'\n已写入：{out_path}')
