# Build expert (oracle) agent trajectories from the gold patches of SWE-bench *train* split instances (disjoint from Verified).
# Tool outputs are produced by the real tool runner on a real checkout, so formats match the live harness.
# usage: gen_oracle.py REPO CAP SEED OUT.jsonl
import sys, os, re, json, random, subprocess, shutil, tempfile
from datasets import load_dataset
from unidiff import PatchSet
repo, cap, seed, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
TOOLRUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'runner', 'toolrun_ctr.py')
ds = load_dataset('princeton-nlp/SWE-bench', split='train')
rows = [r for r in ds if r['repo'] == repo]
random.Random(seed).shuffle(rows)
print(repo, 'train rows', len(rows), flush=True)
subprocess.run(['git', 'clone', '-q', f'https://github.com/{repo}.git', 'src'], check=True)

def tool(ws, name, args):
    p = subprocess.run(['python3', TOOLRUN, ws], input=json.dumps({'name': name, 'args': args}), capture_output=True, text=True, timeout=120)
    return json.loads(p.stdout)
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))
STOP = set('self None True False return import class from this that with have been will would should could error issue when then than they them there which while'.split())
PLAN = ["Search the codebase with grep for the identifiers or error messages named in the issue, to find the relevant source file.",
        "Read that source file around the match and work out the cause.",
        "Edit the existing source file (not the tests) with a minimal, exact change.",
        "Check the edited file (syntax check, or the tests if they can run) and report honestly what was and was not verified."]
HEAD = '次の GitHub issue を解決してください。カレントディレクトリ(/testbed)に {repo} のソースがあります。既存のテストファイルは変更しないでください。\n\n{issue}'
SAY_GREP = ['I will search the code for `{t}` to find where this happens.', 'Let me find the code that mentions `{t}`.', 'First I will locate `{t}` in the source.']
SAY_READ = ['Reading `{p}` around the match.', 'Let me look at the relevant part of `{p}`.', 'Opening `{p}` near the matching line.']
SAY_EDIT = ['This is the cause; I will make a minimal edit.', 'I will change this part of the code.', 'Applying the fix to this spot.']

def hunks_of(patch):
    try: ps = PatchSet(patch)
    except Exception: return None
    res = []
    for pf in ps:
        if pf.is_added_file or pf.is_removed_file or pf.is_rename: return None
        if re.search(r'(^|/)(tests?|testing)(/|_)|test_|conftest|docs?/', pf.path): return None
        res.append((pf.path, [h for h in pf]))
    return res

