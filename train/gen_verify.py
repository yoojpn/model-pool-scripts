# Synthetic verified-habit trajectories: inspect input -> write -> run -> independent cross-check -> [mismatch -> targeted edit -> re-run/re-check] -> honest report.
# Families are disjoint from the evaluation families (eval16, treecount/cfgedit/bugfix/csvagg, held_*, jsonsel, logcount, func).
# Tool outputs come from real execution (toolrun_ctr.py). "bad" first attempts are masked from the loss (context only).
import sys, os, re, json, random, subprocess, tempfile, shutil
out, N, SEED = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
TOOLRUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'runner', 'toolrun_ctr.py')
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))
def tool(ws, name, args):
    p = subprocess.run(['python3', TOOLRUN, ws], input=json.dumps({'name': name, 'args': args}), capture_output=True, text=True, timeout=120)
    return json.loads(p.stdout)
W = ['apple', 'River', 'stone', 'Cloud', 'maple', 'tiger', 'Lamp', 'garden', 'Rocket', 'pencil', 'window', 'Forest', 'candle', 'Harbor', 'violet', 'copper', 'meadow', 'Anchor']
# each family: fn(rng) -> dict(setup, good, flaw=(good_line,bad_line), out, ref(setup)->str, check, req_en, req_ja)
def f_wordfreq(r):
    n = r.randint(2, 4); words = [r.choice(W[:7]) for _ in range(r.randint(18, 30))]
    txt = ' '.join(w.upper() if r.random() < .25 else w for w in words)
    txt = re.sub(r'(\S+ \S+ \S+) ', lambda m: m.group(1) + ', ', txt, count=3) + '\n'
    good = f"import re, collections\nt = open('text.txt').read().lower()\nc = collections.Counter(re.findall(r\"[a-z']+\", t))\nr = sorted(c.items(), key=lambda x: (-x[1], x[0]))[:{n}]\nopen('top.txt', 'w').write(''.join(f'{{w}} {{k}}\\n' for w, k in r))\n"
    flaw = (f"r = sorted(c.items(), key=lambda x: (-x[1], x[0]))[:{n}]", f"r = c.most_common({n})") if r.random() < .5 else ("t = open('text.txt').read().lower()", "t = open('text.txt').read()")
    def ref(s):
        c = {}
        for w in re.findall(r"[a-z']+", s['text.txt'].lower()): c[w] = c.get(w, 0) + 1
        return ''.join(f'{w} {k}\n' for w, k in sorted(c.items(), key=lambda x: (-x[1], x[0]))[:n])
    return dict(setup={'text.txt': txt}, good=good, flaw=flaw, out='top.txt', ref=ref,
        check=f"cat top.txt; echo ---; tr -cs \"a-zA-Z'\" '\\n' < text.txt | tr A-Z a-z | sort | uniq -c | sort -k1,1nr -k2,2 | head -{n + 2}",
        req_en=f"text.txt contains words. Write solve.py that writes the {n} most frequent words (case-insensitive, letters and apostrophes only) to top.txt, one per line as '<word> <count>', most frequent first, ties in alphabetical order. Run it.",
        req_ja=f"text.txt に単語が入っています。大文字小文字を区別せず(英字とアポストロフィのみ)、出現数の多い上位{n}語を top.txt に「単語 回数」の形式で1行ずつ、多い順、同数は辞書順で書く solve.py を作って実行してください。")
def f_dedupe(r):
    ls = [r.choice(['beta', 'alpha', 'gamma', 'delta', 'zeta', 'eta']) for _ in range(r.randint(10, 16))]
    ls = [(' ' * r.randint(0, 1)) + l + (' ' * r.randint(0, 1)) if r.random() < .3 else l for l in ls]
    for _ in range(2): ls.insert(r.randint(0, len(ls)), '')
    good = "seen = set(); res = []\nfor l in open('lines.txt'):\n    l = l.strip()\n    if l and l not in seen:\n        seen.add(l); res.append(l)\nopen('unique.txt', 'w').write(''.join(x + '\\n' for x in res))\n"
    flaw = ("        seen.add(l); res.append(l)", "        seen.add(l); res.append(l)\nres.sort()") if r.random() < .6 else ("    l = l.strip()", "    l = l.rstrip('\\n')")
    def ref(s):
        seen = [];
        for l in s['lines.txt'].split('\n'):
            l = l.strip()
            if l and l not in seen: seen.append(l)
        return ''.join(x + '\n' for x in seen)
    return dict(setup={'lines.txt': '\n'.join(ls) + '\n'}, good=good, flaw=flaw, out='unique.txt', ref=ref,
        check="cat -A lines.txt | head -20; echo ---; cat unique.txt",
        req_en="lines.txt has lines (some repeated, some blank, some with stray spaces). Write solve.py that writes the distinct lines to unique.txt: trimmed, blank lines dropped, keeping the order of first appearance. Run it.",
        req_ja="lines.txt に重複・空行・余分な空白のある行があります。前後の空白を除き、空行を捨て、最初に出た順序のまま重複を除いた行を unique.txt に書く solve.py を作って実行してください。")
