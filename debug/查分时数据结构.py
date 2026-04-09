"""
通达信 fzline(5分钟线) / minline(1分钟线) 正确格式解析
每条记录 32 字节：
  bytes 0-1   uint16   日期 = (年-2004)<<11 | 月<<7 | 日
  bytes 2-3   uint16   时间 = 全天分钟数（570=09:30, 900=15:00）
  bytes 4-7   float32  开盘价（元）
  bytes 8-11  float32  最高价（元）
  bytes 12-15 float32  最低价（元）
  bytes 16-19 float32  收盘价（元）
  bytes 20-23 float32  成交额（元）
  bytes 24-27 uint32   成交量（手）
  bytes 28-31 uint32   保留字段
"""
import struct
import os

DIRS = {
    'fzline  (5分钟线 .lc5)': r'D:\soft\new_tdx\vipdoc\sh\fzline',
    'minline (1分钟线 .lc1)': r'D:\soft\new_tdx\vipdoc\sh\minline',
}

def decode(chunk):
    dv, tv, o, h, l, c, amt, vol, _ = struct.unpack('<HHfffffII', chunk)
    yr = (dv >> 11) + 2004
    mo = (dv >> 7) & 0xF
    dy = dv & 0x7F
    hr = tv // 60
    mn = tv % 60
    return {
        'date':   f'{yr:04d}-{mo:02d}-{dy:02d}',
        'time':   f'{hr:02d}:{mn:02d}',
        'open':   round(o, 3),
        'high':   round(h, 3),
        'low':    round(l, 3),
        'close':  round(c, 3),
        'amount': round(amt / 1e4, 2),   # 万元
        'volume': vol,
    }

for label, base_dir in DIRS.items():
    print('=' * 72)
    print(f'【{label}】')
    print(f'目录：{base_dir}')

    if not os.path.exists(base_dir):
        print('!! 目录不存在\n'); continue

    files = [f for f in os.listdir(base_dir) if f.endswith('.lc5') or f.endswith('.lc1')]
    print(f'文件数量：{len(files)}   示例：{files[:4]}')

    # 选上证指数
    ext = '.lc5' if '.lc5' in files[0] else '.lc1'
    sample = os.path.join(base_dir, f'sh000001{ext}')
    if not os.path.exists(sample):
        sample = os.path.join(base_dir, files[0])

    sz = os.path.getsize(sample)
    count = sz // 32
    print(f'样本：{os.path.basename(sample)}   大小：{sz} B   共 {count} 条')

    with open(sample, 'rb') as f:
        raw = f.read()

    first = decode(raw[:32])
    last  = decode(raw[-32:])

    print(f'\n数据区间：{first["date"]} {first["time"]}  →  {last["date"]} {last["time"]}')
    print()
    print('字段结构（每条32字节，小端序）：')
    print('  偏移  字节  类型      字段')
    print('  0     2     uint16    日期（位压缩：年-2004存高5位，月存中4位，日存低7位）')
    print('  2     2     uint16    时间（当天总分钟数，570=09:30  900=15:00）')
    print('  4     4     float32   开盘价（元）')
    print('  8     4     float32   最高价（元）')
    print(' 12     4     float32   最低价（元）')
    print(' 16     4     float32   收盘价（元）')
    print(' 20     4     float32   成交额（元）')
    print(' 24     4     uint32    成交量（手）')
    print(' 28     4     uint32    保留字段')
    print()

    # 打印第1条 + 最近10条
    print(f'  {"日期":<12} {"时间":<6} {"开盘":>10} {"最高":>10} {"最低":>10} {"收盘":>10} {"成交量(手)":>12} {"成交额(万)":>10}')
    print('  ' + '─' * 72)
    indices = [0] + list(range(max(1, count - 9), count))
    for i in indices:
        r = decode(raw[i*32 : i*32+32])
        tag = ' ← 首条' if i == 0 else (' ← 最新' if i == count-1 else '')
        print(f'  {r["date"]}  {r["time"]}  '
              f'{r["open"]:>10.3f} {r["high"]:>10.3f} {r["low"]:>10.3f} {r["close"]:>10.3f} '
              f'{r["volume"]:>12,} {r["amount"]:>10.2f}万{tag}')
    print()
