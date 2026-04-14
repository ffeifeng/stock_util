"""
策略：涨停强势股跟踪池
逻辑：
  1. 每日扫描当天涨停的股票，加入股票池
  2. 扫描时检查股票池中已有的票：今日下跌的直接移出
  3. 持续追踪，每次输出：新增了哪些、移出了哪些、当前完整池
  4. 已在池中的票再次涨停，标记连板

用法：
  python 扫描-涨停强势股池.py          # 扫最新一天
  python 扫描-涨停强势股池.py 1        # 扫昨天（偏移1个交易日）
  python 扫描-涨停强势股池.py 2        # 扫前天

输出文件：
  output/涨停股池/涨停强势股池.txt      （每次覆盖，展示最新状态）
  output/涨停股池/涨停强势股池_数据库.json  （持久化股票池状态）
"""
import struct, os, sys, json
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# ── 数据路径 ──────────────────────────────────────────────────────────────────
DATA_DIRS = {
    'sz': r'D:\soft\new_tdx\vipdoc\sz\lday',
    'sh': r'D:\soft\new_tdx\vipdoc\sh\lday',
}
MIN_PRICE = 3.0

DAYS_BACK = int(sys.argv[1]) if len(sys.argv) > 1 else 0

OUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output', '涨停股池')
DB_PATH  = os.path.join(OUT_DIR, '涨停强势股池_数据库.json')
TXT_PATH = os.path.join(OUT_DIR, '涨停强势股池.txt')


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def read_day_file(path):
    records = []
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(32)
                if len(chunk) < 32: break
                date, o, h, l, c, amt, vol, _ = struct.unpack('<IIIIIfII', chunk)
                records.append({
                    'date':   date,
                    'open':   o / 100,
                    'high':   h / 100,
                    'low':    l / 100,
                    'close':  c / 100,
                    'volume': vol,
                })
    except: pass
    return records


def is_valid_stock(code):
    c = code.lower()
    if c.startswith('bj'): return False
    num = c[2:]
    if c.startswith('sh'): return num[:3] in ['600','601','602','603','604','605','688']
    if c.startswith('sz'): return num[:3] in ['000','001','002','003','300','301']
    return False


def get_limit_pct(code):
    """科创板/创业板 20%，主板 10%"""
    num = code[2:]
    if code.startswith('sh') and num[:3] == '688': return 20.0
    if code.startswith('sz') and num[:3] in ['300','301']: return 20.0
    return 10.0


def is_limit_up(code, close, prev_close):
    """判断是否涨停（允许0.2%误差应对浮点舍入）"""
    if prev_close <= 0: return False
    pct         = get_limit_pct(code)
    limit_price = round(prev_close * (1 + pct / 100), 2)
    return close >= limit_price * 0.998


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
            return data.get('pool', {})
        except: pass
    return {}