def f_csvjoin(r):
    names = {i: r.choice(['Aki', 'Bo', 'Chie', 'Dan', 'Emi', 'Fuji']) + str(i) for i in range(1, 6)}
    ids = [i for i in names if r.random() < .8]; orders = [(100 + k, r.choice(ids + [9]), r.randint(5, 90)) for k in range(r.randint(6, 9))]
    good = "import csv\nnm = {r['cust_id']: r['name'] for r in csv.DictReader(open('custs.csv'))}\nw = csv.writer(open('out.csv', 'w', newline=''))\nw.writerow(['id', 'name', 'amt'])\nfor r in csv.DictReader(open('orders.csv')):\n    w.writerow([r['id'], nm.get(r['cust_id'], ''), r['amt']])\n"
    flaw = ("    w.writerow([r['id'], nm.get(r['cust_id'], ''), r['amt']])", "    if r['cust_id'] in nm: w.writerow([r['id'], nm[r['cust_id']], r['amt']])")
    def ref(s):
        nm = {}
        for l in s['custs.csv'].split('\n')[1:]:
            if l: a, b = l.split(','); nm[a] = b
        o = ['id,name,amt']
        for l in s['orders.csv'].split('\n')[1:]:
            if l: i, c, a = l.split(','); o.append(f'{i},{nm.get(c, "")},{a}')
        return '\n'.join(o) + '\n'
    return dict(setup={'orders.csv': 'id,cust_id,amt\n' + ''.join(f'{a},{b},{c}\n' for a, b, c in orders), 'custs.csv': 'cust_id,name\n' + ''.join(f'{i},{names[i]}\n' for i in ids)}, good=good, flaw=flaw, out='out.csv', ref=ref,
        check="wc -l orders.csv out.csv; cat orders.csv; echo ---; cat out.csv",
        req_en="orders.csv (id,cust_id,amt) and custs.csv (cust_id,name). Write solve.py that writes out.csv with header id,name,amt: every order in its original order with the customer's name (empty if the customer is unknown). Run it.",
        req_ja="orders.csv (id,cust_id,amt) と custs.csv (cust_id,name) があります。すべての注文を元の順序のまま、顧客名つき(顧客不明なら空)で、ヘッダ id,name,amt の out.csv に書く solve.py を作って実行してください。")
def f_jsonmerge(r):
    def d(): return {'name': r.choice(['x', 'y']), 'opts': {'a': r.randint(1, 3), 'b': {'c': r.randint(1, 3)}}, 'tags': [r.choice('pqr')]}
    A = d(); B = {'opts': {'b': {'d': 7}, 'e': 5}, 'tags': [r.choice('stu')]}
    good = "import json\ndef m(a, b):\n    for k, v in b.items():\n        if isinstance(v, dict) and isinstance(a.get(k), dict): m(a[k], v)\n        elif isinstance(v, list) and isinstance(a.get(k), list): a[k] = a[k] + v\n        else: a[k] = v\n    return a\njson.dump(m(json.load(open('a.json')), json.load(open('b.json'))), open('merged.json', 'w'), sort_keys=True)\n"
    flaw = ("json.dump(m(json.load(open('a.json')), json.load(open('b.json'))), open('merged.json', 'w'), sort_keys=True)", "a = json.load(open('a.json')); a.update(json.load(open('b.json'))); json.dump(a, open('merged.json', 'w'), sort_keys=True)")
    def ref(s):
        def m(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict): m(a[k], v)
                elif isinstance(v, list) and isinstance(a.get(k), list): a[k] = a[k] + v
                else: a[k] = v
            return a
        return json.dumps(m(json.loads(s['a.json']), json.loads(s['b.json'])), sort_keys=True)
    return dict(setup={'a.json': json.dumps(A), 'b.json': json.dumps(B)}, good=good, flaw=flaw, out='merged.json', ref=ref,
        check="cat a.json; echo; cat b.json; echo; cat merged.json; echo",
        req_en="a.json and b.json hold JSON objects. Write solve.py that deep-merges b into a (nested objects merged recursively, lists concatenated a then b, otherwise b wins) and saves it to merged.json with sorted keys. Run it.",
        req_ja="a.json と b.json に JSON オブジェクトがあります。b を a に深くマージ(入れ子のオブジェクトは再帰、リストは a の後ろに b を連結、それ以外は b 優先)し、キーをソートして merged.json に保存する solve.py を作って実行してください。")
def f_intervals(r):
    sp = []
    for _ in range(r.randint(5, 8)):
        a = r.randint(0, 30); sp.append((a, a + r.randint(1, 5)))
    sp.append((sp[0][1], sp[0][1] + 2))
    r.shuffle(sp)
    good = "iv = sorted(tuple(map(int, l.split())) for l in open('spans.txt') if l.strip())\nres = []\nfor a, b in iv:\n    if res and a <= res[-1][1]:\n        res[-1][1] = max(res[-1][1], b)\n    else:\n        res.append([a, b])\nopen('merged.txt', 'w').write(''.join(f'{a} {b}\\n' for a, b in res))\n"
    flaw = ("    if res and a <= res[-1][1]:", "    if res and a < res[-1][1]:")
    def ref(s):
        iv = sorted(tuple(map(int, l.split())) for l in s['spans.txt'].split('\n') if l.strip()); res = []
        for a, b in iv:
            if res and a <= res[-1][1]: res[-1][1] = max(res[-1][1], b)
            else: res.append([a, b])
        return ''.join(f'{a} {b}\n' for a, b in res)
    return dict(setup={'spans.txt': ''.join(f'{a} {b}\n' for a, b in sp)}, good=good, flaw=flaw, out='merged.txt', ref=ref,
        check="sort -n spans.txt; echo ---; cat merged.txt",
        req_en="spans.txt has one 'start end' integer pair per line, unsorted. Write solve.py that merges overlapping or touching spans (end equal to the next start counts as touching) and writes the result sorted to merged.txt in the same format. Run it.",
        req_ja="spans.txt に「開始 終了」の整数組が1行ずつ(順不同)あります。重なる区間と接する区間(終了が次の開始と等しい)を結合し、昇順で同じ形式で merged.txt に書く solve.py を作って実行してください。")
