"""② 新規課題の翻訳生成(7言語)。Actions用の自己完結スクリプト。tidは1143から。"""
import json,sys,os,threading
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
import b_common as C
tasks=json.load(open('/tmp/new_tasks_B.json'))
LANGS=['javascript','typescript','java','cpp','csharp','go','rust']
N=int(os.environ.get('B_LIMIT_TASKS','0')) or len(tasks)
jobs=[(ti,l) for ti in range(N) for l in LANGS]
OUT='/tmp/B_gen_r1.jsonl'
def build(ti,lang):
    t=tasks[ti]; pr=C.build_stdio_pairs([t['io_pairs'][0]])[0]
    return (f"以下は、元のPython関数です。同じ動作をする{C.DISP[lang]}プログラムを書いてください(標準入力から値を読み、結果を標準出力に書く)。\n\n```python\n{t['ref']}\n```\n\n{C.FORMAT}\n標準ライブラリのみ使い、外部ライブラリは使わないでください。\n\n"
      f"テスト例:\n入力:\n{pr['stdin']}\n期待される出力:\n{pr['expected_stdout']}\n\n**説明文は必ず日本語で書き、他の言語を混ぜないこと。**\n実装方針を1文だけ述べてから、コード全体を```{lang}ブロック1つで書いてください。")
cost=[0.0]; lock=threading.Lock()
def work(j):
    ti,lang=j
    for k in range(3):
        t,u,m=call_ds(build(ti,lang),max_tokens=5000,reasoning_off=True)
        with lock: cost[0]+=u.get('prompt_tokens',0)/1e6*0.06+u.get('completion_tokens',0)/1e6*0.18
        if t.strip(): break
    return ti,lang,t
n=0
with ThreadPoolExecutor(30) as ex, open(OUT,'w') as fo:
    for ti,lang,t in ex.map(work,jobs):
        fo.write(json.dumps({"tid":1143+ti,"lang":lang,"task":{"task":"x","instruction":tasks[ti]['instruction'],"io_pairs":tasks[ti]['io_pairs'][:4]},"full_response":t},ensure_ascii=False)+"\n"); n+=1
print('翻訳生成',n,'件 cost$%.3f'%cost[0])
