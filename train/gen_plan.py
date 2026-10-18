# Hallucination-suppression data (CPU only). Reuses the task families of gen_verify.py.
#  plan_sft.jsonl : planner SFT rows {prompt, completion}  -- plans that name only files that exist (or search for them first)
#  plan_dpo.jsonl : planner preference pairs {prompt, chosen, rejected} -- rejected plans invent files / write needless tests / skip checking
#  coder_missing.jsonl : coder trajectories where the named file does not exist (search -> honest report) or lives under another name (search -> fix)
# usage: gen_plan.py OUTDIR N SEED
import sys, os, re, json, random, shutil, tempfile, subprocess
OUT, NN, SEED = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
os.makedirs(OUT, exist_ok=True)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_verify.py')).read().split("n = 0; tries = 0; per = {}")[0]
_argv = sys.argv; sys.argv = ['gen_verify', '/dev/null', '0', str(SEED)]
exec(_src)
sys.argv = _argv
N = NN
INSTR = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plan_instruction.txt')).read().rstrip('\n')
FAKE = ['utils/helpers.py', 'src/main.py', 'tests/test_main.py', 'app/config.yaml', 'lib/core.py', 'main.py', 'helpers.py', 'src/utils.py', 'data/input.json', 'scripts/run.sh']
def prompt_of(listing, request):
    ws = '\n'.join(listing) if listing else '(空)'
    return f"<start_of_turn>user\n{INSTR}\n\n現在の作業ディレクトリ:\n{ws}\n\n依頼: {request}\n出力:<end_of_turn>\n<start_of_turn>model\n"
def plan_json(steps): return json.dumps({'subtasks': steps}, ensure_ascii=False)
def short(c, n=90): c = c.replace('\n', ' '); return c if len(c) <= n else c[:n] + '…'
def fake_for(r, real):
    c = [f for f in FAKE if f not in real]; return r.choice(c)
def plan_gen(T, r):          # new-script tasks
    files = list(T['setup']); out = T['out']; ck = short(T['check'])
    chosen = [f"{' と '.join(files)} の内容を確認する", f"solve.py を作成し、要件どおりに {out} を出力する処理を実装する", "python3 solve.py を実行する", f"`{ck}` で {out} を入力から独立に確かめ、出力を読んで要件と照合する", "食い違いがあれば solve.py の該当箇所を直して再実行し、確認した範囲と未確認の範囲を報告する"]
    fk = fake_for(r, files)
    rejected = r.choice([
        [f"{fk} を開いて入力の形式を調べる", f"solve.py を作成する", f"tests/test_solve.py にテストを書く", "pytest を実行する", "完了を報告する"],
        [f"{files[0]} を読む", f"{fk} に処理を書く", "実行する", "完了を報告する"],
        ["solve.py を作成する", "完了を報告する"]])
    return chosen, rejected, files
def plan_edit(T, r):
    fn = re.search(r'def (\w+)\(', T['setup'][T['file']]).group(1); f = T['file']
    chosen = [f"{f} と test_mod.py を読み、{fn} の現状の動きを把握する", f"{f} の {fn} を最小限の編集で直す", "python3 test_mod.py を実行して既存のテストが通ることを確認する", f"依頼に書かれた端の例を `python3 -c` で {fn} に与え、出力を要件と照合する", "食い違えば直して再実行し、確認した範囲と未確認の範囲を報告する"]
    fk = fake_for(r, list(T['setup']))
    rejected = r.choice([[f"{fk} を開いて {fn} を探す", f"{fk} の {fn} を書き換える", "完了を報告する"], [f"tests/test_{fn}.py を新しく作成する", f"{f} を編集する", "完了を報告する"], [f"{f} を直す", "完了を報告する"]])
    return chosen, rejected, list(T['setup']), fn
NAMES = ['parser', 'loader', 'report', 'cleaner', 'router', 'config_utils', 'text_tools', 'invoice', 'scheduler']
def missing_plan(req_file, other, fn):
    ch = [f"ls と find で {req_file} が実在するか確認する", f"見つからなければ `grep -rn \"def {fn}\" .` で {fn} の定義が別のファイルにないか探す", f"どこにも無ければ、{req_file} を作ったり内容を推測したりせず、見つからなかったことと作業フォルダにあるファイルを報告する"]
    rj = [f"{req_file} を開いて {fn} を探す", f"{fn} の不具合を修正する", "テストを実行する", "完了を報告する"]
    return ch, rj