def f_rpn(r):
    ops = []
    for _ in range(r.randint(5, 7)):
        a, b = r.randint(-20, 20), r.choice([-7, -3, 2, 3, 5]); ops.append(f"{a} {b} {r.choice(['/', '/', '+', '*', '-'])}")
    ops.append('-7 2 /')
    good = "res = []\nfor l in open('exprs.txt'):\n    if not l.strip(): continue\n    st = []\n    for t in l.split():\n        if t in '+-*/' and len(t) == 1:\n            b, a = st.pop(), st.pop()\n            st.append({'+': a + b, '-': a - b, '*': a * b, '/': int(a / b)}[t])\n        else: st.append(int(t))\n    res.append(st[-1])\nopen('results.txt', 'w').write(''.join(f'{x}\\n' for x in res))\n"
    flaw = ("'/': int(a / b)}[t])", "'/': a // b}[t])")
    def ref(s):
        o = []
        for l in s['exprs.txt'].split('\n'):
            if not l.strip(): continue
            st = []
            for t in l.split():
                if t in '+-*/' and len(t) == 1:
                    b, a = st.pop(), st.pop(); st.append({'+': a + b, '-': a - b, '*': a * b, '/': int(a / b)}[t])
                else: st.append(int(t))
            o.append(st[-1])
        return ''.join(f'{x}\n' for x in o)
    return dict(setup={'exprs.txt': '\n'.join(ops) + '\n'}, good=good, flaw=flaw, out='results.txt', ref=ref,
        check="paste -d'=' exprs.txt results.txt",
        req_en="exprs.txt has one reverse-polish expression per line (integers and + - * /). Write solve.py that evaluates each and writes one result per line to results.txt. Division is integer division truncating toward zero. Run it.",
        req_ja="exprs.txt に逆ポーランド記法の式(整数と + - * /)が1行ずつあります。各式を計算して results.txt に1行ずつ書く solve.py を作って実行してください。除算は0方向への切り捨て整数除算です。")
def f_islands(r):
    n, m = 6, 7; g = [[1 if r.random() < .4 else 0 for _ in range(m)] for _ in range(n)]
    g[0][0] = 1; g[1][1] = 1; g[0][1] = 0; g[1][0] = 0
    good = "g = [l.strip() for l in open('grid.txt') if l.strip()]\nseen = set(); n = 0\nfor i in range(len(g)):\n    for j in range(len(g[0])):\n        if g[i][j] == '1' and (i, j) not in seen:\n            n += 1; st = [(i, j)]\n            while st:\n                x, y = st.pop()\n                if (x, y) in seen: continue\n                seen.add((x, y))\n                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):\n                    a, b = x + dx, y + dy\n                    if 0 <= a < len(g) and 0 <= b < len(g[0]) and g[a][b] == '1': st.append((a, b))\nopen('count.txt', 'w').write(f'{n}\\n')\n"
    flaw = ("                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):", "                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):")
    def ref(s):
        gg = [l.strip() for l in s['grid.txt'].split('\n') if l.strip()]; seen = set(); n = 0
        for i in range(len(gg)):
            for j in range(len(gg[0])):
                if gg[i][j] == '1' and (i, j) not in seen:
                    n += 1; st = [(i, j)]
                    while st:
                        x, y = st.pop()
                        if (x, y) in seen: continue
                        seen.add((x, y))
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                            a, b = x + dx, y + dy
                            if 0 <= a < len(gg) and 0 <= b < len(gg[0]) and gg[a][b] == '1': st.append((a, b))
        return f'{n}\n'
    return dict(setup={'grid.txt': '\n'.join(''.join(map(str, row)) for row in g) + '\n'}, good=good, flaw=flaw, out='count.txt', ref=ref,
        check="cat grid.txt; echo ---; cat count.txt",
        req_en="grid.txt is a grid of 0 and 1 characters. Write solve.py that counts the islands of 1s (cells are connected only horizontally or vertically, not diagonally) and writes the number to count.txt. Run it.",
        req_ja="grid.txt は 0 と 1 の文字の格子です。1 の島の数(縦横の隣接のみで連結、斜めは連結しない)を数えて count.txt に書く solve.py を作って実行してください。")
def f_timegap(r):
    base = r.randint(1, 20); ts = sorted(r.sample(range(0, 3600, 7), r.randint(5, 8)))
    ev = [f"2024-03-0{base % 9 + 1}T{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d} {r.choice(['start', 'tick', 'stop'])}" for t in ts]
    r.shuffle(ev)
    good = "from datetime import datetime\nts = sorted(datetime.fromisoformat(l.split()[0]) for l in open('events.log') if l.strip())\ng = max((b - a).total_seconds() for a, b in zip(ts, ts[1:]))\nopen('gap.txt', 'w').write(f'{int(g)}\\n')\n"
    flaw = ("ts = sorted(datetime.fromisoformat(l.split()[0]) for l in open('events.log') if l.strip())", "ts = [datetime.fromisoformat(l.split()[0]) for l in open('events.log') if l.strip()]")
    def ref(s):
        from datetime import datetime
        t = sorted(datetime.fromisoformat(l.split()[0]) for l in s['events.log'].split('\n') if l.strip())
        return f'{int(max((b - a).total_seconds() for a, b in zip(t, t[1:])))}\n'
    return dict(setup={'events.log': '\n'.join(ev) + '\n'}, good=good, flaw=flaw, out='gap.txt', ref=ref,
        check="sort events.log; echo ---; cat gap.txt",
        req_en="events.log has lines '<ISO timestamp> <name>' in no particular order. Write solve.py that finds the largest gap in seconds between two chronologically consecutive events and writes that integer to gap.txt. Run it.",
        req_ja="events.log に「ISO形式の時刻 名前」の行が順不同で並んでいます。時系列で隣り合う2イベント間の最大の間隔(秒)を求め、その整数を gap.txt に書く solve.py を作って実行してください。")
