# Hallucination metrics on bench jsonl (needs SAVE_MSGS=1 so that messages are present).
# 1 plan_unknown: path-like tokens in the plan that appear nowhere in the request / listing / tool outputs and are not created by the agent
# 2 bad_path_call: read_file/edit_file/list_dir calls whose result says the path does not exist
# 3 report_unsupported: backticked tokens in the final report that appear in no tool call or tool output or request
# 4 false_success: report claims success while the verifier failed
import json, re, sys
PATH = re.compile(r'[\w./-]+\.(?:py|json|csv|txt|md|log|ini|yaml|yml|sh|js|toml)\b')
def run(f):
    R = [json.loads(l) for l in open(f)]
    n = len(R); pu = pt = bp = fc = ru = rt = fs = 0
    for r in R:
        ms = r.get('messages') or []
        blob = r.get('prompt', '') + ' '
        wrote = set()
        for m in ms:
            if m.get('role') == 'tool': blob += str(m.get('content', '')) + ' '
            for c in m.get('tool_calls') or []:
                a = c['function']['arguments']; blob += a + ' '
                try: aa = json.loads(a)
                except Exception: aa = {}
                if c['function']['name'] == 'write_file' and aa.get('path'): wrote.add(aa['path'])
        for p in set(PATH.findall(' '.join(r.get('plan') or []))):
            pt += 1
            if p not in blob and p not in wrote and not re.search(r'(solve|test_)\w*\.py|result|out', p): pu += 1
        for c in r.get('calls', []):
            if c['tool'] in ('read_file', 'edit_file', 'list_dir'):
                fc += 1
                if re.search(r'not a file|not found|No such|does not exist|ENOENT', c.get('out', '') or ''): bp += 1
        for t in set(re.findall(r'`([^`\n]{2,60})`', r.get('final', ''))):
            rt += 1
            if t not in blob: ru += 1
        fs += bool(r.get('claimsSuccess'))
    pct = lambda a, b: f'{a}/{b} ({100 * a / b:.1f}%)' if b else '0/0'
    print(f, 'tasks', n, '| plan_unknown', pct(pu, pt), '| bad_path_call', pct(bp, fc), '| report_unsupported', pct(ru, rt), '| false_success', pct(fs, n))
for f in sys.argv[1:]: run(f)
