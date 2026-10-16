# Verified coding-task trajectories (write -> test -> [fail -> fix] -> honest report) from MBPP; tool outputs come from real execution.
import sys, os, re, json, random, subprocess, tempfile, shutil
from datasets import load_dataset
out = sys.argv[1]
TOOLRUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'runner', 'toolrun_ctr.py')
ds = load_dataset('mbpp', 'full')
rows = [r for sp in ('train', 'validation', 'prompt', 'test') for r in ds[sp]]
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(',', ':'))
def tool(ws, name, args):
    p = subprocess.run(['python3', TOOLRUN, ws], input=json.dumps({'name': name, 'args': args}), capture_output=True, text=True, timeout=120)
    return json.loads(p.stdout)
MUT = [(r'<=', '<'), (r'>=', '>'), (r'(?<![<>=!])<(?!=)', '<='), (r'==', '!='), (r'\+ 1\b', '+ 2'), (r'- 1\b', '- 0'), (r'range\(1,', 'range(0,'), (r'\bmin\(', 'max('), (r'\bmax\(', 'min('), (r'\band\b', 'or'), (r'\bor\b', 'and'), (r'\[0\]', '[1]'), (r'\[-1\]', '[0]'), (r'\bsorted\(', 'list(')]
def mutate(code, rng):
    cands = [(a, b) for a, b in MUT if re.search(a, code)]; rng.shuffle(cands)
    for a, b in cands:
        ms = list(re.finditer(a, code))
        m = rng.choice(ms); new = code[:m.start()] + b + code[m.end():]
        if new != code: return new
    return None
def run_tests(ws, code, tests):
    open(os.path.join(ws, 'solution.py'), 'w').write(code); open(os.path.join(ws, 'test_solution.py'), 'w').write(tests)
    p = subprocess.run('python3 test_solution.py', shell=True, cwd=ws, capture_output=True, text=True, timeout=20); return p.returncode == 0
HEAD_EN = 'Write a Python function for the task below and save it as solution.py in the current directory. Run it against the examples to check it works.\n\nTask: {text}\nExample asserts:\n{tests}'
HEAD_JA = '次の仕様の Python 関数を作り、カレントディレクトリの solution.py に保存してください。例の assert で動作を確認してください。\n\n仕様(英語): {text}\n例:\n{tests}'
PLAN_EN = ['Write the function to solution.py.', 'Write the example asserts to test_solution.py.', 'Run the tests and read the result; fix the code if they fail.', 'Report what was and was not verified.']
n = 0; rng0 = random.Random(7)
with open(out, 'w') as f:
    for r in rows:
        rng = random.Random(r['task_id'])
        code = r['code'].replace('\r\n', '\n').strip() + '\n'; tl = [t.strip() for t in r['test_list']]
        setup = (r.get('test_setup_code') or '').strip()
        tests = (setup + '\n' if setup else '') + 'from solution import *\n' + '\n'.join(tl) + '\nprint("all tests passed")\n'
        ws = tempfile.mkdtemp(prefix='m')
        try:
            if not run_tests(ws, code, tests): continue
            ja = rng.random() < 0.5
            user = (HEAD_JA if ja else HEAD_EN).format(text=r['text'], tests='\n'.join(tl))
            plan = '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i+1}. {p}' for i, p in enumerate(PLAN_EN))
            msgs = [{'role': 'user', 'content': user + plan}]; cid = [0]
            def call(name, args, bad=False):
                cid[0] += 1; i = f'call_{cid[0]}'; res = tool(ws, name, args)
                msgs.append({'bad': bad, 'role': 'assistant', 'content': '', 'tool_calls': [{'id': i, 'type': 'function', 'function': {'name': name, 'arguments': J(args)}}]})
                msgs.append({'role': 'tool', 'tool_call_id': i, 'name': name, 'content': J(res)}); return res
            mut = mutate(code, rng) if rng.random() < 0.45 else None
            if mut and run_tests(ws, mut, tests): mut = None     # mutation must break the tests
            shutil.rmtree(ws); ws = tempfile.mkdtemp(prefix='m')
            first = mut or code
            call('write_file', {'path': 'solution.py', 'content': first}, bad=bool(mut))
            call('write_file', {'path': 'test_solution.py', 'content': tests})
            o = call('bash', {'command': 'python3 test_solution.py'})
            if mut:
                if o.get('exit_code') == 0: continue
                # fix: edit the mutated spot back (find the diff region)
                a = next(i for i in range(min(len(mut), len(code))) if mut[i] != code[i])
                ls = mut.rfind('\n', 0, a) + 1; le = mut.find('\n', a); le = len(mut) if le < 0 else le
                cl_ls = code.rfind('\n', 0, a) + 1; cl_le = code.find('\n', a); cl_le = len(code) if cl_le < 0 else cl_le
                old, new = mut[ls:le], code[cl_ls:cl_le]
                if old == new or mut.count(old) != 1: continue
                r2 = call('edit_file', {'path': 'solution.py', 'old': old, 'new': new})
                if not r2.get('ok'): continue
                o = call('bash', {'command': 'python3 test_solution.py'})
            if o.get('exit_code') != 0: continue
            k = len(tl)
            if ja: final = rng.choice([f'`solution.py` に関数を書き、例の assert {k} 件を `test_solution.py` にして `python3 test_solution.py` を実行しました。終了コード 0 で「all tests passed」と出ました。確認したのは仕様に付いていた例だけなので、それ以外の入力での動作は確認できていません。',
                                     f'solution.py を作成し、例の assert {k} 件で確認しました(終了コード 0)。例以外の入力は試していません。'])
            else: final = rng.choice([f'I wrote the function in `solution.py`, put the {k} example asserts into `test_solution.py` and ran `python3 test_solution.py`: exit code 0, "all tests passed". I only checked the examples that came with the task, so other inputs are unverified.',
                                      f'`solution.py` is written and the {k} given examples pass (exit code 0). I did not test any other inputs.'])
            if mut: final = ('最初の版は例の1つに失敗したため、該当行を直して再実行しました。' if ja else 'My first version failed an example, so I fixed that line and re-ran the tests. ') + final
            msgs.append({'role': 'assistant', 'content': final})
            f.write(json.dumps({'name': f"mbpp-{r['task_id']}", 'prompt': user, 'pass': True, 'messages': msgs}, ensure_ascii=False) + '\n'); n += 1
        except Exception as e:
            print('skip', r['task_id'], type(e).__name__, str(e)[:60])
        finally: shutil.rmtree(ws, ignore_errors=True)
print('built', n)
