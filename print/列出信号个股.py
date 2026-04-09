"""列出所有信号个股，去重后按大涨日排序，方便人工审查"""
import json
from collections import defaultdict

with open(r'D:\soft\选股结果-大涨缩量回调MA5_无过滤.json', encoding='utf-8') as f:
    d = json.load(f)

signals = d['signals']

# ── 按大涨日 + 股票代码去重（同一次大涨只看第一次信号）────────────────────────
seen = set()
unique = []
for s in sorted(signals, key=lambda x: (x['surge_date'], x['signal_date'])):
    key = (s['code'], s['surge_date'])
    if key not in seen:
        seen.add(key)
        unique.append(s)

print(f'原始信号 {len(signals)} 个  →  去重后（每次大涨只算一次）{len(unique)} 只')
print()

# ── 按大涨日分组显示 ─────────────────────────────────────────────────────────
by_surge = defaultdict(list)
for s in unique:
    bd = str(s['surge_date'])
    by_surge[bd].append(s)

for surge_date in sorted(by_surge.keys()):
    stocks = by_surge[surge_date]
    bd_fmt = f'{surge_date[:4]}-{surge_date[4:6]}-{surge_date[6:]}'
    print(f'{"="*72}')
    print(f'  大涨日：{bd_fmt}  共 {len(stocks)} 只')
    print(f'{"="*72}')
    print(f'  {"代码":<12} {"涨幅%":>6} {"量倍":>6} {"信号日":>12} {"回调天":>5} '
          f'{"回调%":>7} {"缩量比":>6} {"信号收":>8}  {"1日%":>6} {"2日%":>6} {"3日%":>6}')
    print(f'  {"-"*84}')
    for s in sorted(stocks, key=lambda x: -x['surge_pct']):
        sd = str(s['signal_date'])
        sd_fmt = f'{sd[:4]}-{sd[4:6]}-{sd[6:]}'
        f1 = f"{s['fwd_1d_pct']:>+5.1f}%" if s['fwd_1d_pct'] is not None else '    --'
        f2 = f"{s['fwd_2d_pct']:>+5.1f}%" if s['fwd_2d_pct'] is not None else '    --'
        f3 = f"{s['fwd_3d_pct']:>+5.1f}%" if s['fwd_3d_pct'] is not None else '    --'
        win = 'W' if s['fwd_1d_pct'] and s['fwd_1d_pct'] > 0 else 'L'
        print(f'  {s["code"]:<12} {s["surge_pct"]:>5.0f}% {s["surge_vol_mult"]:>5.1f}x '
              f'{sd_fmt:>12} {s["pullback_days"]:>4}天 {s["pb_low_pct"]:>6.1f}% '
              f'{s["pb_vol_ratio"]:>5.2f}x {s["signal_close"]:>8.2f}  '
              f'{f1} {f2} {f3}  {win}')
    print()

# ── 去重后胜率统计 ────────────────────────────────────────────────────────────
print(f'{"="*60}')
print(f'  去重后胜率统计（每次大涨只算第一次信号）')
print(f'{"="*60}')
for n in [1, 2, 3]:
    key = f'fwd_{n}d_pct'
    valid = [s for s in unique if s[key] is not None]
    if not valid: continue
    win = sum(1 for s in valid if s[key] > 0)
    avg = sum(s[key] for s in valid) / len(valid)
    avg_w = sum(s[key] for s in valid if s[key] > 0) / max(win, 1)
    loss = [s for s in valid if s[key] <= 0]
    avg_l = sum(s[key] for s in loss) / max(len(loss), 1)
    print(f'  持有{n}日  总:{len(valid):>4}  胜率:{win/len(valid)*100:>5.1f}%({win}/{len(valid)})  '
          f'均值:{avg:>+6.2f}%  均盈:{avg_w:>+6.2f}%  均亏:{avg_l:>+6.2f}%')
print(f'{"="*60}')
