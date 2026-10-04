import json,re,sys
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
def fid_prompt(it):
    return ("次の「思考」が、「コード」の内容と食い違っていないかを、厳しく点検してください。\n\n"
      f"## 課題\n{it['instruction'][:1500]}\n\n## コード\n```{it['lang']}\n{it['code']}\n```\n\n## 思考\n{it['think']}\n\n"
      "点検の観点:\n(a) 思考が述べる処理・方針・境界条件は、コードが実際に行っていることか。コードにない処理を述べていないか。\n"
      "(b) コードが行う重要な処理を、思考が逆に説明している(矛盾する)箇所はないか。\n"
      "(c) 思考が課題の要求と無関係なことを述べていないか。\n"
      "出力は1行のJSONだけ: {\"verdict\": \"OK\" か \"NG\", \"reason\": \"NGなら、食い違う箇所を30字以内で\"}")
def run(items):
    with ThreadPoolExecutor(15) as ex: outs=list(ex.map(lambda i:call_ds(fid_prompt(i),max_tokens=200,reasoning_off=True),items))
    res=[]; cost=0
    for it,(t,u,m) in zip(items,outs):
        cost+=u.get('prompt_tokens',0)/1e6*0.06+u.get('completion_tokens',0)/1e6*0.18
        mm=re.search(r'\{.*\}',t,re.S)
        try: v=json.loads(mm.group(0)) if mm else {"verdict":"ERR","reason":t[:50]}
        except Exception: v={"verdict":"ERR","reason":t[:50]}
        res.append(v)
    return res,cost
if __name__=="__main__":
    items=json.load(open('/tmp/think_samples2_out.json'))
    res,cost=run(items)
    import collections
    print('実費$%.4f'%cost,'| 判定',dict(collections.Counter(v['verdict'] for v in res)))
    for it,v in zip(items,res):
        if v['verdict']!='OK': print(f"- [{it['domain']}] {v['verdict']}: {v['reason']}")