def f_slug(r):
    ts = [r.choice(['Hello World', 'hello  world!', 'Rock & Roll', 'rock-and-roll', 'Cafe Menu', 'cafe menu ', 'Plan B', 'plan  b']) for _ in range(r.randint(5, 8))]
    good = "import re\nseen = {}; res = []\nfor l in open('titles.txt'):\n    if not l.strip(): continue\n    s = re.sub(r'[^a-z0-9]+', '-', l.lower()).strip('-')\n    seen[s] = seen.get(s, 0) + 1\n    res.append(s if seen[s] == 1 else f'{s}-{seen[s]}')\nopen('slugs.txt', 'w').write(''.join(x + '\\n' for x in res))\n"
    flaw = ("    res.append(s if seen[s] == 1 else f'{s}-{seen[s]}')", "    res.append(s)")
    def ref(s):
        seen = {}; res = []
        for l in s['titles.txt'].split('\n'):
            if not l.strip(): continue
            x = re.sub(r'[^a-z0-9]+', '-', l.lower()).strip('-'); seen[x] = seen.get(x, 0) + 1
            res.append(x if seen[x] == 1 else f'{x}-{seen[x]}')
        return ''.join(x + '\n' for x in res)
    return dict(setup={'titles.txt': '\n'.join(ts) + '\n'}, good=good, flaw=flaw, out='slugs.txt', ref=ref,
        check="paste -d'|' titles.txt slugs.txt",
        req_en="titles.txt has one title per line. Write solve.py that writes a slug per title to slugs.txt: lowercase, runs of non-alphanumerics become a single '-', no leading/trailing '-'. If a slug repeats, the 2nd gets '-2', the 3rd '-3', and so on. Run it.",
        req_ja="titles.txt に1行1タイトルあります。各タイトルのスラッグを slugs.txt に書く solve.py を作って実行してください。小文字化し、英数字以外の連続は1つの '-' にし、先頭と末尾の '-' は除きます。同じスラッグが重なったら2つ目に '-2'、3つ目に '-3' を付けます。")
def f_flatten(r):
    d = {'id': r.randint(1, 9), 'user': {'name': r.choice('xyz'), 'langs': [r.choice(['ja', 'en']), 'fr']}, 'meta': {'tags': [{'k': 1}], 'ok': True}}
    good = "import json\ndef fl(o, p=''):\n    if isinstance(o, dict):\n        r = {}\n        for k, v in o.items(): r.update(fl(v, f'{p}.{k}' if p else k))\n        return r\n    if isinstance(o, list):\n        r = {}\n        for i, v in enumerate(o): r.update(fl(v, f'{p}.{i}' if p else str(i)))\n        return r\n    return {p: o}\njson.dump(fl(json.load(open('nested.json'))), open('flat.json', 'w'), sort_keys=True)\n"
    flaw = ("    if isinstance(o, list):\n        r = {}\n        for i, v in enumerate(o): r.update(fl(v, f'{p}.{i}' if p else str(i)))\n        return r\n", "")
    def ref(s):
        def fl(o, p=''):
            if isinstance(o, dict):
                r = {}
                for k, v in o.items(): r.update(fl(v, f'{p}.{k}' if p else k))
                return r
            if isinstance(o, list):
                r = {}
                for i, v in enumerate(o): r.update(fl(v, f'{p}.{i}' if p else str(i)))
                return r
            return {p: o}
        return json.dumps(fl(json.loads(s['nested.json'])), sort_keys=True)
    return dict(setup={'nested.json': json.dumps(d)}, good=good, flaw=flaw, out='flat.json', ref=ref,
        check="cat nested.json; echo; cat flat.json; echo",
        req_en="nested.json holds nested JSON. Write solve.py that flattens it into one level in flat.json (sorted keys): nested object keys joined with '.', list items use their index, e.g. 'a.0.b'. Run it.",
        req_ja="nested.json に入れ子の JSON があります。1階層に平坦化して(キーをソートして) flat.json に保存する solve.py を作って実行してください。入れ子のキーは '.' で連結し、リストの要素は添字を使います(例 'a.0.b')。")
