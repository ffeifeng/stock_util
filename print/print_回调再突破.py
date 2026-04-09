import json, sys, os, glob
sys.stdout.reconfigure(encoding='utf-8')

# 自动找 output/ 目录下最新的回调再突破结果文件
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
files   = sorted(glob.glob(os.path.join(out_dir, '回调再突破_*.json')))
if not files:
    print('output/ 目录下没有找到回调再突破结果文件，请先运行 strategies/选股-回调再突破.py')
    sys.exit(1)
latest = files[-1]
print(f'读取：{os.path.basename(latest)}\n')
with open(latest, encoding='utf-8') as f:
    d = json.load(f)

p = d['params']
print(f'策略：{d["strategy"]}')
print(f'扫描区间：{d["scan_range"]}  共 {d["total_found"]} 只  扫描时间：{d["scan_time"]}')
print(f'参数：主升>={p["surge_min_pct"]}%  回调{p["pullback_min_pct"]}~{p["pullback_max_pct"]}%  '
      f'回调{p["pullback_min_days"]}~{p["pullback_max_days"]}天  缩量<{p["shrink_ratio"]}x  '
      f'斐波那契<{p["retrace_max"]*100:.1f}%')
print()

header = (f'  {"排":>2} {"代码":<12} {"评分":>6}  {"形态":<8} '
          f'{"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
          f'{"主升涨":>6}/{"天":>3}  {"回调幅":>6}/{"天":>3}  '
          f'{"斐波":>5} {"缩量":>5}  {"守突破":<5} {"回踩日":<12} {"企稳日":<12}')
print(header)
print('  ' + '-' * 115)

for s in d['stocks']:
    bull  = '多头' if s['bull_ma']    else '    '
    hold  = '守住' if s['hold_break'] else '跌破'
    fib   = f"{s['retrace_ratio']*100:.0f}%" if s['retrace_ratio'] else '  -'
    pb    = s['pullback_date']  or '   未回踩  '
    rs    = s['restable_date']  or ('—' if s['hold_break'] else '待企稳')
    line = (
        f"  {s['rank']:>2} {s['code']:<12} {s['score']:>6}  "
        f"[{bull}]  {s['break_date']:<12} {s['break_close']:>7.2f} {s['break_pct']:>+5.1f}%  "
        f"{s['surge_pct']:>5.0f}%/{s['surge_days']:>3}天  "
        f"{s['pb_pct']:>5.0f}%/{s['pullback_days']:>3}天  "
        f"{fib:>5} {s['shrink_ratio']:>5.2f}x  "
        f"{hold:<5} {pb:<12} {rs:<12}"
    )
    print(line)

print()
print('字段说明：主升涨=主升浪涨幅  回调幅=从峰值回调百分比  斐波=回撤占主升幅度的比例')
print('         缩量=回调期均量/主升期均量  守突破=突破后从未跌破突破日收盘价')