def save_db(pool: dict, scan_date: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump({'last_updated': scan_date, 'pool': pool},
                  f, ensure_ascii=False, indent=2)


def fmt_date(d):
    s = str(d)
    return f'{s[:4]}-{s[4:6]}-{s[6:8]}'


# ── 主扫描逻辑 ────────────────────────────────────────────────────────────────

def scan():
    st_codes = load_st_codes()
    pool     = load_db()      # 当前持久化的股票池
    scan_date = ''

    # 本轮所有股票的行情快照 {code: {close, day_pct, is_lim, above_min}}
    # above_min=False 表示价格低于 MIN_PRICE，不允许新入池，但已在池中的仍受下跌剔除规则约束
    today_snap = {}

    for market, data_dir in DATA_DIRS.items():
        if not os.path.exists(data_dir): continue
        for fname in os.listdir(data_dir):
            if not fname.endswith('.day'): continue
            code = fname[:-4]
            if not is_valid_stock(code): continue
            if code[2:] in st_codes: continue

            records = read_day_file(os.path.join(data_dir, fname))
            if len(records) < 3 + DAYS_BACK: continue

            i  = len(records) - 1 - DAYS_BACK
            i1 = i - 1
            if i1 < 0: continue

            today = records[i]
            yest  = records[i1]

            if not scan_date:
                scan_date = fmt_date(today['date'])

            day_pct    = (today['close'] - yest['close']) / yest['close'] * 100 if yest['close'] > 0 else 0
            above_min  = today['close'] >= MIN_PRICE
            lim_up     = above_min and is_limit_up(code, today['close'], yest['close'])

            today_snap[code] = {
                'close':     round(today['close'], 2),
                'open':      round(today['open'],  2),
                'high':      round(today['high'],  2),
                'low':       round(today['low'],   2),
                'day_pct':   round(day_pct, 2),
                'is_lim':    lim_up,
                'is_yang':   today['close'] > today['open'],   # 阳线（保留字段，不再用于过滤）
                'above_min': above_min,
            }

    # ── ① 判定股票池中哪些今日下跌或收阴线 → 移出 ──────────────────────────
    removed = []
    for code in list(pool.keys()):
        snap = today_snap.get(code)
        if snap is None:
            continue
        # 下跌则移出（不再要求阳线）
        if snap['day_pct'] < 0:
            entry = dict(pool[code])
            entry['remove_date']   = scan_date
            entry['remove_close']  = snap['close']
            entry['remove_pct']    = snap['day_pct']
            entry['remove_reason'] = '下跌'
            removed.append(entry)
            del pool[code]

    # ── ② 今日涨停的票加入/更新股票池（仅限价格 >= MIN_PRICE 的票）──────────
    added   = []   # 首次入池
    renewed = []   # 已在池中，再次涨停（连板）

    for code, snap in today_snap.items():
        if not snap['is_lim']: continue

        if code in pool:
            # 连板：更新记录
            pool[code]['last_seen']     = scan_date
            pool[code]['last_close']    = snap['close']
            pool[code]['last_pct']      = snap['day_pct']
            pool[code]['streak_days']   = pool[code].get('streak_days', 1) + 1
            pool[code]['limit_up_days'] = pool[code].get('limit_up_days', 1) + 1
            renewed.append(dict(pool[code]))
        else:
            # 新入池
            new_entry = {
                'code':           code,
                'first_seen':     scan_date,
                'last_seen':      scan_date,
                'first_close':    snap['close'],
                'last_close':     snap['close'],
                'last_pct':       snap['day_pct'],
                'streak_days':    1,
                'limit_up_days':  1,
            }
            pool[code]  = new_entry
            added.append(dict(new_entry))

    save_db(pool, scan_date)

    # ── 排序 ──────────────────────────────────────────────────────────────────
    added.sort(key=lambda x: -x['last_pct'])
    removed.sort(key=lambda x: x['remove_pct'])
    renewed.sort(key=lambda x: -x['streak_days'])

    # 完整池（按首次入池日期降序，新的在前）
    pool_list = sorted(pool.values(), key=lambda x: x['first_seen'], reverse=True)

    # ── 输出 ──────────────────────────────────────────────────────────────────
    lines = []
    def out(s=''):
        lines.append(s)
        print(s)

    day_tag = '昨天' if DAYS_BACK == 1 else (f'前{DAYS_BACK}天' if DAYS_BACK > 1 else '今天')

    out('=' * 80)
    out(f'【涨停强势股跟踪池】  数据日期：{scan_date}（{day_tag}）')
    out(f'池中总计：{len(pool)} 只  |  本次新增：{len(added)} 只  连板：{len(renewed)} 只  移出：{len(removed)} 只')
    out('=' * 80)

    # ── 完整池（最上方，方便直接看） ──
    out()
    out(f'▶ 当前完整股票池  共 {len(pool_list)} 只  （按入池时间倒序）')
    out('  ' + '─' * 64)
    out(f'  {"排":>2}  {"代码":<10}  {"最新收":>7}  {"今日%":>7}  {"连板":>4}  {"入池日"}')
    out('  ' + '─' * 64)

    for idx, r in enumerate(pool_list, 1):
        snap    = today_snap.get(r['code'])
        cur_pct = snap['day_pct'] if snap else 0.0
        cur_cls = snap['close']   if snap else r['last_close']
        streak  = r.get('streak_days', 1)
        streak_s = f'{streak}连板' if streak > 1 else '  首板'
        out(f'  {idx:>2}  {r["code"]:<10}  {cur_cls:>7.2f}  '
            f'{cur_pct:>+6.2f}%  {streak_s}  {r["first_seen"]}')

    # ── 变化明细 ──────────────────────────────────────────────────────────────
    out()
    out('─' * 80)
    out('  【本次变化明细】')
    out('─' * 80)

    # ── 新增 ──
    if added:
        out()
        out(f'▶ 今日新入池（涨停首次入池）  共 {len(added)} 只')
        out('  ' + '─' * 56)
        out(f'  {"排":>2}  {"代码":<10}  {"收盘":>7}  {"涨跌%":>7}  {"入池日"}')
        out('  ' + '─' * 56)
        for idx, r in enumerate(added, 1):
            out(f'  {idx:>2}  {r["code"]:<10}  {r["last_close"]:>7.2f}  '
                f'{r["last_pct"]:>+6.2f}%  {r["first_seen"]}')

    # ── 连板 ──
    if renewed:
        out()
        out(f'▶ 连板（已在池中，再次涨停）  共 {len(renewed)} 只')
        out('  ' + '─' * 64)
        out(f'  {"排":>2}  {"代码":<10}  {"收盘":>7}  {"涨跌%":>7}  {"连板天":>5}  {"首次入池"}')
        out('  ' + '─' * 64)
        for idx, r in enumerate(renewed, 1):
            out(f'  {idx:>2}  {r["code"]:<10}  {r["last_close"]:>7.2f}  '
                f'{r["last_pct"]:>+6.2f}%  {r["streak_days"]:>4}天  {r["first_seen"]}')

    # ── 移出 ──
    if removed:
        out()
        out(f'▶ 今日移出（下跌被踢）  共 {len(removed)} 只')
        out('  ' + '─' * 76)
        out(f'  {"排":>2}  {"代码":<10}  {"今日收":>7}  {"今日%":>7}  {"首次入池"}  {"持续天":>5}  原因')
        out('  ' + '─' * 76)
        for idx, r in enumerate(removed, 1):
            hold_days = (datetime.strptime(r['remove_date'], '%Y-%m-%d') -
                         datetime.strptime(r['first_seen'],  '%Y-%m-%d')).days
            reason = r.get('remove_reason', '下跌')
            out(f'  {idx:>2}  {r["code"]:<10}  {r["remove_close"]:>7.2f}  '
                f'{r["remove_pct"]:>+6.2f}%  {r["first_seen"]}  {hold_days:>4}天  [{reason}]')

    out()
    out(f'  扫描完成  日期：{scan_date}  池：{len(pool)} 只  '
        f'新增：{len(added)}  连板：{len(renewed)}  移出：{len(removed)}')
    out(f'  文件：{TXT_PATH}')

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(TXT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    scan()