def f_wrap(r):
    W_ = r.randint(14, 20); words = [r.choice(['alpha', 'be', 'cat', 'doggo', 'elephant', 'fig', 'giraffe', 'hi']) for _ in range(r.randint(14, 22))]
    good = f"words = open('text.txt').read().split()\nlines = []; cur = ''\nfor w in words:\n    if not cur: cur = w\n    elif len(cur) + 1 + len(w) <= {W_}: cur += ' ' + w\n    else: lines.append(cur); cur = w\nif cur: lines.append(cur)\nopen('wrapped.txt', 'w').write(''.join(l + '\\n' for l in lines))\n"
    flaw = (f"    elif len(cur) + 1 + len(w) <= {W_}: cur += ' ' + w", f"    elif len(cur) + 1 + len(w) < {W_}: cur += ' ' + w")
    def ref(s):
        lines = []; cur = ''
        for w in s['text.txt'].split():
            if not cur: cur = w
            elif len(cur) + 1 + len(w) <= W_: cur += ' ' + w
            else: lines.append(cur); cur = w
        if cur: lines.append(cur)
        return ''.join(l + '\n' for l in lines)
    return dict(setup={'text.txt': ' '.join(words) + '\n'}, good=good, flaw=flaw, out='wrapped.txt', ref=ref,
        check="awk '{print length($0)\": \"$0}' wrapped.txt",
        req_en=f"text.txt has words. Write solve.py that re-wraps them into wrapped.txt greedily so that no line is longer than {W_} characters (a line of exactly {W_} is allowed) and words are never split. Run it.",
        req_ja=f"text.txt に単語が並んでいます。1行が{W_}文字を超えないよう(ちょうど{W_}文字は可)、単語を分割せず貪欲に折り返して wrapped.txt に書く solve.py を作って実行してください。")
def f_balance(r):
    accs = ['cash', 'bank', 'card']; rows = [(f'2024-01-{i + 1:02d}', r.choice(accs), round(r.uniform(-40, 90), 2)) for i in range(r.randint(7, 10))]
    good = "import csv, json\ns = {}\nfor r in csv.DictReader(open('ledger.csv')):\n    s[r['account']] = round(s.get(r['account'], 0) + float(r['amount']), 2)\njson.dump(s, open('balances.json', 'w'), sort_keys=True)\n"
    flaw = ("float(r['amount'])", "int(float(r['amount']))")
    def ref(s):
        t = {}
        for l in s['ledger.csv'].split('\n')[1:]:
            if l: d, a, m = l.split(','); t[a] = round(t.get(a, 0) + float(m), 2)
        return json.dumps(t, sort_keys=True)
    return dict(setup={'ledger.csv': 'date,account,amount\n' + ''.join(f'{d},{a},{m}\n' for d, a, m in rows)}, good=good, flaw=flaw, out='balances.json', ref=ref,
        check="cat balances.json; echo; awk -F, 'NR>1{s[$2]+=$3}END{for(k in s)printf \"%s %.2f\\n\", k, s[k]}' ledger.csv",
        req_en="ledger.csv has date,account,amount (amounts may be negative and have cents). Write solve.py that totals the amounts per account (rounded to 2 decimals) into balances.json (sorted keys). Run it.",
        req_ja="ledger.csv に date,account,amount があります(金額は負やセント付きもあり)。口座ごとの合計(小数2桁に丸め)を balances.json(キーはソート)に書く solve.py を作って実行してください。")

# ---- edit-existing-code families: read first, targeted edit, run visible tests, probe the spec's edge cases, fix if needed
def e_page(r):
    nm = r.choice(['page', 'get_page', 'paginate']); sz = r.choice(['size', 'per_page'])
    mod = f"def {nm}(items, n, {sz}):\n    start = n * {sz}\n    return items[start:start + {sz}]\n"
    test = f"from mod import {nm}\nassert {nm}(list(range(10)), 1, 3) == [0, 1, 2]\nassert {nm}(list(range(10)), 2, 3) == [3, 4, 5]\nprint('visible ok')\n"
    old = f"    start = n * {sz}\n"; good = f"    if n < 1:\n        raise ValueError('n must be >= 1')\n    start = (n - 1) * {sz}\n"; flaw = f"    start = (n - 1) * {sz}\n"
    hv = f"from mod import {nm}\nassert {nm}(list(range(10)), 4, 3) == [9]\nassert {nm}(list(range(10)), 5, 3) == []\ntry:\n    {nm}([1], 0, 2); raise SystemExit('no error for n=0')\nexcept ValueError: pass\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}(list(range(10)), 4, 3), {nm}(list(range(10)), 5, 3))\ntry:\n    {nm}([1], 0, 2); print('n=0: no error')\nexcept ValueError as e:\n    print('n=0: ValueError', e)\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"mod.py has `{nm}(items, n, {sz})` which should return page n (1-based) of the items; it is off by one. Fix it so test_mod.py passes. Also, a page past the end must give [] and n < 1 must raise ValueError. Run the tests.",
        req_ja=f"mod.py の `{nm}(items, n, {sz})` は items の n ページ目(1始まり)を返すはずですが1つずれています。test_mod.py が通るよう直してください。範囲を超えたページは [] を返し、n < 1 は ValueError にします。テストを実行してください。")
def e_mean(r):
    nm = r.choice(['avg_nonempty', 'mean_of_groups', 'group_mean'])
    mod = f"def {nm}(groups):\n    vals = [sum(g) / len(g) for g in groups]\n    return sum(vals) / len(vals)\n"
    test = f"from mod import {nm}\nassert {nm}([[1, 3], [5]]) == 3.5\nprint('visible ok')\n"
    old = "    vals = [sum(g) / len(g) for g in groups]\n    return sum(vals) / len(vals)\n"
    good = "    vals = [sum(g) / len(g) for g in groups if g]\n    return sum(vals) / len(vals) if vals else 0.0\n"; flaw = "    vals = [sum(g) / len(g) for g in groups if g]\n    return sum(vals) / len(vals)\n"
    hv = f"from mod import {nm}\nassert {nm}([[], [2, 4]]) == 3.0\nassert {nm}([[], []]) == 0.0\nassert {nm}([]) == 0.0\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}([[], [2, 4]])); print({nm}([[], []]))\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"`{nm}(groups)` in mod.py crashes when a group is empty. Make it ignore empty groups, and return 0.0 when there is nothing to average. Keep test_mod.py passing and run it.",
        req_ja=f"mod.py の `{nm}(groups)` は空のグループがあると落ちます。空のグループは無視し、平均する対象がなければ 0.0 を返すようにしてください。test_mod.py が通ることも確認し、実行してください。")
