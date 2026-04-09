"""深度分析 603693 和 002923 的形态特征，辅助优化脚本逻辑"""
import struct, os, sys
sys.stdout.reconfigure(encoding='utf-8')

TARGETS = [
    ('sh', '603693'),
    ('sz', '002923'),
]
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

def read_day_file(filepath):
    records = []
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': open_/100, 'high': high/100,
                                 'low': low/100, 'close': close/100, 'volume': volume})
    except Exception:
        pass
    return records

def calc_ma(values, n):
    return [None if i < n-1 else round(sum(values[i-n+1:i+1])/n, 3) for i in range(len(values))]

def fmt(d):
    s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

for market, num in TARGETS:
    code = f'{market}{num}'
    records = read_day_file(os.path.join(DATA_DIRS[market], f'{code}.day'))
    closes  = [r['close']  for r in records]
    volumes = [r['volume'] for r in records]
    ma5  = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    ma30 = calc_ma(closes, 30)
    ma60 = calc_ma(closes, 60)

    # 找突破日（收盘首次从MA30下方穿越上方）
    bi = -1
    for i in range(1, len(records)):
        if ma30[i] and ma30[i-1]:
            if records[i-1]['close'] <= ma30[i-1] and records[i]['close'] > ma30[i]:
                if records[i]['date'] >= 20260201:   # 只看近期
                    bi = i
                    break

    if bi < 0:
        print(f'\n{code}: 近期未找到突破日')
        continue

    break_date  = records[bi]['date']
    break_close = records[bi]['close']
    break_ma30  = ma30[bi]

    # ── 洗盘期分析 ──
    wash_end   = bi - 1
    wash_start = max(0, bi - 88)
    wash_records = records[wash_start:wash_end+1]
    wash_closes  = [r['close'] for r in wash_records]
    wash_volumes = [r['volume'] for r in wash_records]
    wash_days    = len(wash_records)
    wash_high    = max(wash_closes)
    wash_low     = min(wash_closes)
    wash_range   = (wash_high - wash_low) / wash_low * 100

    # MA收敛度：洗盘期内 MA5 与 MA30 的平均偏差
    ma_diffs = []
    for j in range(wash_start, wash_end+1):
        if ma5[j] and ma30[j]:
            ma_diffs.append(abs(ma5[j] - ma30[j]) / ma30[j] * 100)
    ma_convergence = sum(ma_diffs)/len(ma_diffs) if ma_diffs else 999

    # 突破前连续跌破MA30的天数
    below_days = 0
    for k in range(1, 5):
        idx = bi - k
        if idx < 0 or not ma30[idx]: break
        if records[idx]['close'] < ma30[idx]:
            below_days += 1
        else:
            break

    # 突破日成交量 vs 洗盘均量
    avg_wash_vol  = sum(wash_volumes)/len(wash_volumes) if wash_volumes else 1
    break_vol_mult = volumes[bi] / avg_wash_vol

    # ── 建仓期分析 ──
    pull_end    = wash_start
    pull_start  = max(0, pull_end - 120)
    pull_records = records[pull_start:pull_end+1]
    pull_closes  = [r['close'] for r in pull_records]
    pull_volumes = [r['volume'] for r in pull_records]
    pull_low  = min(pull_closes)
    pull_high = max(pull_closes)
    surge_pct = (pull_high - pull_low) / pull_low * 100
    avg_pull_vol  = sum(pull_volumes)/len(pull_volumes) if pull_volumes else 1
    shrink_ratio  = avg_wash_vol / avg_pull_vol

    # 突破后状态
    post_records = records[bi+1:]
    hold = all(r['close'] >= break_close for r in post_records)
    post_high = max(r['close'] for r in post_records) if post_records else break_close
    post_gain = (post_high - break_close) / break_close * 100

    print(f'\n{"="*62}')
    print(f'  {code}   突破日：{fmt(break_date)}')
    print(f'{"="*62}')
    print(f'  突破收盘：{break_close:.2f}  突破时MA30：{break_ma30:.2f}  超MA30：{(break_close-break_ma30)/break_ma30*100:+.1f}%')
    print(f'  突破前连续跌破MA30：{below_days} 天  → 形态类型：{"强势型" if below_days==1 else ("稳健型" if below_days==0 else "偏弱")}')
    print()
    print(f'  【洗盘期】{fmt(wash_records[0]["date"])} ～ {fmt(wash_records[-1]["date"])}  共 {wash_days} 个交易日')
    print(f'    价格区间：{wash_low:.2f} ～ {wash_high:.2f}   振幅：{wash_range:.1f}%')
    print(f'    MA收敛度（MA5与MA30平均偏差）：{ma_convergence:.2f}%   {"★极度收敛" if ma_convergence < 1.0 else ("好" if ma_convergence < 2.0 else "一般")}')
    print(f'    洗盘均量 vs 建仓均量（缩量比）：{shrink_ratio:.2f}x')
    print(f'    突破日量能 vs 洗盘均量：{break_vol_mult:.1f}x')
    print()
    print(f'  【建仓期】{fmt(pull_records[0]["date"])} ～ {fmt(pull_records[-1]["date"])}  共 {len(pull_records)} 个交易日')
    print(f'    建仓区涨幅（低→高）：{surge_pct:.1f}%')
    print()
    print(f'  【突破后表现】守住突破价：{"是" if hold else "否"}   最高涨幅：{post_gain:.1f}%')
    print(f'    (截至 {fmt(records[-1]["date"])} 收盘 {records[-1]["close"]:.2f})')
