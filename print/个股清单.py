import json, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\soft\选股结果-大涨缩量回调MA5_无过滤.json', encoding='utf-8') as f:
    d = json.load(f)

# 去重：同一只股票同一次大涨只取第一次信号
seen = set()
unique = []
for s in sorted(d['signals'], key=lambda x: (x['surge_date'], x['signal_date'])):
    key = (s['code'], s['surge_date'])
    if key not in seen:
        seen.add(key)
        unique.append(s)

lines = []
lines.append(f'去重后共 {len(unique)} 只  (原始 {d["total"]} 个信号)')
lines.append('')

by_surge = defaultdict(list)
for s in unique:
    bd = str(s['surge_date'])
    by_surge[f'{bd[:4]}-{bd[4:6]}-{bd[6:]}'].append(s)

for surge_date in sorted(by_surge.keys()):
    stocks = by_surge[surge_date]
    lines.append(f'【大涨日 {surge_date}】 {len(stocks)}只')
    lines.append(f'  {"代码":<12} {"大涨%":>5} {"量倍":>5}  {"信号日":<12} {"回调":>3} {"回调%":>6} {"缩量":>5} {"收盘":>8}  {"1日%":>6} {"2日%":>6} {"3日%":>6}  结果')
    lines.append('  ' + '-'*85)
    for s in sorted(stocks, key=lambda x: -x['surge_pct']):
        sd = str(s['signal_date'])
        sd_fmt = f'{sd[:4]}-{sd[4:6]}-{sd[6:]}'
        f1 = f"{s['fwd_1d_pct']:>+5.1f}%" if s['fwd_1d_pct'] is not None else '    --'
        f2 = f"{s['fwd_2d_pct']:>+5.1f}%" if s['fwd_2d_pct'] is not None else '    --'
        f3 = f"{s['fwd_3d_pct']:>+5.1f}%" if s['fwd_3d_pct'] is not None else '    --'
        win = '涨' if s['fwd_1d_pct'] and s['fwd_1d_pct'] > 0 else '跌'
        lines.append(
            f'  {s["code"]:<12} {s["surge_pct"]:>4.0f}% {s["surge_vol_mult"]:>4.1f}x  '
            f'{sd_fmt:<12} {s["pullback_days"]:>2}天 {s["pb_low_pct"]:>5.1f}% '
            f'{s["pb_vol_ratio"]:>4.2f}x {s["signal_close"]:>8.2f}  '
            f'{f1} {f2} {f3}  {win}'
        )
    lines.append('')

lines.append('=' * 60)
lines.append('去重后胜率统计（每次大涨只算第一次信号）')
lines.append('=' * 60)
for n in [1, 2, 3]:
    key = f'fwd_{n}d_pct'
    valid = [s for s in unique if s[key] is not None]
    if not valid: continue
    win = sum(1 for s in valid if s[key] > 0)
    avg = sum(s[key] for s in valid) / len(valid)
    avg_w = sum(s[key] for s in valid if s[key] > 0) / max(win, 1)
    loss = [s for s in valid if s[key] <= 0]
    avg_l = sum(s[key] for s in loss) / max(len(loss), 1)
    lines.append(
        f'持有{n}日  总:{len(valid):>4}只  '
        f'胜率:{win/len(valid)*100:>5.1f}%({win}/{len(valid)})  '
        f'均值:{avg:>+6.2f}%  均盈:{avg_w:>+6.2f}%  均亏:{avg_l:>+6.2f}%'
    )

out = '\n'.join(lines)
path = r'd:\stock\个股清单输出.txt'
with open(path, 'w', encoding='utf-8') as f:
    f.write(out)
print(f'已写入: {path}')
