"""失敗分を、課題・失敗コード・エラーを見せて修正させる(②の第2ラウンド)。Actions用。"""
import json,sys,os,threading
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
import b_common as C
tasks={}
for l in open('/tmp/B_gen_r1.jsonl'):
    r=json.loads(l); tasks[(r['tid'],r['lang'])]=r
refmap={t['instruction']:t['ref'] for t in json.load(open('/tmp/new_tasks_B.json'))}
J=[json.loads(l) for f in sorted(os.listdir('/tmp')) if f.startswith('B_judged1_') for l in open('/tmp/'+f)]
failed=[r for r in J if r['status']=='failed']
print('第1ラウンド:',len(J),'件 / 不合格',len(failed),flush=True)
def build(r):
    g=tasks[(r['tid'],r['lang'])]; task=g['task']; lang=r['lang']
    idx=len(r['pair_results'])-1; pr=C.build_stdio_pairs([task['io_pairs'][idx]])[0]; p=r['pair_results'][idx]
    if p['rc']!=0:
        res="実行結果: エラー終了(コンパイルエラーまたは実行時エラー)\nエラー出力(末尾):\n"+p['stderr'][-500:]
        if idx==0: res+="\n\n期待される出力:\n"+pr['expected_stdout']
    elif idx==0: res=f"あなたのプログラムの出力:\n{p['actual']}\n期待される出力:\n{pr['expected_stdout']}"
    else: res=f"あなたのプログラムの出力:\n{p['actual']}\n(この出力は、元のPython関数の結果と異なります。元のPython関数の動作を正確に追って直してください)"
    return (f"以下は、元のPython関数と、それを{C.DISP[lang]}に翻訳したプログラムです。翻訳プログラムはテストに失敗しました。原因を直して、修正したプログラム全体を書いてください。\n\n"
      f"元のPython関数:\n```python\n{refmap[task['instruction']]}\n```\n\n{C.FORMAT}\n標準ライブラリのみ使い、外部ライブラリは使わないでください。\n\n"
      f"現在の{C.DISP[lang]}コード:\n```{lang}\n{r['code']}\n```\n\n失敗したテスト:\n入力:\n{pr['stdin']}\n{res}\n\n"
      f"**説明文は必ず日本語で書き、他の言語を混ぜないこと。**\n失敗の原因を1文で述べてから、修正したコード全体を```{lang}ブロック1つで書いてください。")
def work(r):
    for k in range(3):
        t,u,m=call_ds(build(r),max_tokens=5000,reasoning_off=True)
        if t.strip(): break
    return r,t
with ThreadPoolExecutor(30) as ex, open('/tmp/B_gen_r2.jsonl','w') as fo:
    for r,t in ex.map(work,failed):
        g=tasks[(r['tid'],r['lang'])]
        fo.write(json.dumps({"tid":r['tid'],"lang":r['lang'],"task":g['task'],"full_response":t},ensure_ascii=False)+"\n")
print('修正生成',len(failed),'件')