def build(r):
    hs = hunks_of(r['patch'])
    if not hs or len(hs) > 2 or sum(len(h) for _, h in hs) > 3: return None
    if len(r['problem_statement']) > 3500 or len(r['problem_statement']) < 200: return None
    ws = tempfile.mkdtemp(prefix='ws'); gold_ws = tempfile.mkdtemp(prefix='gw')
    try:
        for d in (ws, gold_ws):
            subprocess.run(f"git -C src archive {r['base_commit']} | tar -x -C {d}", shell=True, check=True, stderr=subprocess.DEVNULL)
        pf = os.path.join(ws, '_gold.patch'); open(os.path.join(gold_ws, '_g.patch'), 'w').write(r['patch'])
        if subprocess.run('patch -p1 -s < _g.patch', shell=True, cwd=gold_ws, capture_output=True).returncode: return None
        path0 = hs[0][0]
        src0 = open(os.path.join(ws, path0), encoding='utf-8').read()
        gold_text = '\n'.join(l.strip() for _, hh in hs for h in hh for l in (str(x) for x in h))
        issue = r['problem_statement']
        cands = []
        for t in re.findall(r'`([^`\n]{3,60})`', issue) + re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{3,}\b', issue):
            for w in re.findall(r'[A-Za-z_][A-Za-z0-9_]{3,}', t):
                if w in STOP or w.lower() in STOP or w in cands: continue
                if not ('_' in w or re.search(r'[a-z][A-Z]', w) or w[0].isupper()): continue
                if w in src0: cands.append(w)
        msgs = []; cid = [0]
        def call(name, args, say='', bad=False):
            cid[0] += 1; i = f'call_{cid[0]}'
            res = tool(ws, name, args)
            msgs.append({'bad': bad, 'role': 'assistant', 'content': say, 'tool_calls': [{'id': i, 'type': 'function', 'function': {'name': name, 'arguments': J(args)}}]})
            msgs.append({'role': 'tool', 'tool_call_id': i, 'name': name, 'content': J(res)})
            return res
        rng = random.Random(r['instance_id'])
        planNote = '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i+1}. {p}' for i, p in enumerate(PLAN))
        msgs.append({'role': 'user', 'content': HEAD.format(repo=repo, issue=issue) + planNote})
        # localisation: pick an identifier whose grep output contains the gold file
        done = False
        for t in sorted(cands, key=lambda w: (w not in gold_text, -len(w)))[:8]:
            cmd = f"grep -rn --include='*.py' '{t}' . | head -20"
            o = tool(ws, 'bash', {'command': cmd})
            if path0 in (o.get('output') or '').replace('./', '') and len((o.get('output') or '').splitlines()) <= 20:
                call('bash', {'command': cmd}, rng.choice(SAY_GREP).format(t=t)); done = True; break
        if not done: return None
        h0 = hs[0][1][0]
        call('read_file', {'path': path0, 'offset': max(1, h0.source_start - 20), 'limit': min(120, h0.source_length + 45)}, rng.choice(SAY_READ).format(p=path0))
        names = []; recovered = False
        for path, hh in hs:
            if path != path0 and True:
                call('read_file', {'path': path, 'offset': max(1, hh[0].source_start - 20), 'limit': min(120, hh[0].source_length + 45)}, rng.choice(SAY_READ).format(p=path))
            text = open(os.path.join(ws, path), encoding='utf-8').read()
            for h in hh:
                lines = [(l.line_type, l.value.rstrip('\n')) for l in h]
                ok = False
                for ctx in range(2, 8):
                    # trim context to `ctx` lines on each side
                    first = next((i for i, (k, _) in enumerate(lines) if k != ' '), None); last = max(i for i, (k, _) in enumerate(lines) if k != ' ')
                    seg = lines[max(0, first - ctx): last + ctx + 1]
                    old = '\n'.join(v for k, v in seg if k != '+'); new = '\n'.join(v for k, v in seg if k != '-')
                    if old and text.count(old) == 1: ok = True; break
                if not ok or old == new: return None
                if rng.random() < 0.3 and '\n' in old and not recovered:
                    ol = old.split('\n'); k = next((j for j, l in enumerate(ol) if l.startswith('    ')), None)
                    if k is not None:
                        ol[k] = ol[k].lstrip(); badold = '\n'.join(ol)
                        if text.count(badold) == 0:
                            r1 = call('edit_file', {'path': path, 'old': badold, 'new': new}, rng.choice(SAY_EDIT), bad=True)
                            if not r1.get('ok'):
                                recovered = True
                                call('read_file', {'path': path, 'offset': max(1, h.source_start - 5), 'limit': h.source_length + 15}, 'The edit did not match exactly (whitespace). Let me re-read the exact text.')
                res = call('edit_file', {'path': path, 'old': old, 'new': new}, rng.choice(SAY_EDIT))
                if not res.get('ok'): return None
                text = open(os.path.join(ws, path), encoding='utf-8').read()
                if h.section_header: names.append(h.section_header.strip())
        for path, _ in hs:
            if open(os.path.join(ws, path), 'rb').read() != open(os.path.join(gold_ws, path), 'rb').read(): return None
        files = [p for p, _ in hs]
        o = call('bash', {'command': 'python3 -m py_compile ' + ' '.join(files) + ' && echo syntax OK'}, 'Checking that the edited file still compiles.')
        if o.get('exit_code') != 0: return None
        fl = ', '.join(f'`{p}`' for p in files); where = (' (' + '; '.join(dict.fromkeys(names)) + ')') if names else ''
        final = rng.choice([
            f'I edited {fl}{where} to address the issue. `py_compile` passed, but I could not run the project tests in this environment, so the behaviour change itself is unverified.',
            f'Changed {fl}{where}: the code at the location found by grep now follows what the issue asks for. I only confirmed that the file compiles (`py_compile`); the project tests were not run, so please run them.'])
        msgs.append({'role': 'assistant', 'content': final})
        return {'name': r['instance_id'], 'repo': repo, 'prompt': msgs[0]['content'], 'pass': True, 'messages': msgs}
    except Exception as e:
        print('skip', r['instance_id'], type(e).__name__, str(e)[:80], flush=True); return None
    finally:
        shutil.rmtree(ws, ignore_errors=True); shutil.rmtree(gold_ws, ignore_errors=True)

n = 0
with open(out, 'w') as f:
    for r in rows:
        if n >= cap: break
        x = build(r)
        if x: f.write(json.dumps(x, ensure_ascii=False) + '\n'); f.flush(); n += 1
print('built', n, flush=True)
