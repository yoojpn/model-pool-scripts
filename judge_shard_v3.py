import json, subprocess, sys, os, shutil, tempfile, re, argparse, urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--shard", type=int, required=True)
parser.add_argument("--total", type=int, required=True)
parser.add_argument("--orig_shard18_half", type=int, default=-1)
args = parser.parse_args()

URLS = {
    "javascript": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_javascript.jsonl?x-goog-signature=80ea6d7d3e74d803f92bbb56ecfe44274b279b28eae5247e140ab7233b8ee8aed0ca287f68df0d73ef513b4884237734fccdd5b71359d710c7827e3304dc7b29a7f63a4d0d9f5de2e2f6e20418c9741342a3fe6b15f1230d1362fbc2117539d767474f61e885ad86ef4794e34b0f42540c52c0f74ae53ae1123c7fc2461ab8720f976f8adcda692386f1ba40a0cac1c763bcc9d896014c65899f62c1d9c0be4d18586c279437263994b5bea5c571803451996a59a1bf5455b9e94ee6e97a907f79a846c7e463f97aba6f3cf91e3afb398c10371a0150fc7da95185307d7f0ea31452ed03e4ae40d72c427df74aa556a879194ce003723adfb4474e008caada75&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111512Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "typescript": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_typescript.jsonl?x-goog-signature=135e226227f8606d8b104b6bbff20fdf81a1f5386ea7e79f09167c4b58a01fc7c73d5779c35a47ef1a8282ac4a71a369c2436153384c64da26871d1cc32d08507aff2f9d0ed3c5abec2fa10dc5046891c7367e34299c7ad8f68e7fd7b7352438c2b5ce5c45740038b1f9e4c3b448cfd32d807cb0da09f8707c992f1dabf4469840b525ec393225a4d227497f31ff7cf25468589b8b72b3a39aee7e274c18f30e7eac1fb077031244cb3e922966e40ab7696b812d384fea479f981b8575a9fc0623f58807814862f1ed4034a89757f0b6e95dd6da2928a3d3a6ad0a1563c99cdfc18c42b6a7dc19fae7177f3bc1f90f096586e3baf4cc8f9525291cb3ff76bce1&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111514Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "java": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_java.jsonl?x-goog-signature=587e8afaa654dc677a5093f688f037cb3c63386f407268a69f4666c11374ecb456525fa9477dfbca569e4189355164789c2158efe470155fa19cf64a844b5bc56e027dfad3e3fe7fca791136d7fb90bea650ca4ec6d6db419f6c3f412a0db4fb3da1c978e2db000296c0339e97df52c115a43b0a35a32a049e43fd48db242007272b3ada24af5c3fbcbd7bf4023efc84d4f66f0302068693d38cf7d16efaa29058a7c4f463df1197dd2e944e5c8ee6f8f806827e79d9ab461f9c09130bfefe8fc58b2573b7cbad55f023f21f7b1ec6efbafc659d3185a578badd7d2e0270517b0f5e4f9b5e39514b01a347f9092e88a6cac066d27fc1f39138f732e2fb7338bc&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111515Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "cpp": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_cpp.jsonl?x-goog-signature=1fdf64f625b33e3017c3ba100472cc53b8339706cb778e18b9a67a81e0b36c5ea46d571018645eac5d19563c89bc6d211c9f2739612995bcf6c9b987487444c7fc672e9a3ebbf8d5585c1d0382df1f07fe3d96c3134c4dc8954dba7da0c0d12c4ac91c518b65e8808e5bdb4ad85a303fe92e495e70f64aa7ae26fe792f53885eb0d9ef09dd005886d567eb93297593c53795541cc3a997b86d26115a90d0bdad6d2bba5014b70445dc9bb9957e24bd32c35fedebffedf113c9ee657029c16c99ce436dd9f8c5de433b6a0aba19cb77e3e35e1b223a7a88d1a51403cdb23f8664ff346d2421504065e471d97dfeac0020cb5fdb409235ba00809adbafa0d32552&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111517Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "csharp": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_csharp.jsonl?x-goog-signature=2c152e86489d56a67089a734469fc1c4ad9c9fe1a1d7c0af7673a8f99e681186e61864d46b314776914da9dd70329794a9f6a2fa8662303a9204ab9320a51988ad32e90a1c140770ff740d5f4f94bc7d2022372ff145175066be9dd3b49be8607f71ce111afd990a47c8c568772b0c65e55001ea9f2332aba842748a94315b17d48bc517832b2240d6129ac33631b14364ad81d8bf332a581bcdd0099d8fd279c467874d1eb4b868ba2f292433813390579cf87a2e56ac28758e32ce2da3a2a50818ac58368776ca42d4e5948ecfc71c592c441ea51dc8570951123f81bf05a65c6e3fbebf3765c8fb3ffc34d3ae8081e2a3d8439b23e1dd15c955199a9a5365&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111519Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "go": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_go.jsonl?x-goog-signature=581fe0a9ea89a3ff917a6284cc45ad1442ae2f69dc92788ea8fa3eeb6a123bee7790022486af8013aa5bb8b0cf1a040415fdf1f1a44456dd457ddaa93bdcd4c5d8d295f3047d7c67a6b894613371d94b10013653b95df4a2cf604582796249f0024fc1da9e7ba3650d015c92a766ef888ab23769aac0cc18a52d11b7854dc170be5952eb5c58c24b5fbab8e17b2cc5c8fe5f5d9b1798598b7b964f235637b95aeaa026f588c165943e48a94da2a73d9087fa33ab8cb2faf9add9bd55fdfc528c1c12a10b9c414852c71514c71934dc8efc6115dd0965e46738389db13fbe0d37a4a294ac7a1cd82a964df131779ce03db2ff45294045fd6b1e48e8b97cc5bd7d&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111520Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "rust": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_rust.jsonl?x-goog-signature=52c9b41e6aa814199ce33223f861efb857c69ec969de05fa20e4a8dd48f480b26bb429e75691c55b3f68d4f91cd1093f4b54158cea4cc6729c4ec9f99f748354ae561296eb4d282e8af11067497e92deb3021f4a05f1af3ae0c9ea739e28e4783a794d370ceaba6cf041ae4a2c5fde63804fe00facbbc776a3dd413a5e2098cad68a7f3773d077d3b6659307b554f03b91f4dcb75e6dd25e80161ae6769fa701053e640e07d4ed72fa69de2139929f4c0f62f51c7f19e6be29b5f68cc3fc9af30f4eaab324d179f6012d303ae3ba180bea89dc7cc8130e6e852e94fe56f25a3e86d0b8242ff16e2bd885edb8ba6ae0041e1b752ec6183073ffa3ee0f504577d0&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T111522Z&x-goog-expires=86400&x-goog-signedheaders=host",
}

