import json,re,sys,statistics
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
LN={"python":"Python","javascript":"JavaScript","typescript":"TypeScript","java":"Java","cpp":"C++","csharp":"C#","go":"Go","rust":"Rust"}
EXAMPLE=("例(別の課題):\n"
"課題は、文字列から連続する空白を1つにまとめ、前後の空白を取り除くことだ。入力は文字列、出力も文字列である。"
"単純に`split()`で空白区切りに分け、`' '.join`で結べば、連続空白の圧縮と前後の除去が同時にできる。"
"空文字列や空白だけの文字列は、分割結果が空になり、空文字列が返る。改行やタブも空白として扱われる点は、課題の趣旨に合っている。")
def prompt(it):
    edit = it['domain'].startswith('python/edit') or it['domain'].startswith('python/fim') or 'バグ' in it['instruction'] or '<FILL>' in it['instruction']
    extra = "この課題には元のコードが含まれる。元のコードの問題点や、変更すべき箇所は、課題の一部として分析してよい。ただし、修正後の完成形を知っているような書き方はしない。\n" if edit else ""
    return (f"あなたは、プログラミング課題を解く人が、コードを書く直前に頭の中で整理する思考を書く役割です。\n"
      f"次の「課題」と、それを満たす正解の「{LN[it['lang']]}コード」を読み、**課題だけから自然に導ける思考**を日本語で書いてください。正解コードは、思考の内容が食い違わないための確認用で、存在しないものとして扱います。\n\n"
      f"## 課題\n{it['instruction']}\n\n## 正解コード(確認用)\n```{it['lang']}\n{it['code']}\n```\n\n"
      "## 書き方の条件\n"
      "- 出力は思考の本文だけ。見出し、前置き、コードブロックは書かない。\n"
      "- 長さは**250字前後(最大350字)**。2〜5文。箇条書きは使わない。\n"
      "- 流れ: 求められていることの要約 → 入力と出力の形 → 解き方と、その理由 → 注意すべき境界条件(必要なときだけ) → 方針で満たせるという短い確認。\n"
      "- コードを見ていることが分かる表現は禁止: 「このコード」「完成コード」「上記」「既存のコード」「コードでは」「実装では」「想定していない」「考慮していない」「触れない」など。\n"
      "- 正解コードが実際に行う処理だけを述べる。コードにない処理や、使っていない方法を述べない。\n"
      "- 課題が満たせない、代替で済ませる、といった言い訳は書かない。\n"
      "- 日本語のみ(識別子と記号は除く)。変数名や関数名は`バッククォート`で囲んでよい。\n"
      f"{extra}\n{EXAMPLE}")
BAD=re.compile(r"このコード|完成コード|完成形|正解コード|上記|与えられたコード|提示されたコード|以下のコード|既存のコード|既存コード|コードでは|コード上|実装では|この実装|想定していない|考慮していない|考慮しない|触れない|代替|満たすことはできない|満たせない|完全には|できない")
def check(t,code,edit):
    errs=[]
    if '```' in t: errs.append('コードブロック')
    n=len(t.strip())
    if n<100: errs.append(f'短すぎ({n})')
    if n>420: errs.append(f'長すぎ({n})')
    m=BAD.search(t)
    if m and not (edit and m.group(0) in ('与えられたコード','提示されたコード','既存のコード','既存コード','以下のコード')): errs.append('禁止語:'+m.group(0))
    jp=sum(1 for ch in t if '\u3040'<=ch<='\u30ff' or '\u4e00'<=ch<='\u9fff')
    if jp/max(1,len(t))<0.3: errs.append('日本語比率低')
    for l in code.splitlines():
        l=l.strip()
        if len(l)>=40 and l in t: errs.append('コード行の丸写し'); break
    return errs
if __name__=="__main__":
    items=json.load(open('/tmp/think_samples2.json'))
    with ThreadPoolExecutor(15) as ex: outs=list(ex.map(lambda i:call_ds(prompt(i),max_tokens=900,reasoning_off=True),items))
    ti=sum(u.get('prompt_tokens',0) for _,u,_ in outs); to=sum(u.get('completion_tokens',0) for _,u,_ in outs)
    cost=ti/1e6*0.06+to/1e6*0.18
    res=[]
    for it,(t,u,m) in zip(items,outs):
        edit=it['domain'].startswith('python/edit') or it['domain'].startswith('python/fim') or 'バグ' in it['instruction'] or '<FILL>' in it['instruction']
        errs=check(t.strip(),it['code'],edit); res.append({**it,"think":t.strip(),"errs":errs})
    ok=[r for r in res if not r['errs']]
    L=[len(r['think']) for r in res]
    print('実費$%.4f (1件 $%.5f)'%(cost,cost/len(res)),'| 機械チェック合格 %d/%d'%(len(ok),len(res)),'| 長さ 中央値%d 最大%d'%(statistics.median(L),max(L)))
    import collections
    print('不合格の理由:',dict(collections.Counter(e.split(':')[0]+(':'+e.split(':')[1] if ':' in e else '') for r in res for e in r['errs'])))
    json.dump(res,open('/tmp/think_samples2_out.json','w'),ensure_ascii=False)
