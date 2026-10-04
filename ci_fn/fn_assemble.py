"""judged(全体コードの判定)→ 合格したものの関数部分を、思考生成の入力にする"""
import json,sys,glob
mode=sys.argv[1]
if mode=='merge':
    pat,dst=sys.argv[2],sys.argv[3]; n=0
    with open(dst,'w') as f:
        for p in sorted(glob.glob(pat)):
            for l in open(p): f.write(l); n+=1
    print('連結',n,'件')
elif mode=='pass':      # judged と candidates を突き合わせる
    judged,cands,dst=sys.argv[2],sys.argv[3],sys.argv[4]
    ok={}
    for l in open(judged):
        r=json.loads(l)
        if r['status']=='passed': ok[(r['tid'],r['lang'])]=True
    out=[]
    for l in open(cands):
        c=json.loads(l)
        if (c['tid'],c['lang']) in ok: out.append({"tid":c['tid'],"lang":c['lang'],"instruction":c['instruction'],"sig":c['sig'],"fn":c['fn']})
    json.dump(out,open(dst,'w'),ensure_ascii=False)
    print('全体コードがテストに合格した関数:',len(out))
