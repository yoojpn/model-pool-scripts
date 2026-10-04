import json,re,sys,os,gzip,threading
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
tasks=json.load(open('/tmp/pool_sel.json'))
def prompt(w):
    return (f"以下のPython関数をテストするための入力を8件作ってください。\n\n```python\n{w['ref']}\n```\n\n関数名: {w['func']}\n\n"
      "条件:\n- 各入力は、引数を順に並べたJSON配列にする(キーワード引数は使わず、位置引数で)。\n- 引数の型は、関数が想定する型に正しく合わせる(リストにはリスト、辞書にはJSONオブジェクト、文字列には文字列、数値には数値)。\n"
      "- ファイル・ネットワーク・乱数・現在時刻に依存せず、例外が出ない入力にする。\n- 値は小さく、多様にする(通常の値、空、境界値を混ぜる)。\n"
      "- 出力は、入力の配列の配列(例: [[1,2],[3,4]])のJSONだけ。説明は書かない。")
def parse(t):
    cands=[t.strip()]+[x.strip() for x in re.findall(r"```(?:json)?\s*(.*?)```",t,re.S)]
    i,j=t.find("["),t.rfind("]")
    if i>=0 and j>i: cands.append(t[i:j+1])
    for c in cands:
        try:
            v=json.loads(c)
            if isinstance(v,list) and v and all(isinstance(a,list) for a in v): return v
        except Exception: pass
    lines=[l.strip() for l in t.splitlines() if l.strip().startswith('[')]
    try:
        v=[json.loads(l) for l in lines]
        if v and all(isinstance(a,list) for a in v): return v
    except Exception: pass
    return None
def work(w):
    for _ in range(3):
        t,u,m=call_ds(prompt(w),max_tokens=3000,reasoning_off=True)
        v=parse(t) if t.strip() else None
        if v: return w,v
    return w,None
out=0
with ThreadPoolExecutor(30) as ex, open('/tmp/inputs_B.jsonl','w') as fo:
    for w,v in ex.map(work,tasks):
        if v: fo.write(json.dumps({"instruction":w['instruction'],"func":w['func'],"ref":w['ref'],"inputs":v[:8]},ensure_ascii=False)+"\n"); out+=1
print('入力生成 成功',out,'/',len(tasks))
