import gzip,json,os,sys,subprocess,re,tempfile,glob
shard,total,src=int(sys.argv[1]),int(sys.argv[2]),sys.argv[3]
sys.path.insert(0,'ci_loop'); import b_common as C
rows=[json.loads(l) for l in gzip.open(src,'rt')]
mine=[r for i,r in enumerate(rows) if i%total==shard]
def code_of(resp):
    m=re.findall(r"```python\n(.*?)```",resp,re.S)
    if m: return m[-1]
    m=re.findall(r"```python\n(.*)$",resp,re.S); return m[-1] if m else None
out=[]
for r in [x for x in mine if x['lang']=='python']:
    code=code_of(r['full_response']); ok=code is not None
    if ok:
        pairs=[p for p in C.build_stdio_pairs(r['task']['io_pairs'][:4]) if p['expected_stdout'].strip()!='']
        ok=len(pairs)>0
        for p in pairs:
            with tempfile.TemporaryDirectory() as td:
                try: q=subprocess.run([sys.executable,'-c',code],input=p['stdin'],capture_output=True,text=True,timeout=10,cwd=td)
                except subprocess.TimeoutExpired: ok=False; break
            if q.returncode!=0 or q.stdout.strip()!=p['expected_stdout'].strip(): ok=False; break
    out.append({'tid':r['tid'],'lang':'python','status':'passed' if ok else 'failed'})
open(f'judged_py_{shard}.jsonl','w').write('\n'.join(json.dumps(o) for o in out))
other=[x for x in mine if x['lang']!='python']
with gzip.open('other_in.jsonl.gz','wt') as f:
    for r in other: f.write(json.dumps(r,ensure_ascii=False)+'\n')
env=dict(os.environ,GEN_INPUT='other_in.jsonl.gz')
subprocess.run([sys.executable,'judge_v6.py','--shard','0','--total','1'],env=env)
for p in glob.glob('judged_*.jsonl'):
    if not p.startswith('judged_py_'): os.rename(p,f'judged_other_{shard}.jsonl') if not os.path.exists(f'judged_other_{shard}.jsonl') else None
print('shard',shard,'完了: python',len(out),'other',len(other))