def e_phone(r):
    nm = r.choice(['normalize_phone', 'clean_phone'])
    mod = f"import re\ndef {nm}(s):\n    return re.sub(r'\\D', '', s)\n"
    test = f"from mod import {nm}\nassert {nm}('090-1234-5678') == '09012345678'\nprint('visible ok')\n"
    old = "    return re.sub(r'\\D', '', s)\n"
    good = "    d = re.sub(r'\\D', '', s)\n    if d.startswith('81') and len(d) == 12:\n        d = '0' + d[2:]\n    return d if len(d) in (10, 11) else None\n"; flaw = "    d = re.sub(r'\\D', '', s)\n    if d.startswith('81') and len(d) == 12:\n        d = '0' + d[2:]\n    return d\n"
    hv = f"from mod import {nm}\nassert {nm}('+81 90 1234 5678') == '09012345678'\nassert {nm}('123') is None\nassert {nm}('03-1234-5678') == '0312345678'\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}('+81 90 1234 5678'), {nm}('123'), {nm}('03-1234-5678'))\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"`{nm}(s)` in mod.py only strips non-digits. Also convert a leading +81 (country code, 12 digits in total) to a leading 0, and return None unless the result has 10 or 11 digits. Keep test_mod.py passing and run it.",
        req_ja=f"mod.py の `{nm}(s)` は数字以外を除くだけです。先頭の +81(国番号、合計12桁)は先頭の 0 に直し、結果が10桁か11桁でなければ None を返すようにしてください。test_mod.py も通し、実行してください。")
def e_dur(r):
    nm = r.choice(['fmt_duration', 'format_secs'])
    mod = f"def {nm}(sec):\n    h, rem = divmod(sec, 3600)\n    m, s = divmod(rem, 60)\n    return f'{{h}}h{{m:02d}}m{{s:02d}}s'\n"
    test = f"from mod import {nm}\nassert {nm}(3723) == '1h02m03s'\nprint('visible ok')\n"
    old = "    return f'{h}h{m:02d}m{s:02d}s'\n"
    good = "    if h == 0:\n        return f'{m}m{s:02d}s' if m else f'{s}s'\n    return f'{h}h{m:02d}m{s:02d}s'\n"; flaw = "    if h == 0:\n        return f'{m}m{s:02d}s'\n    return f'{h}h{m:02d}m{s:02d}s'\n"
    hv = f"from mod import {nm}\nassert {nm}(125) == '2m05s'\nassert {nm}(42) == '42s'\nassert {nm}(3600) == '1h00m00s'\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}(125), {nm}(42), {nm}(3600))\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"`{nm}(sec)` in mod.py always prints hours. Change it so the hours part is omitted when it is 0, and when there are also no minutes only seconds are shown (e.g. '42s', '2m05s'). Keep test_mod.py passing and run it.",
        req_ja=f"mod.py の `{nm}(sec)` は常に時間を出力します。時間が0なら時間を省き、分も0なら秒だけ('42s'、'2m05s' のように)にしてください。test_mod.py も通し、実行してください。")
def e_topk(r):
    nm = r.choice(['top_k', 'best_k'])
    mod = f"def {nm}(d, k):\n    return [key for key, _ in sorted(d.items(), key=lambda x: -x[1])[:k]]\n"
    test = f"from mod import {nm}\nassert {nm}({{'a': 3, 'b': 5, 'c': 1}}, 2) == ['b', 'a']\nprint('visible ok')\n"
    old = "key=lambda x: -x[1])"
    good = "key=lambda x: (-x[1], x[0]))"; flaw = "key=lambda x: (-x[1],))"
    hv = f"from mod import {nm}\nassert {nm}({{'z': 2, 'a': 2, 'm': 2, 'q': 9}}, 3) == ['q', 'a', 'm']\nassert {nm}({{}}, 3) == []\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}({{'z': 2, 'a': 2, 'm': 2, 'q': 9}}, 3))\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"`{nm}(d, k)` in mod.py returns the keys of the k largest values, but equal values come out in arbitrary order. Make ties come out in alphabetical order of the key. Keep test_mod.py passing and run it.",
        req_ja=f"mod.py の `{nm}(d, k)` は値の大きい上位k個のキーを返しますが、同値のときの順序が不定です。同値はキーの辞書順にしてください。test_mod.py も通し、実行してください。")
