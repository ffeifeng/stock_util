"""完整复盘 002826 的主力建仓/洗盘/突破形态"""
import struct, sys
sys.stdout.reconfigure(encoding='utf-8')

def read_day_file(filepath):
    records = []
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, open_, high, low, close, amount, volume, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': open_/100, 'high': high/100,
                             'low': low/100, 'close': close/100, 'volume': volume})
    return records

def calc_ma(values, n):
    return [None if i < n-1 else round(sum(values[i-n+1:i+1])/n, 3)
            for i in range(len(values))]

def fmt(d):
    s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

records = read_day_file(r'D:\soft\new_tdx\vipdoc\sz\lday\sz002826.day')
closes  = [r['close'] for r in records]
volumes = [r['volume'] for r in records]
ma5  = calc_ma(closes, 5)
ma10 = calc_ma(closes, 10)
ma20 = calc_ma(closes, 20)
ma30 = calc_ma(closes, 30)
ma60 = calc_ma(closes, 60)

# 用户买入日
BUY_DATE  = 20260129
BUY_PRICE = 18.73

# 找买入日索引
bi = next(i for i, r in enumerate(records) if r['date'] == BUY_DATE)

# ── 打印三个阶段 ──────────────────────────────────────────────
print('=' * 78)
print(f'  sz002826  买入日：{fmt(BUY_DATE)}  买入价（收盘）：{BUY_PRICE}')
print('=' * 78)

def print_section(title, start, end, highlight_date=None, note=''):
    print(f'\n【{title}】{note}')
    print(f'  {"日期":<12} {"开":>7} {"高":>7} {"低":>7} {"收":>7}  {"MA5":>7} {"MA20":>7} {"MA30":>7} {"MA60":>7}  {"量(万手)":>8}  备注')
    print(f'  {"-"*100}')
    for i in range(start, end+1):
        r = records[i]
        flag = ''
        if ma30[i] and r['close'] < ma30[i]:
            flag = '↓MA30'
        elif ma30[i] and i > 0 and ma30[i-1] and records[i-1]['close'] < ma30[i-1] and r['close'] > ma30[i]:
            flag = '★回踩后站上'
        if r['date'] == BUY_DATE:
            flag += '  ← 买入日'
        # 量能标注
        vol_w = r['volume'] / 10000
        if i >= 10:
            avg10 = sum(volumes[i-10:i]) / 10
            vol_mult = r['volume'] / avg10 if avg10 > 0 else 1
            if vol_mult >= 2.5:
                flag += f'  🔥放量{vol_mult:.1f}x'
            elif vol_mult <= 0.5:
                flag += f'  📉缩量{vol_mult:.1f}x'
        m5  = f'{ma5[i]:>7.2f}'  if ma5[i]  else '      -'
        m20 = f'{ma20[i]:>7.2f}' if ma20[i] else '      -'
        m30 = f'{ma30[i]:>7.2f}' if ma30[i] else '      -'
        m60 = f'{ma60[i]:>7.2f}' if ma60[i] else '      -'
        print(f'  {fmt(r["date"]):<12} {r["open"]:>7.2f} {r["high"]:>7.2f} {r["low"]:>7.2f} {r["close"]:>7.2f}  {m5} {m20} {m30} {m60}  {vol_w:>8.1f}  {flag}')

# 阶段1：主力建仓期（买入前约90天）
build_start = max(0, bi - 90)
build_mid   = max(0, bi - 45)
print_section('主力建仓 & 洗盘全景（买入前90天）', build_start, bi,
              note=f'  {fmt(records[build_start]["date"])} ~ {fmt(records[bi]["date"])}')

# 阶段2：突破后的走势
print_section('突破后走势（买入后至今）', bi, len(records)-1,
              note=f'  {fmt(records[bi]["date"])} ~ {fmt(records[-1]["date"])}')

# 阶段总结
last = records[-1]
li   = len(records) - 1
gain = (last['close'] - BUY_PRICE) / BUY_PRICE * 100
peak_after = max(r['close'] for r in records[bi:])
peak_gain  = (peak_after - BUY_PRICE) / BUY_PRICE * 100

# MA收敛分析（买入日前30天）
wash_start = max(0, bi - 60)
wash_end   = bi
ma_diffs = [abs(ma5[j] - ma30[j]) / ma30[j] * 100
            for j in range(wash_start, wash_end+1)
            if ma5[j] and ma30[j]]
avg_convergence = sum(ma_diffs)/len(ma_diffs) if ma_diffs else 0

# 洗盘期量能 vs 前期
wash_vols = volumes[wash_start:wash_end+1]
pre_start = max(0, wash_start - 60)
pre_vols  = volumes[pre_start:wash_start]
shrink    = (sum(wash_vols)/len(wash_vols)) / (sum(pre_vols)/len(pre_vols)) if pre_vols else 1

print(f'\n{"="*78}')
print(f'  复盘总结')
print(f'{"="*78}')
print(f'  买入日：{fmt(BUY_DATE)}  买入价：{BUY_PRICE}')
print(f'  当前收盘（{fmt(last["date"])}）：{last["close"]}  持仓收益：{gain:+.1f}%')
print(f'  买入后最高价：{peak_after:.2f}  最大浮盈：{peak_gain:+.1f}%')
print()
print(f'  【洗盘质量】（买入前60天）')
print(f'    MA收敛度（MA5与MA30平均偏差）：{avg_convergence:.2f}%  {"★极优" if avg_convergence < 1.5 else ("优" if avg_convergence < 3 else "一般")}')
print(f'    洗盘缩量比（vs前期）：{shrink:.2f}x  {"★缩量明显" if shrink < 0.6 else ("缩量" if shrink < 0.8 else "一般")}')
print(f'    买入日MA结构：MA5={ma5[bi]:.2f}  MA20={ma20[bi]:.2f}  MA30={ma30[bi]:.2f}  MA60={ma60[bi]:.2f}')
ma_spread = (max(ma5[bi], ma20[bi], ma30[bi], ma60[bi]) -
             min(ma5[bi], ma20[bi], ma30[bi], ma60[bi]))
print(f'    四线最大差值：{ma_spread:.2f}元 ({ma_spread/ma30[bi]*100:.1f}%)  {"★粘合极佳" if ma_spread/ma30[bi] < 0.02 else ("粘合" if ma_spread/ma30[bi] < 0.04 else "一般")}')
print()
print(f'  【买入信号特征】')
prev = records[bi-1]
print(f'    前一日：{fmt(prev["date"])}  收{prev["close"]:.2f}  MA30={ma30[bi-1]:.2f}  {"跌破MA30" if prev["close"] < ma30[bi-1] else "在MA30上"}')
print(f'    买入日：{fmt(records[bi]["date"])}  收{records[bi]["close"]:.2f}  MA30={ma30[bi]:.2f}  站上MA30：{"是" if records[bi]["close"] > ma30[bi] else "否"}')
print(f'    形态识别：{"强势型（前日跌破MA30，当日立即站回）" if prev["close"] < ma30[bi-1] and records[bi]["close"] > ma30[bi] else "稳健型（持续在MA30上方）"}')
