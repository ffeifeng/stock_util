"""
通达信 cw 目录深度分析
每条记录 13 字节（通过 GCD 确认）
"""
import struct, os

base = r'D:\soft\new_tdx\vipdoc\cw'
files = os.listdir(base)
dats  = sorted([f for f in files if f.endswith('.dat')])

# ── 1. 目录概览 ──────────────────────────────────────────────────────────────
print('=' * 68)
print(f'目录：{base}')
print(f'.dat 文件：{len(dats)} 个  前缀分布：')
pfx = {}
for f in dats:
    p = f[:4]; pfx[p] = pfx.get(p, 0) + 1
for p, n in sorted(pfx.items(), key=lambda x: -x[1]):
    print(f'  {p}  →  {n} 个文件   （文件名规则：gp+市场+股票代码）')

# ── 2. 单文件深度解析（gpsh 沪市 + gpsz 深市各取1个有代表性的）──────────────
SAMPLES = {}
for prefix, code in [('gpsh', '600036'), ('gpsz', '000858'), ('gpbj', '920000')]:
    fname = f'{prefix}{code}.dat'
    path  = os.path.join(base, fname)
    if os.path.exists(path):
        SAMPLES[fname] = path

if not SAMPLES:
    # fallback：随便取前3个
    for f in dats[:3]:
        SAMPLES[f] = os.path.join(base, f)

RECORD_SIZE = 13  # GCD 确认

for fname, path in SAMPLES.items():
    sz    = os.path.getsize(path)
    count = sz // RECORD_SIZE
    print()
    print('=' * 68)
    print(f'文件：{fname}  大小：{sz} B  共 {count} 条记录（{RECORD_SIZE} 字节/条）')

    with open(path, 'rb') as f:
        raw = f.read()

    print()
    print('字段结构（每条 13 字节）：')
    print('  偏移  字节  类型       推测含义')
    print('  0     1     uint8      标志位（观察到多为 0x01）')
    print('  1     3     3字节      ---（日期/ID编码，待分析）')
    print('  4     1     uint8      子类型/标志（观察到多为 0x01）')
    print('  5     4     float32    主值')
    print('  9     4     float32    副值')

    # 尝试解析日期 ─ 按 YYYYMMDD 将 bytes 1-4 作为 uint32（小端）
    def try_date_le(b1, b2, b3, b4):
        """尝试把4字节小端解读为 YYYYMMDD 整数"""
        v = b1 | (b2 << 8) | (b3 << 16) | (b4 << 24)
        y, m, d = v // 10000, (v % 10000) // 100, v % 100
        if 1990 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return f'{y:04d}-{m:02d}-{d:02d}'
        return None

    print()
    print(f'首条 & 最近 15 条数据：')
    print(f'  {"#":>5}  {"bytes 0-3 (hex)":16}  {"日期尝试":12}  {"b4":>3}  {"主值(f32)":>12}  {"副值(f32)":>12}')
    print('  ' + '─' * 68)

    indices = [0] + list(range(max(1, count - 14), count))
    for i in indices:
        chunk = raw[i * RECORD_SIZE : i * RECORD_SIZE + RECORD_SIZE]
        if len(chunk) < RECORD_SIZE:
            break
        b0, b1, b2, b3, b4 = chunk[0], chunk[1], chunk[2], chunk[3], chunk[4]
        v1 = struct.unpack('<f', chunk[5:9])[0]
        v2 = struct.unpack('<f', chunk[9:13])[0]
        date_str = try_date_le(b1, b2, b3, b4) or '---'
        hex4 = f'{b0:02x} {b1:02x} {b2:02x} {b3:02x}'
        tag  = ' ← 首条' if i == 0 else (' ← 最新' if i == count - 1 else '')
        # 过滤掉明显异常的float（nan/inf）
        import math
        v1s = f'{v1:12.4f}' if math.isfinite(v1) else '       NaN/Inf'
        v2s = f'{v2:12.4f}' if math.isfinite(v2) else '       NaN/Inf'
        print(f'  {i:>5}  {hex4}  {date_str:12}  {b4:>3}  {v1s}  {v2s}{tag}')

    # 统计 b0 和 b4 的分布
    b0_dist, b4_dist = {}, {}
    for i in range(count):
        chunk = raw[i*RECORD_SIZE : i*RECORD_SIZE+RECORD_SIZE]
        b0_dist[chunk[0]] = b0_dist.get(chunk[0], 0) + 1
        b4_dist[chunk[4]] = b4_dist.get(chunk[4], 0) + 1
    print()
    print(f'byte[0] 分布（标志位）：{sorted(b0_dist.items())}')
    print(f'byte[4] 分布（子标志）：{sorted(b4_dist.items())[:20]}')

    # 找出主值的范围
    vals = []
    for i in range(count):
        chunk = raw[i*RECORD_SIZE : i*RECORD_SIZE+RECORD_SIZE]
        v = struct.unpack('<f', chunk[5:9])[0]
        if math.isfinite(v) and abs(v) < 1e9:
            vals.append(v)
    if vals:
        print(f'主值(float)范围：min={min(vals):.4f}  max={max(vals):.4f}  '
              f'均值={sum(vals)/len(vals):.4f}  非零条数={sum(1 for v in vals if v!=0)}')
