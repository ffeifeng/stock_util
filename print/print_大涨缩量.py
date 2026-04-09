import json
from collections import defaultdict

with open(r'D:\soft\选股结果-大涨缩量回调MA5.json', encoding='utf-8') as f:
    d = json.load(f)

print(f'共 {d["total"]} 个信号  扫描范围：{d["scan_range"]}')
print(f'参数：{d["params"]}')
print()

def fmt_pct(v):
    if v is None: return '  -- '
    return f'{v:+.1f}%'

# 按信号日分组
by_date = defaultdict(list)
for s in d['signals']:
    sd = str(s['signal_date'])
    key = f'{sd[:4]}-{sd[4:6]}-{sd[6:]}'
    by_date[key].append(s)

total_win1 = total_win2 = total_win3 = 0
total_n = 0

for date in sorted(by_date.keys()):
    stocks = by_date[date]
    # 当天胜负统计
    w1 = sum(1 for s in stocks if s['fwd_1d_pct'] and s['fwd_1d_pct'] > 0)
    w2 = sum(1 for s in stocks if s['fwd_2d_pct'] and s['fwd_2d_pct'] > 0)
    w3 = sum(1 for s in stocks if s['fwd_3d_pct'] and s['fwd_3d_pct'] > 0)
    n  = len(stocks)
    total_win1 += w1; total_win2 += w2; total_win3 += w3; total_n += n

    print(f'{"="*72}')
    print(f'  {date}  共{n}只   1日胜率:{w1}/{n}={w1/n*100:.0f}%  2日:{w2}/{n}={w2/n*100:.0f}%  3日:{w3}/{n}={w3/n*100:.0f}%')
    print(f'{"="*72}')
    print(f'  {"代码":<10} {"大涨日":<12} {"涨%":>5} {"量x":>5} {"回调天":>4} {"回调%":>6} {"缩量":>5} {"信号收":>8}  {"1日":>6} {"2日":>6} {"3日":>6}')
    print(f'  {"-"*78}')

    for s in sorted(stocks, key=lambda x: -(x['fwd_1d_pct'] or -999)):
        bd = str(s['surge_date'])
        bd_fmt = f'{bd[:4]}-{bd[4:6]}-{bd[6:]}'
        f1 = fmt_pct(s['fwd_1d_pct'])
        f2 = fmt_pct(s['fwd_2d_pct'])
        f3 = fmt_pct(s['fwd_3d_pct'])
        win_mark = 'W' if s['fwd_1d_pct'] and s['fwd_1d_pct'] > 0 else 'L'
        print(f'  {s["code"]:<10} {bd_fmt:<12} {s["surge_pct"]:>4.0f}% {s["surge_vol_mult"]:>4.1f}x '
              f'{s["pullback_days"]:>4}天 {s["pb_low_pct"]:>5.1f}% {s["pb_vol_ratio"]:>5.2f}x '
              f'{s["signal_close"]:>8.2f}  {f1:>6} {f2:>6} {f3:>6}  {win_mark}')
    print()

print(f'{"="*72}')
print(f'  汇总胜率（次日开盘买 → N日收盘卖）')
print(f'  1日：{total_win1}/{total_n} = {total_win1/total_n*100:.1f}%')
print(f'  2日：{total_win2}/{total_n} = {total_win2/total_n*100:.1f}%')
print(f'  3日：{total_win3}/{total_n} = {total_win3/total_n*100:.1f}%')
print(f'{"="*72}')
