"""读取回测结果文件，按月汇总胜率，对照大盘阶段"""
import re

RESULT_FILE = r'd:\stock\backtest\results\回测-站回MA30_大涨过滤版_202501.txt'

# 大盘阶段时间轴（手动录入）
PHASES = [
    ('20250102', '20250221', '▼空仓'),
    ('20250224', '20250320', '★做波段'),
    ('20250321', '20250403', '△企稳观察'),
    ('20250407', '20250515', '▼空仓'),
    ('20250516', '20250612', '★做波段'),
    ('20250613', '20250623', '△企稳观察'),
    ('20250624', '20250917', '★做波段'),
    ('20250918', '20250929', '△企稳观察'),
    ('20250930', '20251114', '★做波段'),
    ('20251117', '20251204', '△企稳观察'),
    ('20251205', '20251231', '▼空仓'),
    ('20260105', '20260130', '★做波段'),
    ('20260202', '20260316', '△企稳观察'),
    ('20260317', '20260410', '▼空仓'),
]

def get_phase(date_str):
    for s, e, p in PHASES:
        if s <= date_str <= e:
            return p
    return '?'

# 读取文件，解析每日胜率行
# 格式: 20250102    跌-2.66%      13     0.0%     7.7%    15.4%
month_data = {}   # {month: {'wins1':[], 'wins3':[], 'counts':[]}}

with open(RESULT_FILE, encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(
    r'(\d{8})\s+[涨跌]\s*[+-][\d.]+%\s+(\d+)\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%'
)

for m in pattern.finditer(content):
    date, cnt, w1, w2, w3 = m.group(1), int(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5))
    month = date[:6]
    if month not in month_data:
        month_data[month] = {'dates': [], 'cnts': [], 'w1': [], 'w2': [], 'w3': []}
    month_data[month]['dates'].append(date)
    month_data[month]['cnts'].append(cnt)
    month_data[month]['w1'].append((w1, cnt))
    month_data[month]['w2'].append((w2, cnt))
    month_data[month]['w3'].append((w3, cnt))

def wavg(pairs):
    """加权平均胜率"""
    total_w = sum(w * c for w, c in pairs)
    total_c = sum(c for _, c in pairs)
    return total_w / total_c if total_c else 0

def main_phase(month):
    """取该月主要阶段（出现最多的）"""
    phase_days = {}
    for d in month_data[month]['dates']:
        p = get_phase(d)
        phase_days[p] = phase_days.get(p, 0) + 1
    return max(phase_days, key=phase_days.get), phase_days

MONTH_LABEL = {
    '202501':'2025-01','202502':'2025-02','202503':'2025-03',
    '202504':'2025-04','202505':'2025-05','202506':'2025-06',
    '202507':'2025-07','202508':'2025-08','202509':'2025-09',
    '202510':'2025-10','202511':'2025-11','202512':'2025-12',
    '202601':'2026-01','202602':'2026-02','202603':'2026-03',
}

print('=' * 78)
print('【MA30站回策略 月度胜率汇总（大涨过滤版）2025-01 至 2026-03】')
print('=' * 78)
print(f'  {"月份":<8}  {"大盘主阶段":<10}  {"信号数":>5}  {"持1天胜率":>8}  {"持2天胜率":>8}  {"持3天胜率":>8}')
print('  ' + '─' * 62)

total_c = 0
total_w1 = total_w2 = total_w3 = 0

for month in sorted(month_data.keys()):
    d = month_data[month]
    cnt   = sum(d['cnts'])
    w1    = wavg(d['w1'])
    w2    = wavg(d['w2'])
    w3    = wavg(d['w3'])
    ph, ph_detail = main_phase(month)

    # 阶段混合时显示明细
    ph_str = ph
    if len(ph_detail) > 1:
        detail = '/'.join(f'{v}日{k}' for k, v in sorted(ph_detail.items(), key=lambda x:-x[1]))
        ph_str = f'{ph}({detail})'

    # 胜率颜色标记
    def mark(v):
        if v >= 60: return f'{v:>5.1f}%★'
        if v <= 35: return f'{v:>5.1f}%▼'
        return f'{v:>5.1f}%  '

    print(f'  {MONTH_LABEL.get(month, month):<8}  {ph_str:<20}  {cnt:>5}  {mark(w1):>10}  {mark(w2):>10}  {mark(w3):>10}')
    total_c  += cnt
    total_w1 += w1 * cnt
    total_w2 += w2 * cnt
    total_w3 += w3 * cnt

print('  ' + '─' * 62)
print(f'  {"合计":<8}  {"":20}  {total_c:>5}  '
      f'{total_w1/total_c:>5.1f}%    {total_w2/total_c:>5.1f}%    {total_w3/total_c:>5.1f}%')
print()
print('  ★ = 胜率≥60%（强势）   ▼ = 胜率≤35%（弱势）')
print()
print('【大盘阶段对照表】')
print('  ─' * 35)
for s, e, p in PHASES:
    sd = f'{s[:4]}-{s[4:6]}-{s[6:]}'
    ed = f'{e[:4]}-{e[4:6]}-{e[6:]}'
    print(f'  {p}   {sd} → {ed}')
