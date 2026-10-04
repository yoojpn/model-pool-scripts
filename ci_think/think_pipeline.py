import json,re,sys,os,gzip,time,threading,subprocess,tempfile,hashlib
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
import think_gen2 as g
from think_fid import fid_prompt
from concurrent.futures import ThreadPoolExecutor
MODE=sys.argv[1]; CONC=int(sys.argv[2]); LIMIT=float(sys.argv[3]); BUGFILES=os.environ.get('BUGFILES','/tmp/bugjudged_prod.jsonl').split(',')
BAD2=re.compile(r"このコード|完成コード|完成形|正解コード|上記|既存のコード|既存コード|コードでは|コード上|この実装|想定していない|考慮していない|触れない|代替|満たすことはできない|満たせない")
EDIT_OK=('与えられたコード','提示されたコード','既存のコード','既存コード','以下のコード')
def mcheck(t,code,edit):
    errs=[]; n=len(t.strip())
    if '```' in t: errs.append('コードブロック')
    if n<100: errs.append('短すぎ')
    if n>420: errs.append('長すぎ')
    m=BAD2.search(t)
    if m and not (edit and m.group(0) in EDIT_OK): errs.append('禁止語:'+m.group(0))
    jp=sum(1 for ch in t if '\u3040'<=ch<='\u30ff' or '\u4e00'<=ch<='\u9fff')
    if jp/max(1,len(t))<0.3: errs.append('日本語比率低')
    for l in code.splitlines():
        l=l.strip()
        if len(l)>=40 and l in t: errs.append('コード行の丸写し'); break
    return errs
def mcheck_bf(t,code):
    errs=[]; n=len(t.strip())
    if '```' in t: errs.append('コードブロック')
    if n<100: errs.append('短すぎ')
    if n>480: errs.append('長すぎ')
    m=re.search(r"完成コード|完成形|正解コード|修正後のコードでは|元の正しい|正しいコードでは|もともと正しい|仕込|埋め込まれ|意図的に|注入",t)
    if m: errs.append('禁止語:'+m.group(0))
    jp=sum(1 for ch in t if '\u3040'<=ch<='\u30ff' or '\u4e00'<=ch<='\u9fff')
    if jp/max(1,len(t))<0.3: errs.append('日本語比率低')
    for l in code.splitlines():
        l=l.strip()
        if len(l)>=40 and l in t: errs.append('コード行の丸写し'); break
    return errs
cost=[0.0]; stop=[False]; lock=threading.Lock()
def addc(u):
    c=u.get('prompt_tokens',0)/1e6*0.06+u.get('completion_tokens',0)/1e6*0.18
    with lock:
        cost[0]+=c
        if cost[0]>LIMIT: stop[0]=True
def call(p,mt):
    for k in range(4):
        t,u,m=call_ds(p,max_tokens=mt,reasoning_off=True); addc(u)
        if t.strip(): return t.strip()
        time.sleep(2+2*k)
    return ""
def fidelity(it):
    for _ in range(2):
        t=call(fid_prompt(it),200); mm=re.search(r'\{.*\}',t,re.S)
        try:
            v=json.loads(mm.group(0)); 
            if v.get('verdict') in ('OK','NG'): return v
        except Exception: pass
    return {"verdict":"ERR","reason":""}
BUGFIX_EXTRA="\n\n【この課題について】課題はバグ修正である。現在のコードの動きと失敗したテストの症状から、原因を特定し、最小限の修正方針を立てる、という思考にする(症状 → 原因 → 修正方針 → 修正で解消できる確認)。"
MATH_EXTRA="\nこの問題には入力がない。問題文の数値をそのまま使って計算し、答えを出力する、という前提で書く(「入力として与えられる」とは書かない)。"
def solve_math(it):
    p=("次の算数の文章題を解く、Pythonプログラムを書いてください。\n\n"+it['instruction']+"\n\n条件:\n- 標準入力は使わない。必要な数値はコード内の変数に書き、計算して、**最終的な答えだけ**を出力する。\n"
       "- 答えは数値のみ(単位や文字は付けない)。**最後の出力は必ず `print(int(answer) if answer == int(answer) else answer)` の形にする**(整数なら整数、小数なら小数)。割り算は結果が整数になる場合でも浮動小数になるので、この形で整える。\n"
       "- 変数名は意味が分かるものにし、計算の各ステップがコードから読み取れるようにする。\n- 出力は```pythonのコードブロック1つだけ。説明は書かない。")
    t=call(p,900); cm=re.findall(r"```python\n(.*?)```",t,re.S); c=cm[-1].strip() if cm else None
    if not c: return None
    with tempfile.TemporaryDirectory() as td:
        try:
            r=subprocess.run([sys.executable,'-c',c],capture_output=True,text=True,timeout=5,cwd=td)
            return c if (r.returncode==0 and r.stdout.strip()==it['expected']) else None
        except Exception: return None
def process(it):
    if stop[0]: return None
    rec={"key":it['key'],"domain":it['domain'],"lang":it['lang'],"instruction":it['instruction']}
    if MODE=='math':
        c=solve_math(it)
        if not c: rec['status']='math_wrong'; return rec
        it['code']=c
    rec['code']=it['code']
    p=g.prompt(it)+(MATH_EXTRA if MODE in ('math','mathhard') else '')+(BUGFIX_EXTRA if MODE=='bugfix' else '')
    t=call(p,900)
    edit=it['domain'].startswith(('python/edit','python/fim','bugfix/')) or 'バグ' in it['instruction'] or '<FILL>' in it['instruction']
    errs=(mcheck_bf(t,it['code']) if MODE=='bugfix' else mcheck(t,it['code'],edit)) if t else ['空']
    rec['think']=t
    if errs: rec['status']='mech_ng'; rec['errs']=errs; return rec
    it['think']=t; v=fidelity(it); rec['fid']=v
    rec['status']='ok' if v['verdict']=='OK' else ('fid_ng' if v['verdict']=='NG' else 'fid_err')
    return rec
