import struct

def read_last(path, n=40):
    recs = []
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            total = f.tell() // 32
            f.seek(max(0, total - n) * 32)
            while True:
                c = f.read(32)
                if len(c) < 32: break
                d, o, h, l, cl, amt, vol, _ = struct.unpack('<IIIIIfII', c)
                recs.append({'date': d, 'open': o/100, 'high': h/100,
                             'low': l/100, 'close': cl/100, 'vol': vol})
    except:
        pass
    return recs

def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n - 1, len(values)):
        r[i] = sum(values[i-n+1:i+1]) / n
    return r

path = r'D:\soft\new_tdx\vipdoc\sz\lday\sz002427.day'
recs = read_last(path, 40)
if not recs:
    print('文件不存在或无数据')
    exit()

closes = [r['close'] for r in recs]
ma5  = calc_ma(closes,  5)
ma10 = calc_ma(closes, 10)
ma30 = calc_ma(closes, 30)

print(f'sz002427  最近5日数据')
print(f'  {"日期":<12} {"开":>7} {"收":>7} {"MA5":>7} {"MA10":>7} {"MA30":>7}  {"阴线"} {"多头"} {"收/MA30"}')
print('  ' + '-' * 70)
for i in range(max(0, len(recs)-5), len(recs)):
    r = recs[i]
    is_yin = r['close'] < r['open']
    m5  = ma5[i]  or 0
    m10 = ma10[i] or 0
    m30 = ma30[i] or 0
    bull = m5 > 0 and m10 > 0 and m30 > 0 and m5 > m10 > m30
    if m30 > 0:
        diff = (r['close'] - m30) / m30 * 100
        pos  = '上方' if r['close'] >= m30 else '下方'
        diff_str = f'{pos}{abs(diff):.2f}%'
    else:
        diff_str = 'N/A'
    print(f'  {r["date"]}  {r["open"]:>7.2f}  {r["close"]:>7.2f}  '
          f'{m5:>7.2f}  {m10:>7.2f}  {m30:>7.2f}  '
          f'{"Y" if is_yin else "N"}    {"Y" if bull else "N"}    {diff_str}')

print()
# 分析为何未入选
last = recs[-1]
i = len(recs) - 1
is_yin = last['close'] < last['open']
m5  = ma5[i]  or 0
m10 = ma10[i] or 0
m30 = ma30[i] or 0
bull = m5 > 0 and m10 > 0 and m30 > 0 and m5 > m10 > m30
above_10 = m30 > 0 and (last['close'] - m30) / m30 * 100 > 10

print('未入选原因分析（A组条件）:')
print(f'  ① 今天是阴线(close<open):  {"✓" if is_yin else "✗  收{:.2f} >= 开{:.2f}，阳线或平开，不符合".format(last["close"], last["open"])}')
print(f'  ② MA5>MA10>MA30 多头排列:  {"✓" if bull else f"✗  MA5={m5:.2f}  MA10={m10:.2f}  MA30={m30:.2f}"}')
if m30 > 0:
    above = (last['close'] - m30) / m30 * 100
    if last['close'] < m30:
        print(f'  ③ 收盘在MA30上方:         ✗  收盘{last["close"]:.2f} < MA30 {m30:.2f}，在MA30下方')
    elif above > 10:
        print(f'  ③ 离MA30不超过10%:        ✗  离MA30 {above:.2f}%，超过10%上限')
    else:
        print(f'  ③ 收盘在MA30上方且≤10%:   ✓  离MA30 {above:.2f}%')
