import json, sys, os, glob
sys.stdout.reconfigure(encoding='utf-8')

# 自动找 output/ 目录下最新的起爆点结果文件
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
files   = sorted(glob.glob(os.path.join(out_dir, '起爆点_*.json')))
if not files:
    print('output/ 目录下没有找到起爆点结果文件，请先运行 strategies/选股-起爆点分析.py')
    sys.exit(1)
latest = files[-1]
print(f'读取：{os.path.basename(latest)}\n')
with open(latest, encoding='utf-8') as f:
    d = json.load(f)

print(f'扫描区间：{d["scan_range"]}  共 {d["total_found"]} 只  扫描时间：{d["scan_time"]}')
print()
header = (f'  {"排":>2} {"代码":<12} {"评分":>6}  {"形态":<6} {"突破日":<12} {"突破价":>7} {"超MA30":>6}  '
          f'{"洗盘天":>5} {"建仓涨":>6} {"缩量":>5}  {"粘合度":>6}  {"守突破价":<5} {"回踩日":<12} {"企稳日":<12}')
print(header)
print('  ' + '-' * 120)

for s in d['stocks']:
    ptype  = '强势' if s['pattern_type'] == 'strong' else '稳健'
    hold   = '守住' if s['hold_breakout_close'] else '跌破'
    pb     = s['pullback_date'] or '   未回踩  '
    rs     = s['restable_date'] or ('—' if s['hold_breakout_close'] else '待企稳')
    mc     = s.get('ma_convergence', 99)
    mc_str = f'{mc:.1f}%{"★" if mc < 2 else ("+" if mc < 3.5 else "")}'
    line = (
        f"  {s['rank']:>2} {s['code']:<12} {s['score']:>6}  "
        f"[{ptype}]  {s['break_date']:<12} {s['break_close']:>7.2f} {s['break_pct']:>+5.1f}%  "
        f"{s['wash_days']:>4}天 {s['surge_pct']:>+6.1f}% {s['shrink_ratio']:>5.2f}x  "
        f"{mc_str:>7}  {hold:<5} {pb:<12} {rs:<12}"
    )
    print(line)

print()
print('字段说明：突破价=突破MA30当日收盘  超MA30=收盘偏离MA30百分比  洗盘天=洗盘期交易日数')
print('         建仓涨=建仓阶段涨幅  缩量=洗盘均量/建仓均量(越小越好)')
print('         粘合度=洗盘期MA5/MA20/MA30/MA60四线平均离散度  ★<2%极致粘合  +<3.5%优质')
print('         守突破价=突破后从未跌破突破日收盘')
