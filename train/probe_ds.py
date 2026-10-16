import json, sys, collections
from datasets import load_dataset
name, n = sys.argv[1], int(sys.argv[2])
ds = load_dataset(name, split='train', streaming=True)
rows = []; stats = collections.Counter(); tools = collections.Counter(); turns = []; chars = []
VER = None
for i, r in enumerate(ds):
    if i >= 6000: break
    stats['seen'] += 1
    if not r.get('resolved'): continue
    stats['resolved'] += 1
    tr = r['trajectory']
    if isinstance(tr, str): tr = json.loads(tr)
    nt = sum(1 for m in tr if m['role'] == 'assistant'); c = sum(len(json.dumps(m, ensure_ascii=False)) for m in tr)
    turns.append(nt); chars.append(c)
    for m in tr:
        for tc in (m.get('tool_calls') or []): tools[tc['function']['name']] += 1
    if len(rows) < n and nt <= 30 and c < 60000: rows.append({k: r[k] for k in ('instance_id', 'repo', 'trajectory', 'tools') if k in r})
print('stats', dict(stats)); print('tools', dict(tools))
import statistics as S
print('turns median', S.median(turns), 'p25', sorted(turns)[len(turns)//4], 'chars median', S.median(chars), 'short(<=30 turns,<60k chars):', sum(1 for t, c in zip(turns, chars) if t <= 30 and c < 60000), 'of', len(turns))
print('repos', collections.Counter(r['repo'] for r in rows).most_common(12))
with open('data2/sample_' + name.replace('/', '_') + '.jsonl', 'w') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
