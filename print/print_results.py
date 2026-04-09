import json
with open(r'D:\soft\选股结果-起爆点.json', encoding='utf-8') as f:
    d = json.load(f)
print('扫描范围:', d['scan_range'])
print('扫描时间:', d['scan_time'])
print('共找到:', d['total_found'], '只')
print()
for s in d['stocks']:
    pt  = '【强势】' if s['pattern_type'] == 'strong' else '【稳健】'
    hold = '【守住突破价】' if s['hold_breakout_close'] else ''

    # 回踩信息
    if s['pullback_date']:
        pb_str = f"  回踩: {s['pullback_date']} 收{s['pullback_close']}"
        drop   = round((s['pullback_close'] - s['break_close']) / s['break_close'] * 100, 1)
        pb_str += f"（距突破价{drop:+.1f}%）"
    else:
        pb_str = '  回踩: 无数据'

    # 企稳信息
    if s['hold_breakout_close']:
        rs_str = '  企稳: 从未跌破突破价，持续强势'
    elif s['restable_date']:
        rs_str = f"  企稳: {s['restable_date']} 重回突破价以上"
    else:
        rs_str = '  企稳: 尚未企稳（仍在突破价以下）'

    print(f"{'─'*62}")
    print(f"  {s['rank']:2}. {s['code']}  评分{s['score']}  {pt}{hold}")
    print(f"  突破: {s['break_date']}  收盘{s['break_close']}  涨幅{s['break_pct']}%  "
          f"缩量{s['shrink_ratio']}  突破量比{s['break_vol_ratio']}")
    print(pb_str)
    print(rs_str)
print(f"{'─'*62}")