def load_items():
    out=[]
    if MODE=='code':
        for i,l in enumerate(gzip.open('/tmp/py_v2.jsonl.gz','rt')):
            r=json.loads(l); m=re.findall(r"```python\n(.*?)```",r['full_response'],re.S)
            if not m: continue
            out.append({"key":f"py{i}","domain":"python/"+r['task_type'],"lang":"python","instruction":r['instruction'],"code":m[-1].strip(),"task_type":r['task_type']})
        tasks=json.load(open('/tmp/new_tasks.json'))
        for x in json.load(open('/tmp/final_passed_v2.json')):
            out.append({"key":f"ml{x['tid']}_{x['lang']}","domain":"multi/"+x['lang'],"lang":x['lang'],"instruction":tasks[x['tid']]['instruction'],"code":x['code']})
    elif MODE=='bugfix':
        import importlib.util
        spec=importlib.util.spec_from_file_location('ng','/tmp/newtest_gen_lib.py'); ng=importlib.util.module_from_spec(spec); spec.loader.exec_module(ng)
        FORMAT=ng.FORMAT; DISPN={"python":"Python","javascript":"JavaScript","typescript":"TypeScript","java":"Java","cpp":"C++","csharp":"C#","go":"Go","rust":"Rust"}
        seen=set()
        for fn in BUGFILES:
            for l in open(fn):
                r=json.loads(l)
                if r['status']!='ok': continue
                k=(r['lang'],r['tid'],hashlib.md5(r['buggy'].encode()).hexdigest())
                if k in seen: continue
                seen.add(k); f=r['fail']
                up=(f"次の{DISPN[r['lang']]}プログラムは、仕様どおりに動かず、テストに失敗します。バグの原因を見つけて修正してください。\n\n仕様:\n{r['instruction']}\n\n{FORMAT}\n"
                    f"現在のコード:\n```{r['lang']}\n{r['buggy']}\n```\n\n失敗したテスト:\n入力:\n{f['stdin']}\n期待される出力:\n{f['expected']}\n実際の出力:\n{f['actual']}\n\n"
                    f"修正後のコード全体を```{r['lang']}ブロックで出力してください。")
                out.append({"key":"bf%s_%d_%s"%(r['lang'],r['tid'],k[2][:8]),"domain":"bugfix/"+r['lang'],"lang":r['lang'],"instruction":up,"code":r['fixed'],"tid":r['tid']})
    elif MODE=='mathhard':
        for l in open('/tmp/mathhard_sol.jsonl'):
            r=json.loads(l)
            if r['ok']: out.append({"key":f"mh{r['idx']}","domain":"math_hard","lang":"python","instruction":r['problem'],"code":r['code']})
    elif MODE=='writeB':
        import b_common as C
        tasksB=json.load(open('/tmp/new_tasks_B.json'))
        for r in json.load(open('/tmp/B_pass.json')):
            ti=r['tid']-1143; t=tasksB[ti]
            out.append({"key":f"ml{r['tid']}_{r['lang']}","domain":"multi/"+r['lang'],"lang":r['lang'],"instruction":t['instruction'],"code":r['code']})
    elif MODE=='pystdio':
        tasks=json.load(open('/tmp/new_tasks.json'))
        for r in json.load(open('/tmp/pystdio_all.json')):
            if r['status']=='pass': out.append({"key":f"ml{r['tid']}_python","domain":"multi/python","lang":"python","instruction":tasks[r['tid']]['instruction'],"code":r['code']})
    elif MODE=='pynat':
        tasks=json.load(open('/tmp/new_tasks.json'))
        for l in open('/tmp/pynat_all.jsonl'):
            r=json.loads(l)
            if r['status']=='pass': out.append({"key":f"pn{r['tid']}","domain":"python/natural","lang":"python","instruction":tasks[r['tid']]['instruction'],"code":r['code']})
    else:
        for i,l in enumerate(gzip.open('/tmp/math_tasks_3000.jsonl.gz','rt')):
            r=json.loads(l); out.append({"key":f"m{i}","domain":"math","lang":"python","instruction":r['instruction'],"expected":r['stdio_pairs'][0]['expected_stdout'].strip(),"code":""})
    return out
NL=int(os.environ.get('N_LIMIT','0'))
OUT=f'/tmp/think_out_{MODE}'+('_TEST' if NL else '')+'.jsonl'; done=set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)['key'])
        except: pass
items=[it for it in load_items() if it['key'] not in done]
if NL:
    import random; random.seed(1); random.shuffle(items); items=items[:NL]
print(MODE,'対象',len(items)+len(done),'済',len(done),'残',len(items),flush=True)
n=0
with ThreadPoolExecutor(CONC) as ex, open(OUT,'a') as fo:
    for rec in ex.map(process,items):
        if rec is None: continue
        fo.write(json.dumps(rec,ensure_ascii=False)+"\n"); fo.flush(); n+=1
        if n%300==0: print(n,'cost$%.3f'%cost[0],flush=True)
print('DONE' if not stop[0] else 'STOPPED(cost limit)','cost$%.3f'%cost[0],flush=True)