def e_chunk(r):
    nm = r.choice(['chunk', 'split_chunks'])
    mod = f"def {nm}(seq, n):\n    return [seq[i:i + n] for i in range(0, len(seq) - n, n)]\n"
    test = f"from mod import {nm}\nassert {nm}([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]\nprint('visible ok')\n"
    old = "range(0, len(seq) - n, n)"
    good = "range(0, len(seq), n)"; flaw = "range(0, len(seq) - n + 1, n)"
    hv = f"from mod import {nm}\nassert {nm}([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\nassert {nm}([], 3) == []\nassert {nm}([1], 3) == [[1]]\n"
    chk = f"python3 test_mod.py && python3 -c \"from mod import {nm}; print({nm}([1, 2, 3, 4, 5], 2), {nm}([1], 3))\""
    return dict(setup={'mod.py': mod, 'test_mod.py': test}, file='mod.py', old=old, good=good, flaw=flaw, hv=hv, check=chk,
        req_en=f"`{nm}(seq, n)` in mod.py drops items at the end. It must return every item: all chunks of size n plus a shorter last chunk if needed. Keep test_mod.py passing and run it.",
        req_ja=f"mod.py の `{nm}(seq, n)` は末尾の要素を落とします。すべての要素を、n個ずつのかたまりと(必要なら)短い最後のかたまりで返すようにしてください。test_mod.py も通し、実行してください。")
EFAMS = [e_page, e_mean, e_phone, e_dur, e_topk, e_chunk]
def run_cmd(ws, cmd):
    return subprocess.run(cmd, shell=True, cwd=ws, capture_output=True, text=True, timeout=30)
def edit_variant(T, which):
    s = dict(T['setup']); a = T['file']
    new = T['good'] if which == 'good' else T['flaw']
    assert s[a].count(T['old']) == 1
    s[a] = s[a].replace(T['old'], new); return s
def edit_valid(T):
    for which, want_hv in (('good', True), ('flaw', False), ('orig', False)):
        s = T['setup'] if which == 'orig' else edit_variant(T, which)
        ws = tempfile.mkdtemp(prefix='e')
        for p, c in s.items(): open(os.path.join(ws, p), 'w').write(c)
        open(os.path.join(ws, '_hv.py'), 'w').write(T['hv'])
        vis = run_cmd(ws, 'python3 test_mod.py').returncode == 0; hv = run_cmd(ws, 'python3 _hv.py').returncode == 0; shutil.rmtree(ws)
        if which != 'orig' and not vis: return False
        if hv != want_hv: return False
    return True
def make_edit(fam, r, f_out, n_id):
    T = fam(r)
    if not edit_valid(T): return False
    use_bad = r.random() < .55; ja = r.random() < .4
    user = (T['req_ja'] if ja else T['req_en']) + '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i + 1}. {p}' for i, p in enumerate(PLAN_E))
    ws = tempfile.mkdtemp(prefix='e')
    for p, c in T['setup'].items(): open(os.path.join(ws, p), 'w').write(c)
    msgs = [{'role': 'user', 'content': user}]; cid = [0]
    def call(name, args, bad_=False):
        cid[0] += 1; i = f'call_{cid[0]}'; res = tool(ws, name, args)
        msgs.append({'bad': bad_, 'role': 'assistant', 'content': '', 'tool_calls': [{'id': i, 'type': 'function', 'function': {'name': name, 'arguments': J(args)}}]})
        msgs.append({'role': 'tool', 'tool_call_id': i, 'name': name, 'content': J(res)}); return res
    try:
        call('list_dir', {'path': '.'}); call('read_file', {'path': T['file']})
        if r.random() < .6: call('read_file', {'path': 'test_mod.py'})
        o = call('edit_file', {'path': T['file'], 'old': T['old'], 'new': T['flaw'] if use_bad else T['good']}, bad_=use_bad)
        if not o.get('ok'): raise RuntimeError('edit failed')
        o = call('bash', {'command': T['check']})
        if o.get('exit_code') != 0 and not use_bad: raise RuntimeError('check failed on good')
        if use_bad:
            o = call('edit_file', {'path': T['file'], 'old': T['flaw'], 'new': T['good']})
            if not o.get('ok'): raise RuntimeError('fix failed')
            o = call('bash', {'command': T['check']})
            if o.get('exit_code') != 0: raise RuntimeError('recheck failed')
        open(os.path.join(ws, '_hv.py'), 'w').write(T['hv'])
        if run_cmd(ws, 'python3 _hv.py').returncode != 0: raise RuntimeError('hidden check failed')
        fx_ja = '最初の修正は仕様の端の例で期待と食い違ったため、その部分を直して再実行しました。'; fx_en = 'My first edit gave an unexpected result on an edge case from the requirements, so I fixed that part and re-ran. '
        if ja: final = (fx_ja if use_bad else '') + f"`{T['file']}` を直し、`test_mod.py` と、要件の端の例(出力を目視で要件と照合)を実行しました。見た範囲では要件どおりです。それ以外の入力は試していません。"
        else: final = (fx_en if use_bad else '') + f"I edited `{T['file']}`, ran `test_mod.py`, and ran the edge cases from the requirements, comparing the printed output with them. They match; other inputs are untested."
        msgs.append({'role': 'assistant', 'content': final})
        f_out.write(json.dumps({'name': f"e-{fam.__name__[2:]}-{n_id}", 'prompt': user, 'pass': True, 'messages': msgs}, ensure_ascii=False) + '\n'); return True
    except Exception as e:
        print('eskip', fam.__name__, str(e)[:60]); return False
    finally: shutil.rmtree(ws, ignore_errors=True)
PLAN_E = ['Read the file to change (and its tests).', 'Make a small, targeted edit.', 'Run the tests, then probe the edge cases named in the request and read the printed output.', 'Fix any mismatch, re-run, and report what was and was not verified.']
FAMS = [f_wordfreq, f_dedupe, f_csvjoin, f_jsonmerge, f_intervals, f_rpn, f_islands, f_timegap, f_slug, f_flatten, f_wrap, f_balance]
PLAN = ['Inspect the input file(s).', 'Write solve.py that produces the requested output.', 'Run it, then cross-check the output against the input with an independent command and read the result.', 'Fix any mismatch with a small edit, re-run, and report what was and was not verified.']
def apply_flaw(good, flaw):
    a, b = flaw
    return good.replace(a, b) if a in good and good.count(a) == 1 else None