JAPANESE_PUNCTUATION_MAP = str.maketrans({
    "。": ".", "、": ",", "「": '"', "」": '"', "『": '"', "』": '"',
    "・": ",", "　": " ", "：": ":", "；": ";",
})

def clean_code(code):
    return code.translate(JAPANESE_PUNCTUATION_MAP)

def extract_code_block(text, lang_tag=None, strict=False):
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    if lang_tag:
        matches = re.findall(rf"```{re.escape(lang_tag)}\n(.*?)```", text, re.DOTALL)
        if matches:
            return clean_code(matches[-1].strip())
        if strict:
            return None
    matches = re.findall(r"```\w*\n(.*?)```", text, re.DOTALL)
    if matches:
        return clean_code(matches[-1].strip())
    return None

def value_repr(value):
    if isinstance(value, bool): return "true" if value else "false"
    if isinstance(value, list): return f"{len(value)}\n" + " ".join(str(v) for v in value)
    if value is None: return ""
    return str(value)

def build_stdio_pairs(io_pairs):
    out = []
    for pair in io_pairs:
        stdin_lines = [value_repr(a) for a in pair["args"]]
        out.append({"stdin": "\n".join(stdin_lines), "expected_stdout": value_repr(pair["expected"])})
    return out


import signal, resource

def _limit_mem():
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))

def sp_run(cmd, input=None, capture_output=True, text=True, timeout=None, cwd=None):
    """subprocess.run相当。タイムアウト時にプロセスグループごと強制終了する(孫プロセスの残留防止)。
    ネイティブ実行ファイル(a.out)にはメモリ上限3GBを設ける。"""
    pre = _limit_mem if str(cmd[0]).endswith("a.out") else None
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=text, cwd=cwd, start_new_session=True, preexec_fn=pre)
    try:
        out, err = p.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
        p.communicate()
        raise
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)  # 正常終了後も残留プロセスを掃除
        except Exception:
            pass
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)

