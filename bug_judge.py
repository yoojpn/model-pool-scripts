import json,re,sys,os,gzip,tempfile,argparse
src=open('/tmp/judge_v6.py').read() if os.path.exists('/tmp/judge_v6.py') else open('judge_v6.py').read()
sys.argv_backup=sys.argv; 
_a=argparse.ArgumentParser(); _a.add_argument("--shard",type=int,default=0); _a.add_argument("--total",type=int,default=1); A,_=_a.parse_known_args()
sys.argv=[sys.argv[0],"--shard","0","--total","1"]
exec(src[:src.index('import argparse as _ap')])
import subprocess
DANGER2=DANGER
def run_any(lang,code,stdin):
    if lang=='python':
        with tempfile.TemporaryDirectory() as td:
            try:
                r=subprocess.run([sys.executable,'-c',code],input=stdin,capture_output=True,text=True,timeout=8,cwd=td); return r.stdout,r.stderr,r.returncode
            except Exception as e: return '',str(e),-1
    with tempfile.TemporaryDirectory() as td: return run_lang(lang,code,stdin,td)
entries=[json.loads(l) for l in gzip.open(os.environ.get("BUG_INPUT","bug_input.jsonl.gz"),"rt")]
entries=[e for i,e in enumerate(entries) if i%A.total==A.shard]
out=open(f"bugjudged_{A.shard}.jsonl","w"); cnt={}
for n,e in enumerate(entries):
    lang=e['lang']; pairs=build_stdio_pairs(e['io_pairs'])[:8]; rec={k:e[k] for k in ('lang','tid','kind','fixed','buggy','instruction')}
    if DANGER2.search(e['buggy']): rec['status']='unsafe'
    else:
        st='bug_not_detected'; fail=None
        for i,pr in enumerate(pairs):
            so,se,rc=run_any(lang,e['buggy'],pr['stdin'])
            exp=pr['expected_stdout'].strip()
            if rc!=0: st='crash_or_compile' if i==0 else 'crash_later'; fail={"idx":i,"stdin":pr['stdin'],"expected":exp,"stderr":se[-300:]}; break
            if so.strip()!=exp: st='ok'; fail={"idx":i,"stdin":pr['stdin'],"expected":exp,"actual":so.strip()[:300]}; break
        if st=='ok':   # 正解コードが同じ全テスト(最大8件)を通ることを確認(元が間違っているテストでの失敗を除外)
            for pr in pairs:
                so,se,rc=run_any(lang,e['fixed'],pr['stdin'])
                if rc!=0 or so.strip()!=pr['expected_stdout'].strip(): st='fixed_fails'; break
        rec['status']=st; rec['fail']=fail
    cnt[rec['status']]=cnt.get(rec['status'],0)+1
    out.write(json.dumps(rec,ensure_ascii=False)+"\n")
    if (n+1)%50==0: out.flush(); print(n+1,'/',len(entries),cnt,flush=True)
out.close(); print('結果',cnt)
