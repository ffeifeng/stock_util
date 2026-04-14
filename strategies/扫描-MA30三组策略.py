"""
MA30 三组策略扫描：
  A组：指定日收盘在 MA30 上方（阴线整理，离MA30在5%以内）
  B组：指定日首次跌破 MA30（前一天还在上方，当天才破）
  C组：前一天在 MA30 下方，当天站回 MA30 上方（强势修复信号）

每组独立输出到固定文件（持久化累积，自动踢除不符合条件的）：
  output/MA30扫描_上方整理.txt
  output/MA30扫描_首次跌破.txt
  output/MA30扫描_站回MA30.txt
  output/MA30扫描_数据库.json

用法：
  python 扫描-MA30三组策略.py          # 扫最新一天
  python 扫描-MA30三组策略.py 1        # 扫昨天
  python 扫描-MA30三组策略.py 2        # 扫前天
"""
import struct, os, sys, json
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
MIN_PRICE = 3.0

DAYS_BACK = int(sys.argv[1]) if len(sys.argv) > 1 else 0

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '均线策略')
DB_PATH = os.path.join(OUT_DIR, 'MA30扫描_数据库.json')
TXT_A   = os.path.join(OUT_DIR, 'MA30扫描_上方整理.txt')
TXT_B   = os.path.join(OUT_DIR, 'MA30扫描_首次跌破.txt')
TXT_C   = os.path.join(OUT_DIR, 'MA30扫描_站回MA30.txt')


def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({'date': date, 'open': o/100, 'high': h/100,
                                'low': l/100, 'close': c/100, 'volume': vol})
    except: pass
    return records


def calc_ma(values, n):
    r = [None] * len(values)
    for i in range(n-1, len(values)):
        r[i] = sum(values[i-n+1:i+1]) / n
    return r


def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False


def load_st_codes():
    st_set = set()
    p = r'D:\soft\st_codes.txt'
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                c = line.strip()
                if c: st_set.add(c)
    return st_set


def load_db():
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('stocks', {})
        except:
            pass
    return {}


