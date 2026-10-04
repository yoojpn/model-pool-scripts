"""judgedのシャード結果を連結して、gen_input(gz)形式のファイルや合格リストを作る。modeで動作を切り替える。"""
import json,sys,os,gzip,glob
mode=sys.argv[1]
if mode=='to_gz':          # B_gen_r{1,2}.jsonl -> gen_input.jsonl.gz
    src,dst=sys.argv[2],sys.argv[3]
    with gzip.open(dst,'wt') as f:
        for l in open(src):
            r=json.loads(l); f.write(json.dumps({"lang":r['lang'],"tid":r['tid'],"task":r['task'],"full_response":r['full_response']},ensure_ascii=False)+"\n")
elif mode=='merge_judged':  # judged_*.jsonl を1つに
    pat,dst=sys.argv[2],sys.argv[3]; n=0
    with open(dst,'w') as f:
        for p in sorted(glob.glob(pat)):
            for l in open(p): f.write(l); n+=1
    print('連結',n,'件')
elif mode=='think_items':   # 合格(r1+r2)を think_pipeline の入力にする
    seen=set(); out=[]
    for fn in sys.argv[2:-1]:
        for l in open(fn):
            r=json.loads(l)
            if r['status']=='passed' and (r['tid'],r['lang']) not in seen:
                seen.add((r['tid'],r['lang'])); out.append(r)
    json.dump([{"tid":r['tid'],"lang":r['lang'],"code":r['code']} for r in out],open(sys.argv[-1],'w'),ensure_ascii=False)
    print('合格',len(out))
