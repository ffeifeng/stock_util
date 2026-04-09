import struct, os

path = r'D:\soft\new_tdx\vipdoc\sh\lday\sh605218.day'
records = []
with open(path, 'rb') as f:
    while True:
        chunk = f.read(32)
        if len(chunk) < 32:
            break
        date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
        records.append({'date': date, 'close': c/100.0, 'high': h/100.0,
                        'low': l/100.0, 'open': o/100.0, 'volume': vol})

# 取后 180 天
recent = records[-180:]

def calc_ma(vals, n):
    return [None if i < n-1 else sum(vals[i-n+1:i+1])/n for i in range(len(vals))]

closes  = [r['close'] for r in recent]
volumes = [r['volume'] for r in recent]
ma30    = calc_ma(closes, 30)

# 找所有穿越 MA30 的点（下穿上）
crossovers = []
for i in range(1, len(recent)):
    if ma30[i] and ma30[i-1]:
        if recent[i-1]['close'] <= ma30[i-1] and recent[i]['close'] > ma30[i]:
            crossovers.append(i)

print('=== sh605218 近 180 天 K 线 + MA30 ===')
print(f'{"日期":<10}  {"开盘":>7}  {"收盘":>7}  {"MA30":>7}  {"成交量":>12}  备注')
print('-' * 65)
for i, r in enumerate(recent):
    m30 = f'{ma30[i]:.2f}' if ma30[i] else '     -'
    mark = ''
    if i in crossovers:
        mark = '  <<< 突破MA30'
    chg = (r['close'] - recent[i-1]['close']) / recent[i-1]['close'] * 100 if i > 0 else 0
    chg_s = f'{chg:+.1f}%' if i > 0 else '    '
    above = '上方' if (ma30[i] and r['close'] > ma30[i]) else ('下方' if ma30[i] else '  -')
    print(f'{r["date"]}  {r["open"]:>7.2f}  {r["close"]:>7.2f}  {m30:>7}  {r["volume"]:>12,}  {chg_s} {above}{mark}')

print()
print(f'穿越点日期: {[recent[i]["date"] for i in crossovers]}')
print(f'总记录数: {len(records)}, 用最后180条分析')

# 找洗盘区间：突破日前的 wash 区间（程序用的是 bi-1 往前 88 天）
if crossovers:
    bi = crossovers[-1]  # 最后一次穿越
    wash_end   = bi - 1
    wash_start = max(0, bi - 88)
    print()
    print(f'突破日索引: {bi}, 日期: {recent[bi]["date"]}')
    print(f'洗盘区间: recent[{wash_start}]={recent[wash_start]["date"]} ~ recent[{wash_end}]={recent[wash_end]["date"]}')
    print(f'洗盘天数: {wash_end - wash_start + 1}')

    # 建仓区间：wash_start 之前 120 天
    pull_end   = wash_start
    pull_start = max(0, pull_end - 120)
    pull_closes = [r['close'] for r in recent[pull_start:pull_end+1]]
    if pull_closes:
        pull_high = max(pull_closes)
        pull_low  = min(pull_closes)
        surge_pct = (pull_high - pull_low) / pull_low * 100
        print(f'建仓区间: recent[{pull_start}]={recent[pull_start]["date"]} ~ recent[{pull_end}]={recent[pull_end]["date"]}')
        print(f'建仓期高低点: {pull_high:.2f} / {pull_low:.2f}, 涨幅: {surge_pct:.1f}%')