def run_tool(ws, name, args):
    p = subprocess.run(['python3', TOOLRUN, ws], input=json.dumps({'name': name, 'args': args}), capture_output=True, text=True, timeout=120); return json.loads(p.stdout)
class Traj:
    def __init__(self, ws, user): self.ws = ws; self.msgs = [{'role': 'user', 'content': user}]; self.i = 0
    def call(self, name, args, bad=False):
        self.i += 1; cid = f'call_{self.i}'; res = run_tool(self.ws, name, args)
        self.msgs.append({'bad': bad, 'role': 'assistant', 'content': '', 'tool_calls': [{'id': cid, 'type': 'function', 'function': {'name': name, 'arguments': J(args)}}]})
        self.msgs.append({'role': 'tool', 'tool_call_id': cid, 'name': name, 'content': J(res)}); return res
def missing_traj(r, ja):       # named file/function does not exist anywhere
    req_file = r.choice(NAMES) + '.py'; fn = r.choice(['parse_line', 'load_rows', 'build_report', 'clean_text', 'route_path', 'read_config'])
    others = r.sample([n for n in ['notes.txt', 'data.csv', 'README.md', 'sample.json', 'run.sh', 'todo.md'] if n != req_file], 3)
    ws = tempfile.mkdtemp(prefix='m')
    for o in others: open(os.path.join(ws, o), 'w').write(f'{o}\n')
    req = (f"{req_file} の `{fn}` が空の入力で例外を出します。空の入力でも落ちないように直してください。" if ja else f"`{fn}` in {req_file} raises an exception on empty input. Please fix it so empty input does not crash.")
    ch, rj = missing_plan(req_file, others, fn)
    user = req + '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i + 1}. {p}' for i, p in enumerate(ch))
    t = Traj(ws, user)
    try:
        t.call('list_dir', {'path': '.'})
        o = t.call('read_file', {'path': req_file})
        if o.get('ok') is not False: raise RuntimeError('file unexpectedly exists')
        o = t.call('bash', {'command': f'find . -name "*{req_file[:-3]}*" -not -path "./.git/*"; grep -rn "def {fn}" . ; echo "exit=$?"'})
        if 'def ' in (o.get('output') or ''): raise RuntimeError('found')
        lst = ', '.join(sorted(others))
        final = (f"`{req_file}` は作業フォルダにありません。`{fn}` の定義も、どのファイルにも見つかりませんでした。あるのは {lst} だけです。存在しないファイルを作ったり中身を推測したりはせず、何も変更していません。正しいファイル名か場所を教えてください。" if ja else
                 f"`{req_file}` does not exist in the working directory, and no file defines `{fn}`. The only files are {lst}. I did not create the file or guess its contents, and I changed nothing. Please tell me the correct file name or location.")
        t.msgs.append({'role': 'assistant', 'content': final}); return user, t.msgs, req, others, ch, rj
    finally: shutil.rmtree(ws, ignore_errors=True)
