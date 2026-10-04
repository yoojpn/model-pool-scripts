"""関数形式: 検証済みプログラムを『関数+main』に分けさせる(API)。Actions用の自己完結スクリプト。"""
import json,re,sys,os,gzip,threading,collections
sys.path.insert(0,'/tmp')
from ds_lib import call_ds
from concurrent.futures import ThreadPoolExecutor
LN={"javascript":"JavaScript","typescript":"TypeScript","java":"Java","cpp":"C++","csharp":"C#","go":"Go","rust":"Rust"}
TYPEHINT={'javascript':'**JavaScriptなので、型注釈(: number など)は書かない。**必要なら、関数の直前にJSDocコメントで型を示す。','typescript':'TypeScriptなので、引数と戻り値に、処理に合った型注釈を書く。','java':'引数と戻り値には、処理に合った型を書く。','cpp':'引数と戻り値には、処理に合った型を書く。','csharp':'引数と戻り値には、処理に合った型を書く。','go':'引数と戻り値には、処理に合った型を書く。','rust':'引数と戻り値には、処理に合った型を書く。'}
IO=re.compile(r'System\.in|Scanner|readLine|\bcin\b|getline|process\.stdin|readline|os\.Stdin|bufio|io::stdin|Console\.Read|\binput\(|sys\.stdin|BufferedReader|\bscanf\b|fmt\.Scan',re.I)
DANGER=re.compile(r'(\bkillpg?\s*\(|\braise\s*\(|Process\.Kill|\.kill\s*\(|os\.kill|Runtime\.getRuntime\(\)\s*\.exec|ProcessBuilder|\bsystem\s*\(|\bpopen\s*\(|\bexec[lv]p?e?\s*\(|\bfork\s*\(|child_process|std::process::Command|process::Command|"os/exec"|Process\.Start|syscall\.Kill|libc::kill|\bSIGKILL\b|\bSIGTERM\b|\bSIGABRT\b|\bSIGSTOP\b|\bshutdown\s*\(|\breboot\s*\()')
def prompt(code,lang):
    return (f"次の{LN[lang]}プログラムは、標準入力から値を読み取り、結果を標準出力に書く、動作確認済みのプログラムです。これを、**(1)仕様どおりの処理を行う関数**と、**(2)入出力だけを行うmain(ドライバ)**に分けて、書き直してください。\n\n"
      f"```{lang}\n{code}\n```\n\n条件:\n- 関数は、{LN[lang]}らしい自然なシグネチャにする。{TYPEHINT[lang]}\n"
      "- 入力の読み取りと、出力の整形・表示は、mainだけが行う。**関数の中では、標準入出力を使わない。**\n- 関数の中身は、元のプログラムと同じ動作にする。補助関数が必要なら、関数のコードに含める。\n"
      "- 出力は、次の3つのタグだけで構成する(タグの外には何も書かない):\n<signature>関数宣言の1行(本体なし)</signature>\n<function>\n関数のコード(必要なimportと補助関数を含む。mainは含めない)\n</function>\n<full>\n全体のコード(関数とmain)\n</full>\n- タグの中に、```のコードブロック記号は書かない。")
def parse(t):
    def tag(n):
        m=re.search(r"<"+n+r">(.*?)</"+n+r">",t,re.S); return m.group(1).strip() if m else None
    def sf(c):
        if c is None: return None
        c=re.sub(r"^```\w*\n","",c.strip()); c=re.sub(r"\n```$","",c); return c.strip().strip('`').strip()
    sig,fn,full=sf(tag('signature')),sf(tag('function')),sf(tag('full'))
    if not sig or not fn or not full: return None
    return sig.splitlines()[0].strip().rstrip(';'),fn,full
def check(sig,fn,full):
    if IO.search(fn): return 'fn_has_io'
    toks=sig.split('(')[0].split()
    if not toks or toks[-1] not in fn: return 'sig_not_in_fn'
    full_lines={l.strip() for l in full.splitlines() if l.strip()}
    fl=[l.strip() for l in fn.splitlines() if l.strip()]
    if sum(1 for l in fl if l in full_lines)/max(1,len(fl))<0.9: return 'fn_not_in_full'
    return None
if __name__=="__main__":
    N=int(os.environ.get('FN_PER_LANG','0'))
    progs=[json.loads(l) for l in gzip.open('/tmp/fn_programs.jsonl.gz','rt')]
    if N:
        by=collections.defaultdict(list)
        for p in progs: by[p['lang']].append(p)
        progs=[p for l in by for p in by[l][:N]]
    print('対象',len(progs),dict(collections.Counter(p['lang'] for p in progs)),flush=True)
    cost=[0.0]; lock=threading.Lock(); stat=collections.Counter()
    def work(p):
        for k in range(3):
            tx,u,m=call_ds(prompt(p['code'],p['lang']),max_tokens=4000,reasoning_off=True,temperature=0.3)
            with lock: cost[0]+=u.get('prompt_tokens',0)/1e6*0.06+u.get('completion_tokens',0)/1e6*0.18
            if tx.strip(): break
        r=parse(tx)
        if not r: return p,'parse_fail',None
        sig,fn,full=r
        if DANGER.search(full): return p,'unsafe',None
        err=check(sig,fn,full)
        if err: return p,err,None
        return p,'candidate',(sig,fn,full)
    out=[]
    with ThreadPoolExecutor(30) as ex:
        for p,st,r in ex.map(work,progs):
            stat[(p['lang'],st)]+=1
            if st=='candidate':
                sig,fn,full=r
                out.append({"tid":p['tid'],"lang":p['lang'],"instruction":p['instruction'],"io_pairs":p['io_pairs'],"sig":sig,"fn":fn,"full":full})
    with open('/tmp/fn_candidates.jsonl','w') as f:
        for o in out: f.write(json.dumps(o,ensure_ascii=False)+"\n")
    with gzip.open('/tmp/fn_judge_input.jsonl.gz','wt') as f:
        for o in out:
            f.write(json.dumps({"lang":o['lang'],"tid":o['tid'],"task":{"task":"x","instruction":o['instruction'],"io_pairs":o['io_pairs']},"full_response":f"```{o['lang']}\n{o['full']}\n```"},ensure_ascii=False)+"\n")
    print('費用 $%.3f | 候補 %d / %d'%(cost[0],len(out),len(progs)))
    for l in LN: print(f"  {l:11s}",{s:stat[(l,s)] for s in ('candidate','parse_fail','fn_has_io','sig_not_in_fn','fn_not_in_full','unsafe')})