def run_lang(lang_key, code, stdin_text, tmpdir):
    ext_map = {"javascript": ".js", "typescript": ".ts", "go": ".go", "cpp": ".cpp", "rust": ".rs", "java": ".java", "csharp": ".cs"}
    code_path = os.path.join(tmpdir, f"Main{ext_map[lang_key]}")
    with open(code_path, "w") as f:
        f.write(code)
    try:
        if lang_key == "javascript":
            p = sp_run(["node", code_path], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "typescript":
            p = sp_run(["npx", "ts-node", code_path], input=stdin_text, capture_output=True, text=True, timeout=20)
        elif lang_key == "go":
            p = sp_run(["go", "run", code_path], input=stdin_text, capture_output=True, text=True, timeout=20)
        elif lang_key == "cpp":
            exe = os.path.join(tmpdir, "a.out")
            c = sp_run(["g++", code_path, "-o", exe], capture_output=True, text=True, timeout=20)
            if c.returncode != 0:
                return "", c.stderr
            p = sp_run([exe], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "rust":
            exe = os.path.join(tmpdir, "a.out")
            c = sp_run(["rustc", code_path, "-o", exe], capture_output=True, text=True, timeout=30)
            if c.returncode != 0:
                return "", c.stderr
            p = sp_run([exe], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "java":
            m = re.search(r'public\s+class\s+(\w+)', code)
            cname = m.group(1) if m else "Main"
            jpath = os.path.join(tmpdir, f"{cname}.java")
            if os.path.abspath(jpath) != os.path.abspath(code_path):
                shutil.copy(code_path, jpath)
            c = sp_run(["javac", jpath], capture_output=True, text=True, timeout=20, cwd=tmpdir)
            if c.returncode != 0:
                return "", c.stderr
            p = sp_run(["java", "-cp", tmpdir, cname], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "csharp":
            proj = os.path.join(tmpdir, "proj")
            os.makedirs(proj, exist_ok=True)
            sp_run(["dotnet", "new", "console", "-o", proj, "--force"], capture_output=True, text=True, timeout=30)
            shutil.copy(code_path, os.path.join(proj, "Program.cs"))
            c = sp_run(["dotnet", "build", proj, "-o", os.path.join(proj, "out")], capture_output=True, text=True, timeout=60)
            if c.returncode != 0:
                return "", c.stderr
            dlls = [f for f in os.listdir(os.path.join(proj, "out")) if f.endswith(".dll") and "proj" in f.lower()]
            if not dlls:
                return "", "dll not found"
            p = sp_run(["dotnet", os.path.join(proj, "out", dlls[0])], input=stdin_text, capture_output=True, text=True, timeout=10)
        else:
            return "", "unsupported"
        return p.stdout, p.stderr
    except Exception as e:
        return "", str(e)

all_entries = []
for lang_key, url in URLS.items():
    print(f"ダウンロード中: {lang_key}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = resp.read().decode("utf-8")
    for line in data.splitlines():
        if line.strip():
            try:
                e = json.loads(line)
            except Exception:
                continue  # 不正な形式の行はスキップする
            all_entries.append((lang_key, e))

print(f"全体件数: {len(all_entries)}", flush=True)
if args.orig_shard18_half >= 0:
    # 旧shard18(半分=1050件の、さらに半分=525件分)を、4分割する
    orig18_half1 = [item for i, item in enumerate(all_entries) if i % 20 == 18][525:]  # halfだった分の後半
    n = len(orig18_half1)
    q = n // 4
    boundaries = [0, q, q*2, q*3, n]
    i0, i1 = boundaries[args.orig_shard18_half], boundaries[args.orig_shard18_half + 1]
    my_shard = orig18_half1[i0:i1]
    shard_label = f"18-half1-q{args.orig_shard18_half}"
else:
    my_shard = [item for i, item in enumerate(all_entries) if i % args.total == args.shard]
    shard_label = str(args.shard)
print(f"このシャード({shard_label})の件数: {len(my_shard)}", flush=True)


out_path = f"output_v2_shard_{shard_label}.jsonl"
fout = open(out_path, "w")
counts = {}

def emit(rec):
    counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

for i, (lang_key, e) in enumerate(my_shard):
    task = e.get("task", {})
    base = {"lang": lang_key, "task_name": task.get("task", ""), "instruction": task.get("instruction", ""),
            "io_pairs": task.get("io_pairs", []), "full_response": e.get("full_response", "")}
    if e.get("error") or not e.get("full_response"):
        emit({**base, "status": "generation_error", "stderr": str(e.get("error", ""))[:500]})
        continue
    code = extract_code_block(e["full_response"], lang_tag=lang_key, strict=True)
    if not code:
        emit({**base, "status": "no_code_block"})
        continue
    stdio_pairs = build_stdio_pairs(task.get("io_pairs", []))
    if not stdio_pairs:
        emit({**base, "status": "no_io_pairs", "code": code})
        continue
    pair = stdio_pairs[0]
    with tempfile.TemporaryDirectory() as tmpdir:
        stdout, stderr = run_lang(lang_key, code, pair["stdin"], tmpdir)
    ok = stdout.strip() == pair["expected_stdout"].strip()
    rec = {**base, "code": code, "stdin": pair["stdin"], "expected_stdout": pair["expected_stdout"][:1500]}
    if ok:
        rec["status"] = "passed"
    else:
        rec["status"] = "failed"
        rec["actual_stdout"] = stdout[:1500]
        rec["stderr"] = stderr[-2500:]
    emit(rec)
    if (i + 1) % 100 == 0:
        fout.flush()
        print(f"  {i+1}/{len(my_shard)}件処理済み {counts}", flush=True)

fout.close()
print(f"シャード{shard_label}完了: {counts}", flush=True)
