import json, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open(r'D:\soft\选股结果-大涨缩量回调MA5.json', encoding='utf-8') as f:
    data = json.load(f)

signals = data['signals']

# 去重：每个 (code, surge_date) 只保留第一次信号
seen = set()
unique = []
for r in signals:
    key = (r['code'], r['surge_date'])
    if key not in seen:
        seen.add(key)
        unique.append(r)

# 按信号日分组
groups = defaultdict(list)
for r in unique:
    groups[r['signal_date']].append(r)

lines = []
lines.append(f'共 {len(unique)} 个唯一信号（去重后，每次大涨只取首次信号）')
p = data['params']
lines.append(f'参数：大涨>={p["surge_min_pct"]}%  量>={p["surge_vol_mult"]}x  '
             f'回调{p["pullback_days"]}天  缩量<{p["pullback_shrink"]}x  '
             f'信号日涨<{p.get("signal_max_pct","5")}%  回调须触碰MA5')
lines.append('')

for sig_date in sorted(groups.keys()):
    recs = groups[sig_date]
    sd = str(sig_date)
    lines.append(f'── {sd[:4]}-{sd[4:6]}-{sd[6:]}  ({len(recs)}只) {"─"*50}')
    for r in sorted(recs, key=lambda x: -x['surge_pct']):
        bd = str(r['surge_date'])
        f1 = f"{r['fwd_1d_pct']:>+6.1f}%" if r['fwd_1d_pct'] is not None else '    --'
        f2 = f"{r['fwd_2d_pct']:>+6.1f}%" if r['fwd_2d_pct'] is not None else '    --'
        f3 = f"{r['fwd_3d_pct']:>+6.1f}%" if r['fwd_3d_pct'] is not None else '    --'
        win1 = 'W' if r['fwd_1d_pct'] and r['fwd_1d_pct'] > 0 else 'L'
        sig_g = r.get('signal_day_gain', 0)
        lines.append(
            f"  {r['code']:<12} 大涨{bd[:4]}-{bd[4:6]}-{bd[6:]} {r['surge_pct']:>6.1f}%/{r['surge_vol_mult']:>4.1f}x  "
            f"回调{r['pullback_days']}天 {r['pb_low_pct']:>+6.1f}%  "
            f"信号涨{sig_g:>+5.1f}%  收{r['signal_close']:>9.2f}  "
            f"1d:{f1}({win1}) 2d:{f2} 3d:{f3}"
        )
    w = sum(1 for r in recs if r['fwd_1d_pct'] and r['fwd_1d_pct'] > 0)
    lines.append(f'  → 当日1日胜率 {w}/{len(recs)} = {w/len(recs)*100:.0f}%')
    lines.append('')

# 整体胜率
valid = [r for r in unique if r['fwd_1d_pct'] is not None]
win = sum(1 for r in valid if r['fwd_1d_pct'] > 0)
avg = sum(r['fwd_1d_pct'] for r in valid) / len(valid)
lines.append('=' * 70)
lines.append(f'总计唯一信号：{len(unique)}  有效1日数据：{len(valid)}  '
             f'1日胜率：{win/len(valid)*100:.1f}%({win}/{len(valid)})  平均：{avg:+.2f}%')

out = '\n'.join(lines)
with open(r'd:\stock\个股清单输出.txt', 'w', encoding='utf-8') as f:
    f.write(out)

print(f'完成！共 {len(unique)} 个唯一信号，已写入 d:\\stock\\个股清单输出.txt')
