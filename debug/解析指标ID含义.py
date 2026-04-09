"""
通过已知股票的财务数据，反推 cw 文件中各 indicator ID 的含义

策略：
  1. 取招商银行(sh600036) + 五粮液(gpsz000858) 两只熟悉的股票
  2. 按 byte[0] (指标ID) 分组，每组显示最近 5 个日期 + 值
  3. 结合已知财务常识对号入座
"""
import struct, os, math

base = r'D:\soft\new_tdx\vipdoc\cw'

TARGETS = {
    'sh600036': '招商银行',
    'sz000858': '五粮液',
    'sz000001': '平安银行',
    'sh601318': '中国平安',
}

RECORD_SIZE = 13

def read_all(fname):
    """读取 cw dat 文件，返回按 ID 分组的记录"""
    path = os.path.join(base, f'gp{fname}.dat')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        raw = f.read()
    groups = {}
    count = len(raw) // RECORD_SIZE
    for i in range(count):
        chunk = raw[i*RECORD_SIZE : i*RECORD_SIZE+RECORD_SIZE]
        indicator_id = chunk[0]
        date_int = struct.unpack('<I', chunk[1:5])[0]
        v1 = struct.unpack('<f', chunk[5:9])[0]
        v2 = struct.unpack('<f', chunk[9:13])[0]
        yr, mo, dy = date_int//10000, (date_int%10000)//100, date_int%100
        if not (1990 <= yr <= 2030 and 1 <= mo <= 12 and 1 <= dy <= 31):
            continue
        date_str = f'{yr:04d}-{mo:02d}-{dy:02d}'
        if indicator_id not in groups:
            groups[indicator_id] = []
        v1 = v1 if math.isfinite(v1) else 0.0
        v2 = v2 if math.isfinite(v2) else 0.0
        groups[indicator_id].append((date_str, round(v1, 4), round(v2, 4)))
    return groups

# ── 已知的参考值（2026-03 前后大约值）────────────────────────────────────────
# 招商银行(600036): 股价~43元, PE~6.5x, PB~0.95x, 市值~1.65万亿, 换手率~0.3%
# 五粮液(000858):   股价~145元, PE~17x, PB~5x, 市值~5600亿, 换手率~0.5%
KNOWN = {
    'sh600036': {
        '股价(元)': 43,
        'PE(倍)': 6.5,
        'PB(倍)': 0.95,
        '总市值(亿元)': 16500,
        '流通市值(亿元)': 16000,
        '换手率(%)': 0.3,
        '量比': 1.0,
    },
    'sz000858': {
        '股价(元)': 145,
        'PE(倍)': 17,
        'PB(倍)': 5,
        '总市值(亿元)': 5600,
        '流通市值(亿元)': 5600,
        '换手率(%)': 0.5,
    }
}

all_groups = {}
for code, name in TARGETS.items():
    g = read_all(code)
    if g:
        all_groups[code] = (name, g)
        print(f'已读取 {code}({name})：共 {len(g)} 种指标ID')

# ── 汇总：所有 ID，显示各股票最近5条 ─────────────────────────────────────────
all_ids = set()
for code, (name, g) in all_groups.items():
    all_ids.update(g.keys())

print()
print('=' * 80)
print(f'共发现 {len(all_ids)} 种指标ID：{sorted(all_ids)}')
print()
print('参考值（招商银行2026-03附近）：股价≈43元  PE≈6.5x  PB≈0.95  市值≈1.65万亿  换手≈0.3%')
print('参考值（五粮液2026-03附近）：  股价≈145元 PE≈17x   PB≈5.0  市值≈5600亿   换手≈0.5%')
print('=' * 80)

for iid in sorted(all_ids):
    print(f'\n【ID = {iid:>3}】', end='')
    for code, (name, g) in all_groups.items():
        if iid not in g:
            continue
        recs = g[iid]
        recent = recs[-5:]
        vals = [r[1] for r in recent]
        avg  = sum(vals) / len(vals) if vals else 0
        print(f'   {name}({code}) 最近{len(recent)}条均值={avg:.4f}', end='')
    print()
    # 打印每只股票最近3条明细
    for code, (name, g) in all_groups.items():
        if iid not in g:
            continue
        recs = g[iid][-3:]
        for date_str, v1, v2 in recs:
            v2s = f'  副={v2:.4f}' if v2 != 0 else ''
            print(f'      {name:6s} {date_str}  主值={v1:>18.4f}{v2s}')
