import struct
import os

dirs = {
    'SZ': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'SH': r'D:\soft\new_tdx\vipdoc\sh\lday',
}

for market, d in dirs.items():
    files = [f for f in os.listdir(d) if f.endswith('.day')]
    print(f'{market} 目录：{d}')
    print(f'  共 {len(files)} 个 .day 文件')
    print(f'  示例文件名：{files[:6]}')
    print()

sample = r'D:\soft\new_tdx\vipdoc\sz\lday\sz002432.day'
size   = os.path.getsize(sample)

print('=' * 65)
print(f'示例文件：{sample}')
print(f'文件大小：{size} 字节，共 {size // 32} 条日线记录（每条32字节）')
print()
print('字段结构（每条32字节，小端序 Little-Endian）：')
print('  偏移  字节  类型      字段说明')
print('  0     4     uint32    日期（YYYYMMDD 整数）')
print('  4     4     uint32    开盘价（单位：分，除以100得元）')
print('  8     4     uint32    最高价（单位：分）')
print(' 12     4     uint32    最低价（单位：分）')
print(' 16     4     uint32    收盘价（单位：分）')
print(' 20     4     float32   成交额（元）')
print(' 24     4     uint32    成交量（手，1手=100股）')
print(' 28     4     uint32    保留字段（通常为0）')
print()

records = []
with open(sample, 'rb') as f:
    while True:
        chunk = f.read(32)
        if len(chunk) < 32:
            break
        date, open_, high, low, close, amount, volume, _ = struct.unpack('<IIIIIfII', chunk)
        records.append({
            'date':   date,
            'open':   open_ / 100,
            'high':   high  / 100,
            'low':    low   / 100,
            'close':  close / 100,
            'volume': volume,
            'amount': amount,
        })

print('最近10条数据（sz002432 易明医药）：')
print(f'  {"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8} {"成交量(手)":>12} {"成交额(万)":>10}')
print('  ' + '-' * 68)
for r in records[-10:]:
    print(f'  {r["date"]}  {r["open"]:>8.2f} {r["high"]:>8.2f} '
          f'{r["low"]:>8.2f} {r["close"]:>8.2f} '
          f'{r["volume"]:>12,} {r["amount"]/10000:>9.0f}万')

print()
print(f'数据区间：{records[0]["date"]} ~ {records[-1]["date"]}，共 {len(records)} 个交易日')