def renamed_traj(r, ja):       # the user names the wrong file; the function lives in mod.py
    fam = r.choice(EFAMS); T = fam(r)
    if not edit_valid(T): return None
    fn = re.search(r'def (\w+)\(', T['setup'][T['file']]).group(1); wrong = r.choice(NAMES) + '.py'
    req = re.sub(r'(?<![_\w])mod\.py', wrong, (T['req_ja'] if ja else T['req_en']))
    ch = [f"{wrong} が実在するか確認し、無ければ `grep -rn \"def {fn}\" .` で {fn} の定義を探す", "見つかったファイルとテストを読む", f"{fn} を最小限の編集で直す", "python3 test_mod.py と、依頼の端の例を `python3 -c` で実行し、出力を要件と照合する", f"指定されたファイル名と実際のファイルが違った場合はその旨を含めて、確認した範囲を報告する"]
    user = req + '\n\nSuggested plan (from a planning assistant; adapt it if needed):\n' + '\n'.join(f'{i + 1}. {p}' for i, p in enumerate(ch))
    ws = tempfile.mkdtemp(prefix='m')
    for p, c in T['setup'].items(): open(os.path.join(ws, p), 'w').write(c)
    t = Traj(ws, user)
    try:
        t.call('list_dir', {'path': '.'})
        o = t.call('read_file', {'path': wrong})
        if o.get('ok') is not False: raise RuntimeError('exists')
        o = t.call('bash', {'command': f'grep -rn "def {fn}" .'})
        if T['file'] not in (o.get('output') or ''): raise RuntimeError('grep miss')
        t.call('read_file', {'path': T['file']})
        o = t.call('edit_file', {'path': T['file'], 'old': T['old'], 'new': T['good']})
        if not o.get('ok'): raise RuntimeError('edit')
        o = t.call('bash', {'command': T['check']})
        if o.get('exit_code') != 0: raise RuntimeError('check')
        open(os.path.join(ws, '_hv.py'), 'w').write(T['hv'])
        if subprocess.run('python3 _hv.py', shell=True, cwd=ws, capture_output=True).returncode != 0: raise RuntimeError('hv')
        final = (f"指定された `{wrong}` は存在せず、`{fn}` は `{T['file']}` にありました。そこを直し、`test_mod.py` と要件の端の例を実行して、出力が要件と合うことを見ました。それ以外の入力は試していません。" if ja else
                 f"`{wrong}` does not exist; `{fn}` is defined in `{T['file']}`, so I edited that file. I ran `test_mod.py` and the edge cases from the request and the output matches the requirements; other inputs are untested.")
        t.msgs.append({'role': 'assistant', 'content': final}); return user, t.msgs, req, list(T['setup']), ch, None
    finally: shutil.rmtree(ws, ignore_errors=True)
rng0 = random.Random(SEED); sft = []; dpo = []; coder = []
fo = [open(os.path.join(OUT, n), 'w') for n in ('plan_sft.jsonl', 'plan_dpo.jsonl', 'coder_missing.jsonl')]
nb = {'gen': 0, 'edit': 0, 'miss': 0, 'ren': 0}
tries = 0
while sum(nb.values()) < N and tries < N * 8:
    tries += 1; r = random.Random(rng0.random()); ja = r.random() < .4; k = tries % 4
    try:
        if k == 0:
            fam = r.choice(FAMS); T = fam(r); ch, rj, files = plan_gen(T, r); req = T['req_ja'] if ja else T['req_en']; key = 'gen'
        elif k == 1:
            fam = r.choice(EFAMS); T = fam(r)
            if not edit_valid(T): continue
            ch, rj, files, fn = plan_edit(T, r); req = T['req_ja'] if ja else T['req_en']; key = 'edit'
        elif k == 2:
            user, msgs, req, files, ch, rj = missing_traj(r, ja); key = 'miss'
            fo[2].write(json.dumps({'name': f'miss-{tries}', 'prompt': user, 'pass': True, 'messages': msgs}, ensure_ascii=False) + '\n')
        else:
            res = renamed_traj(r, ja)
            if not res: continue
            user, msgs, req, files, ch, rj = res; key = 'ren'
            fo[2].write(json.dumps({'name': f'ren-{tries}', 'prompt': user, 'pass': True, 'messages': msgs}, ensure_ascii=False) + '\n')
        listing = files if k != 2 else files
        pr = prompt_of(listing, req)
        fo[0].write(json.dumps({'prompt': pr, 'completion': plan_json(ch) + '<end_of_turn>', 'kind': key}, ensure_ascii=False) + '\n')
        if rj is not None: fo[1].write(json.dumps({'prompt': pr, 'chosen': plan_json(ch), 'rejected': plan_json(rj), 'kind': key}, ensure_ascii=False) + '\n')
        nb[key] += 1
    except Exception as e:
        print('skip', k, type(e).__name__, str(e)[:70])
for f in fo: f.close()
print('built', nb, 'tries', tries)