def run_sol(setup, code):
    ws = tempfile.mkdtemp(prefix='v')
    for p, c in setup.items(): open(os.path.join(ws, p), 'w').write(c)
    open(os.path.join(ws, 'solve.py'), 'w').write(code)
    p = subprocess.run('python3 solve.py', shell=True, cwd=ws, capture_output=True, text=True, timeout=20)
    return ws, p
n = 0; tries = 0; per = {}
rng0 = random.Random(SEED)
with open(out, 'w') as f:
    while n < N and tries < N * 6:
        tries += 1; fam = FAMS[tries % len(FAMS)]; r = random.Random(rng0.random())
        try: T = fam(r)
        except Exception as e: print('gen fail', fam.__name__, e); continue
        good, flaw = T['good'], T['flaw']; bad = apply_flaw(good, flaw)
        wsg, pg = run_sol(T['setup'], good)
        okg = pg.returncode == 0 and os.path.exists(os.path.join(wsg, T['out'])) and open(os.path.join(wsg, T['out'])).read() == T['ref'](T['setup']); shutil.rmtree(wsg)
        if not okg: print('good mismatch', fam.__name__); continue
        use_bad = r.random() < .55
        if use_bad:
            if bad is None: continue
            wsb, pb = run_sol(T['setup'], bad); okb = pb.returncode == 0 and open(os.path.join(wsb, T['out'])).read() == T['ref'](T['setup']) if os.path.exists(os.path.join(wsb, T['out'])) else False; shutil.rmtree(wsb)
            if okb: continue      # flaw must change the output on this instance
        ja = r.random() < .4
        user = (T['req_ja'] if ja else T['req_en']) + '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i + 1}. {p}' for i, p in enumerate(PLAN))
        ws = tempfile.mkdtemp(prefix='v')
        for p, c in T['setup'].items(): open(os.path.join(ws, p), 'w').write(c)
        msgs = [{'role': 'user', 'content': user}]; cid = [0]
        def call(name, args, bad_=False):
            cid[0] += 1; i = f'call_{cid[0]}'; res = tool(ws, name, args)
            msgs.append({'bad': bad_, 'role': 'assistant', 'content': '', 'tool_calls': [{'id': i, 'type': 'function', 'function': {'name': name, 'arguments': J(args)}}]})
            msgs.append({'role': 'tool', 'tool_call_id': i, 'name': name, 'content': J(res)}); return res
        try:
            files = list(T['setup'])
            if r.random() < .5: call('bash', {'command': 'ls -la && head -n 12 ' + ' '.join(files)})
            else:
                call('list_dir', {'path': '.'})
                call('read_file', {'path': files[0]})
            call('write_file', {'path': 'solve.py', 'content': bad if use_bad else good}, bad_=use_bad)
            o = call('bash', {'command': 'python3 solve.py'})
            if o.get('exit_code') != 0: raise RuntimeError('run failed')
            o = call('bash', {'command': T['check']})
            if use_bad:
                r2 = call('edit_file', {'path': 'solve.py', 'old': flaw[1], 'new': flaw[0]})
                if not r2.get('ok'):
                    # multi-line replacement: rewrite whole file instead
                    r2 = call('write_file', {'path': 'solve.py', 'content': good})
                    if not r2.get('ok'): raise RuntimeError('fix failed')
                o = call('bash', {'command': 'python3 solve.py && ' + T['check']})
                if o.get('exit_code') != 0: raise RuntimeError('recheck failed')
            if open(os.path.join(ws, T['out'])).read() != T['ref'](T['setup']): raise RuntimeError('final output wrong')
            fix_ja = '最初の版は独立した確認コマンドの出力と食い違ったため、該当箇所を直して再実行・再確認しました。' ; fix_en = 'My first version disagreed with the independent check, so I fixed that part, re-ran it and re-checked. '
            if ja: final = (fix_ja if use_bad else '') + f"`solve.py` を実行して `{T['out']}` を作り、入力を独立したコマンドで確認して出力が一致することを見ました。確認したのはこの入力のみで、他の入力での検証はしていません。"
            else: final = (fix_en if use_bad else '') + f"I ran `solve.py`, which wrote `{T['out']}`, and cross-checked the output against the input with an independent command; they agree. I only checked this input; other inputs are untested."
            msgs.append({'role': 'assistant', 'content': final})
            f.write(json.dumps({'name': f"v-{fam.__name__[2:]}-{n}", 'prompt': user, 'pass': True, 'messages': msgs}, ensure_ascii=False) + '\n'); n += 1; per[fam.__name__] = per.get(fam.__name__, 0) + 1
        except Exception as e:
            print('skip', fam.__name__, type(e).__name__, str(e)[:80])
        finally: shutil.rmtree(ws, ignore_errors=True)
print('built', n, 'tries', tries, per)
ne = 0
with open(out, 'a') as f:
    rng1 = random.Random(SEED + 1)
    att = 0
    while ne < int(os.environ.get('NEDIT', N // 2)) and att < 20000:
        fam = EFAMS[att % len(EFAMS)]; att += 1
        if make_edit(fam, random.Random(rng1.random()), f, ne): ne += 1
print('edit built', ne)

