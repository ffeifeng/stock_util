import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'D:\soft\选股结果-回调再突破.json', encoding='utf-8') as f:
    d = json.load(f)
for s in d['stocks']:
    if s['code'] in ['sz002923', 'sh002923']:
        print(f'排名 {s["rank"]}  评分 {s["score"]}')
        print(f'主升浪：{s["base_date"]} {s["base_close"]} -> {s["peak_date"]} {s["peak_close"]}  涨{s["surge_pct"]}%/{s["surge_days"]}天')
        print(f'回调：  峰值{s["peak_close"]} -> 低点{s["pb_date"]} {s["pb_close"]}  回调{s["pb_pct"]}%/{s["pullback_days"]}天')
        print(f'斐波回撤：{s["retrace_ratio"]*100:.1f}%  缩量比：{s["shrink_ratio"]}x')
        print(f'突破日：{s["break_date"]}  收{s["break_close"]}  超MA30 {s["break_pct"]:+.1f}%')
        print(f'多头排列：{s["bull_ma"]}  守住突破价：{s["hold_break"]}')