def save_db(stocks: dict, scan_date: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump({'last_updated': scan_date, 'stocks': stocks},
                  f, ensure_ascii=False, indent=2)


def scan():
    st_codes = load_st_codes()
    db = load_db()

    # 扫描前记录上一次各票所在分组及数据快照
    prev_group = {code: entry.get('last_group', '') for code, entry in db.items()}
    prev_data  = {code: dict(entry) for code, entry in db.items()}

    group_a, group_b, group_c = [], [], []
    scan_date = ''

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < 35 + DAYS_BACK: continue

            closes = [r['close'] for r in records]
            ma5  = calc_ma(closes,  5)
            ma10 = calc_ma(closes, 10)
            ma30 = calc_ma(closes, 30)

            i  = len(records) - 1 - DAYS_BACK
            i1 = i - 1

            if any(x is None for x in [ma5[i], ma10[i], ma30[i], ma5[i1], ma30[i1]]):
                continue

            today = records[i]
            yest  = records[i1]

            if today['close'] < MIN_PRICE: continue

            if not scan_date:
                d = str(today['date'])
                scan_date = f'{d[:4]}-{d[4:6]}-{d[6:8]}'

            is_yin  = today['close'] < today['open']
            day_pct = (today['close'] - yest['close']) / yest['close'] * 100

            base = {
                'code':      code,
                'close':     round(today['close'], 2),
                'ma30':      round(ma30[i], 2),
                'ma10':      round(ma10[i], 2),
                'ma5':       round(ma5[i], 2),
                'day_pct':   round(day_pct, 2),
                'scan_date': scan_date,
            }

            today_above = today['close'] >= ma30[i]
            yest_above  = yest['close']  >= ma30[i1]

            if today_above and yest_above:
                above_pct = (today['close'] - ma30[i]) / ma30[i] * 100
                if above_pct > 5.0: continue
                base['group']     = 'A'
                base['above_pct'] = round(above_pct, 2)
                group_a.append(base)
            elif not today_above and yest_above:
                below_pct = (ma30[i] - today['close']) / ma30[i] * 100
                base['group']     = 'B'
                base['below_pct'] = round(below_pct, 2)
                group_b.append(base)
            elif today_above and not yest_above:
                # C组：仅昨天在MA30下方，今天站回（前天必须在MA30上方）
                i2 = i - 2
                if i2 < 0 or ma30[i2] is None: continue
                if records[i2]['close'] < ma30[i2]: continue   # 前天也在下方则排除
                above_pct = (today['close'] - ma30[i]) / ma30[i] * 100
                base['group']     = 'C'
                base['above_pct'] = round(above_pct, 2)
                group_c.append(base)

    # ── 标记每条记录的变化类型 ──────────────────────────────────────
    for rec in group_a + group_b + group_c:
        code = rec['code']
        pg   = prev_group.get(code, '')
        if code not in prev_group:
            rec['tag'] = '[新]'     # 全新出现
        elif pg != rec['group']:
            rec['tag'] = '[换]'     # 从其他组换过来
        else:
            rec['tag'] = '    '     # 正常更新

    # ── 更新数据库 ──────────────────────────────────────────────────
    current_codes = set()
    for rec in group_a + group_b + group_c:
        code = rec['code']
        current_codes.add(code)
        if code in db:
            db[code].update({
                'close':      rec['close'],
                'ma30':       rec['ma30'],
                'ma10':       rec['ma10'],
                'ma5':        rec['ma5'],
                'day_pct':    rec['day_pct'],
                'last_group': rec['group'],
                'last_seen':  scan_date,
                'scan_date':  scan_date,
            })
            for k in ('above_pct', 'below_pct'):
                db[code].pop(k, None)
            if 'above_pct' in rec: db[code]['above_pct'] = rec['above_pct']
            if 'below_pct' in rec: db[code]['below_pct'] = rec['below_pct']
        else:
            db[code] = {
                'code':        code,
                'first_seen':  scan_date,
                'first_group': rec['group'],
                'last_seen':   scan_date,
                'last_group':  rec['group'],
                'close':       rec['close'],
                'ma30':        rec['ma30'],
                'ma10':        rec['ma10'],
                'ma5':         rec['ma5'],
                'day_pct':     rec['day_pct'],
                'scan_date':   scan_date,
            }
            if 'above_pct' in rec: db[code]['above_pct'] = rec['above_pct']
            if 'below_pct' in rec: db[code]['below_pct'] = rec['below_pct']

    # 踢掉不再符合条件的票（踢前先按原分组收集，用于文件末尾展示）
    deleted_by_group = {'A': [], 'B': [], 'C': []}
    for code in list(db.keys()):
        if code not in current_codes:
            pg = prev_group.get(code, '')
            if pg in deleted_by_group:
                deleted_by_group[pg].append(prev_data[code])
            del db[code]

    save_db(db, scan_date)

    # ── 排序 ────────────────────────────────────────────────────────
    group_a.sort(key=lambda x: (x['tag'] != '[新]', x['tag'] != '[换]', x['above_pct']))
    group_b.sort(key=lambda x: (x['tag'] != '[新]', x['tag'] != '[换]', x['below_pct']))
    group_c.sort(key=lambda x: (x['tag'] != '[新]', x['tag'] != '[换]', x['above_pct']))

    day_tag = '昨天' if DAYS_BACK == 1 else (f'前{DAYS_BACK}天' if DAYS_BACK > 1 else '今天')
    os.makedirs(OUT_DIR, exist_ok=True)

    def count_tags(group):
        new_  = sum(1 for r in group if r['tag'] == '[新]')
        swap_ = sum(1 for r in group if r['tag'] == '[换]')
        upd_  = sum(1 for r in group if r['tag'] == '    ')
        return new_, swap_, upd_

    def write_group(title, desc, group, col_key, col_label, sign, filepath, del_list):
        new_, swap_, upd_ = count_tags(group)
        del_ = len(del_list)

        lines = []
        def out(s=''):
            lines.append(s); print(s)

        out('=' * 80)
        out(f'【{title}】')
        out(f'数据日期：{scan_date}    {desc}')
        out(f'本次共 {len(group)} 只  |  新增 {new_} 只  换组 {swap_} 只  更新 {upd_} 只  移出 {del_} 只')
        out('=' * 80)
        hdr = f'  {"标记":^4}  {"排":>2}  {"代码":<10} {"收盘":>7} {"MA30":>7} {"MA10":>7} {"MA5":>7}  {"涨跌%":>7}  {col_label:>6}  {"首次出现":>10}'
        out(hdr)
        out('  ' + '─' * 76)
        for idx, r in enumerate(group, 1):
            first = db.get(r['code'], {}).get('first_seen', '')
            val   = r.get(col_key, 0)
            out(f'  {r["tag"]}  {idx:>2}  {r["code"]:<10} {r["close"]:>7.2f} {r["ma30"]:>7.2f} '
                f'{r["ma10"]:>7.2f} {r["ma5"]:>7.2f}  {r["day_pct"]:>+6.2f}%  '
                f'{sign}{val:>5.2f}%  {first}')

        # ── 移出区 ──────────────────────────────────────────────────
        if del_list:
            out()
            out('─' * 80)
            out(f'  【本次移出 {del_} 只（不再符合条件）】  以下为最后一次记录')
            out('─' * 80)
            out(hdr)
            out('  ' + '─' * 76)
            for r in del_list:
                val  = r.get(col_key, 0)
                first = r.get('first_seen', '')
                out(f'  [出]  {"":>2}  {r["code"]:<10} {r.get("close",0):>7.2f} {r.get("ma30",0):>7.2f} '
                    f'{r.get("ma10",0):>7.2f} {r.get("ma5",0):>7.2f}  {r.get("day_pct",0):>+6.2f}%  '
                    f'{sign}{val:>5.2f}%  {first}')

        out()
        out(f'  [新]=首次出现  [换]=从其他组换入  [出]=本次移出')
        out(f'  文件：{filepath}')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return new_, swap_, upd_, del_

    print()
    na, sa, ua, da = write_group(
        f'A组：{day_tag} 收在MA30上方（离MA30≤5%）',
        '按离MA30距离从近到远，新增/换入优先',
        group_a, 'above_pct', '离MA30', '+', TXT_A, deleted_by_group['A']
    )
    print()
    nb, sb, ub, db_ = write_group(
        f'B组：{day_tag} 首次跌破MA30（前一天还在上方）',
        '按跌破幅度从浅到深，新增/换入优先',
        group_b, 'below_pct', '跌破%', '-', TXT_B, deleted_by_group['B']
    )
    print()
    nc, sc, uc, dc = write_group(
        f'C组：{day_tag} 站回MA30上方（前一天在MA30下方）',
        '按站回幅度从小到大，新增/换入优先',
        group_c, 'above_pct', '站回%', '+', TXT_C, deleted_by_group['C']
    )

    print()
    print('=' * 60)
    print(f'  扫描完成  数据日期：{scan_date}')
    print(f'  上方整理(A)：共{len(group_a):>3}只  新增{na:>3}  换组{sa:>3}  更新{ua:>3}  移出{da:>3}')
    print(f'  首次跌破(B)：共{len(group_b):>3}只  新增{nb:>3}  换组{sb:>3}  更新{ub:>3}  移出{db_:>3}')
    print(f'  站回MA30(C)：共{len(group_c):>3}只  新增{nc:>3}  换组{sc:>3}  更新{uc:>3}  移出{dc:>3}')
    print(f'  数据库总计：{len(db)} 只')
    print('=' * 60)


if __name__ == '__main__':
    scan()
