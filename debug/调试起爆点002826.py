"""逐步追踪 002826 在起爆点策略中被哪个条件过滤"""
import struct, sys
sys.stdout.reconfigure(encoding='utf-8')

def read_day_file(fp):
    records = []
    with open(fp, 'rb') as f:
        while True:
            chunk = f.read(32)
            if len(chunk) < 32: break
            date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
            records.append({'date': date, 'open': o/100, 'high': h/100,
                             'low': l/100, 'close': c/100, 'volume': vol})
    return records

def calc_ma(v, n):
    return [None if i < n-1 else sum(v[i-n+1:i+1])/n for i in range(len(v))]

def fmt(d):
    s = str(d); return f'{s[:4]}-{s[4:6]}-{s[6:]}'

records = read_day_file(r'D:\soft\new_tdx\vipdoc\sz\lday\sz002826.day')
closes  = [r['close'] for r in records]
volumes = [r['volume'] for r in records]
ma5  = calc_ma(closes, 5)
ma20 = calc_ma(closes, 20)
ma30 = calc_ma(closes, 30)
ma60 = calc_ma(closes, 60)

# 找突破日（1月20日～1月31日窗口内）
bi = -1
for i in range(1, len(records)):
    if records[i]['date'] < 20260120 or records[i]['date'] > 20260131: continue
    if ma30[i] is None or ma30[i-1] is None: continue
    if not (records[i-1]['close'] <= ma30[i-1] and records[i]['close'] > ma30[i]): continue
    confirmed = any(ma30[j] and records[j]['close'] > ma30[j]
                    for j in range(i+1, min(i+4, len(records))))
    print(f'候选突破日 {fmt(records[i]["date"])}: prev={records[i-1]["close"]:.2f} ma30={ma30[i-1]:.2f} | close={records[i]["close"]:.2f} ma30={ma30[i]:.2f} | 确认={confirmed}')
    if confirmed:
        bi = i; break

if bi < 0:
    print('未找到突破日'); exit()

print(f'\n突破日：{fmt(records[bi]["date"])}  收{records[bi]["close"]:.2f}  MA30={ma30[bi]:.2f}')
break_close = records[bi]['close']
break_pct   = (break_close - ma30[bi]) / ma30[bi] * 100
print(f'超MA30：{break_pct:+.2f}%  (要求0.5~12%)')

# 洗盘期
wash_end   = bi - 1
wash_start = max(0, bi - 88)
wash_recs  = records[wash_start:wash_end+1]
wash_vols  = volumes[wash_start:wash_end+1]
wash_cls   = closes[wash_start:wash_end+1]
print(f'\n洗盘期：{fmt(records[wash_start]["date"])} ~ {fmt(records[wash_end]["date"])}  共{len(wash_recs)}天')

below_count = sum(1 for j in range(wash_start, wash_end+1)
                  if ma30[j] and records[j]['close'] <= ma30[j] * 1.03)
wash_days = len(wash_recs)
print(f'洗盘期收盘<=MA30*1.03的天数：{below_count}/{wash_days}  要求>={wash_days*0.6:.0f}天  {"通过" if below_count >= wash_days*0.6 else "❌过滤"}')

# 建仓期
pull_end   = wash_start
pull_start = max(0, pull_end - 120)
pull_cls   = closes[pull_start:pull_end+1]
pull_vols  = volumes[pull_start:pull_end+1]
pull_low   = min(pull_cls)
pull_high  = max(pull_cls)
surge_pct  = (pull_high - pull_low) / pull_low * 100
print(f'\n建仓期：{fmt(records[pull_start]["date"])} ~ {fmt(records[pull_end]["date"])}  共{len(pull_cls)}天')
print(f'建仓期最低：{pull_low:.2f}  最高：{pull_high:.2f}  涨幅：{surge_pct:.1f}%  (要求>=20%)  {"通过" if surge_pct >= 20 else "❌过滤"}')

# 缩量
avg_pull = sum(pull_vols) / len(pull_vols)
avg_wash = sum(wash_vols) / len(wash_vols)
shrink   = avg_wash / avg_pull
print(f'\n建仓期均量：{avg_pull/10000:.0f}万手  洗盘期均量：{avg_wash/10000:.0f}万手')
print(f'缩量比：{shrink:.2f}x  (要求<0.8)  {"通过" if shrink < 0.8 else "❌过滤"}')

# 洗盘振幅
peak_in_wash = max(range(len(wash_cls)), key=lambda k: wash_cls[k])
pp_cls  = wash_cls[peak_in_wash:]
w_range = (max(pp_cls) - min(pp_cls)) / min(pp_cls) * 100
print(f'\n洗盘振幅（从高点往后）：{w_range:.1f}%  (要求<35%)  {"通过" if w_range < 35 else "❌过滤"}')

# MA粘合度
ma_sp = []
for j in range(wash_start, wash_end+1):
    if ma5[j] and ma20[j] and ma30[j] and ma60[j]:
        hi = max(ma5[j], ma20[j], ma30[j], ma60[j])
        lo = min(ma5[j], ma20[j], ma30[j], ma60[j])
        ma_sp.append((hi-lo)/ma30[j]*100)
mc = sum(ma_sp)/len(ma_sp) if ma_sp else 99
print(f'\nMA四线粘合度：{mc:.2f}%  {"★极致" if mc < 2 else ("优质" if mc < 3.5 else "一般")}')
