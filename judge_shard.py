import json, subprocess, sys, os, shutil, tempfile, re, argparse, urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--shard", type=int, required=True)
parser.add_argument("--total", type=int, required=True)
args = parser.parse_args()

URLS = {
    "javascript": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_javascript.jsonl?x-goog-signature=3fe757760a0783a7b92170f1c234f347338cd8172ae67f929020268e20d6449cdc72e39c31805913798d28f7a0d6274ba4938a98afcaaee43b84a5bc6a71c2d83dc58d59e85dc7eb12545d2bb56c3f99bf874d125a65d15d1523b0b3cf55f75845de3c573a4285afac7d38bfce2069b977c930d9976688ea7c682473e0674d67d081ecbbe98990fb7d652235204cb580f425b067e77e14769c1334e2f433bfc9edd2c688a3ace0ef7182c841bd604df153d0aa1843f48ea82afc8897821ac31b8de778b3c7a22e31fb7508a1027beb3e09ca20f954218a5ad92abb9ef6c7c16e1fc4fa25f98dc5293008b11b7d500322d1d7d47b08c24dfbc0635b2d4fd00d9b&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110815Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "typescript": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_typescript.jsonl?x-goog-signature=611e3646d7cfcf59453df3ccaac03eadeeb930410d182fd37daa248918d8823856f86ebc06846b719bd8e35327db17e6210bf19166530bb0a98aea263070e20727b5f9e452728426d352fa19c438751941fd37db5e51bd89929878024f773a282e302a9e31f4418ff5842e496b8f38a74973b451c1a9e2d48c7b88ae4e8811e8c598e3ab3c23f6d5f842d7a0346e9b24044002c6ec6cc2fc32e079e05fbd8fce1c9d4d0882da70d20de3afa8b62a57daeeb379d1b202027ed2f9de7652136f785a579597566a56b5f06df8c4b238bd9e22ec9f622504baa5a4a93831da99ddab5224e2e2a99246d15780d57a4991e66108a685248cd0704b0c7b659dc65dc4d5&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110817Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "java": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_java.jsonl?x-goog-signature=961c026727db391962db60fd87977d49fadcef17f2090a96a6889b3fd7a1d0a4cb4bc89bc1688b7bb91c9c676e3f0a83e280c7370bad548907fc8c3be26acd73f16643d5c5220c6fe7078eff376f444ecc5981e745d35f9c9cb23083bfbdc3166e76a97873a2a8fdfac2feb208257b9e65dd448b93b7c0923bc0f04dcd1a09ac0c5323b72858e717e40ebe544ed75b55fbfacd2913d663ca8ecef7b4b76284dead08c5d736b6eb0c0aa2a0034a1668ac70edf5b54267c46a56bca0e0de4ad86ecd89f9898714026099a25431429f456e6df5ffc76962ef07bedcbfb7e2bd8cbf2a19cbbbe0ece49487b30159f437dea17153b877866cef2cc58db50e76fe3d0f&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110819Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "cpp": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_cpp.jsonl?x-goog-signature=05198229e842379b9834be1d55744e1390c7ec936248da3a1ea131de99959b4f09faf94708e0f2c2a33b5378f264578f683690d9b47ebbcb9b71edda1ede399ddbe9ccadc7ccdb98a30db6501c71cb04c38681456770a975c1c242131acc83805abb68547f48260346e41a73fa797155e2d4d053feb5af92209a04bc093c80e25eaaddde9d6313080869b5f11d24b432f47d83b62d8938042980a8dd6239b89bf7a0ae799a53a7fe2abf815e517f2aa07d6428426088b5b25abcc6db58ee5ef43d5384fd250985c62e34a5c68a6bdcaf20e81ea68548dd4f6fce852833b0dc543c8ee76281b40ed6950e845156e8fb99f5e98251c3d2983efd3cab10cbdda4a8&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110821Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "csharp": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_csharp.jsonl?x-goog-signature=7c5b528e3a6d03388bb4b2912da1d0aedc4a0bb36d6b034dda1309ac40e2e041e65b6b2eb7ea6f5f4ce1b9ab580a80075d9afaba3894e151945678222eead547c8686c6701104110b3c2934ae126c276a7e5445168666ba7544d80d6f99b9696c2765c6f38a2eea03824aad962dab97f633b0afcafb774c89905453c61207bc528ce0ef2dc0d2191c9a5a18710311d298eaf72dcc60a7c39ff37e9da9ab55d86fd1719924e7af50656d799b62882d8ce87f132dd773998189cade7b1073eef11a27d844d43a13ebc0d73113c1c49f9b4a19b4140388d62ad7b87c815a9ff59a67b3bc6bfa25bd358d3b2e8f386166a674a4cac24517e0b8613ec6be875b61f5f&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110822Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "go": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_go.jsonl?x-goog-signature=98bf2be97763cf0ef7e7a663e7b2a9c5961a5cd134670db1b60b4f94399873d36ab84f68454a10b23dba1d800e206b447369baa168d88201084b0b7c532071893e98f5da3f6d81b79fe1313fe3aec60dae377836e002965f0ed53669a8785a16e9046622ae5ac84899e54a2bb0aea55901a12cd4b3365a54ce0b338ba3d2c01ff599a46fce0b85725c0ff44d5f7b6660d74ff5f7a4cd156af8f2764e9e06d7d2b2f5a01a6c1419ca65aaddbd2e9ff88ff4f1a139501ca360f618f9b2c57c6c38c27f3b51ef4785895f4562e4cabebd8dafdc1872af5025674df5032d6c35b2906b7455b0b69d2b4fe106031a206114f05c528b172d1d8bcc99e28b44db778fd1&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110824Z&x-goog-expires=86400&x-goog-signedheaders=host",
    "rust": "https://storage.googleapis.com/dataset_bucket01/judge_data/direct_phi4_rust.jsonl?x-goog-signature=4b9457edbd10e6af605067d25585adc1fc7821dc7a31df53daa5699b22097f9e7273f2e77442b9685c27d4b76eb04c5725805d948cbc5ef58538c43ba406cdaa09700950d0733bdc72aa68ce9f72c3ec9dc79aa34d818ed6dba21e69c1083dbb31dbb639ff7f0d79cfdd4af83dac64a66c3a3ff90c804739ea47efe7566eb4b33a93ad6a3ed2fa65aaad9d9e540c12e1c083cf9fab73c81365d4120eef082511bda98fe91025661efd0ebc1da951d225907be2d01dbbeab125d2b93d05a994461786690eb1a7fa1fd024270cb06e5a6ee886ee363ca1024a93f19e0e5caaee6486d0bb93d79dcd2ec227f7ae390b69dea33392efc80b0eee3f04435ae42dac29&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=swebench-runner%40project-532317c9-c2be-4103-98e.iam.gserviceaccount.com%2F20261001%2Fus-central1%2Fstorage%2Fgoog4_request&x-goog-date=20261001T110826Z&x-goog-expires=86400&x-goog-signedheaders=host",
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

def run_lang(lang_key, code, stdin_text, tmpdir):
    ext_map = {"javascript": ".js", "typescript": ".ts", "go": ".go", "cpp": ".cpp", "rust": ".rs", "java": ".java", "csharp": ".cs"}
    code_path = os.path.join(tmpdir, f"Main{ext_map[lang_key]}")
    with open(code_path, "w") as f:
        f.write(code)
    try:
        if lang_key == "javascript":
            p = subprocess.run(["node", code_path], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "typescript":
            p = subprocess.run(["npx", "ts-node", code_path], input=stdin_text, capture_output=True, text=True, timeout=20)
        elif lang_key == "go":
            p = subprocess.run(["go", "run", code_path], input=stdin_text, capture_output=True, text=True, timeout=20)
        elif lang_key == "cpp":
            exe = os.path.join(tmpdir, "a.out")
            c = subprocess.run(["g++", code_path, "-o", exe], capture_output=True, text=True, timeout=20)
            if c.returncode != 0:
                return "", c.stderr
            p = subprocess.run([exe], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "rust":
            exe = os.path.join(tmpdir, "a.out")
            c = subprocess.run(["rustc", code_path, "-o", exe], capture_output=True, text=True, timeout=30)
            if c.returncode != 0:
                return "", c.stderr
            p = subprocess.run([exe], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "java":
            m = re.search(r'public\s+class\s+(\w+)', code)
            cname = m.group(1) if m else "Main"
            jpath = os.path.join(tmpdir, f"{cname}.java")
            if os.path.abspath(jpath) != os.path.abspath(code_path):
                shutil.copy(code_path, jpath)
            c = subprocess.run(["javac", jpath], capture_output=True, text=True, timeout=20, cwd=tmpdir)
            if c.returncode != 0:
                return "", c.stderr
            p = subprocess.run(["java", "-cp", tmpdir, cname], input=stdin_text, capture_output=True, text=True, timeout=10)
        elif lang_key == "csharp":
            proj = os.path.join(tmpdir, "proj")
            os.makedirs(proj, exist_ok=True)
            subprocess.run(["dotnet", "new", "console", "-o", proj, "--force"], capture_output=True, text=True, timeout=30)
            shutil.copy(code_path, os.path.join(proj, "Program.cs"))
            c = subprocess.run(["dotnet", "build", proj, "-o", os.path.join(proj, "out")], capture_output=True, text=True, timeout=60)
            if c.returncode != 0:
                return "", c.stderr
            dlls = [f for f in os.listdir(os.path.join(proj, "out")) if f.endswith(".dll") and "proj" in f.lower()]
            if not dlls:
                return "", "dll not found"
            p = subprocess.run(["dotnet", os.path.join(proj, "out", dlls[0])], input=stdin_text, capture_output=True, text=True, timeout=10)
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
            e = json.loads(line)
            all_entries.append((lang_key, e))

print(f"全体件数: {len(all_entries)}", flush=True)
my_shard = [item for i, item in enumerate(all_entries) if i % args.total == args.shard]
print(f"このシャード({args.shard})の件数: {len(my_shard)}", flush=True)

passed_results = []
for i, (lang_key, e) in enumerate(my_shard):
    if e.get("error") or not e.get("full_response"):
        continue
    code = extract_code_block(e["full_response"], lang_tag=lang_key, strict=True)
    if not code:
        continue
    stdio_pairs = build_stdio_pairs(e["task"].get("io_pairs", []))
    if not stdio_pairs:
        continue
    pair = stdio_pairs[0]
    with tempfile.TemporaryDirectory() as tmpdir:
        stdout, stderr = run_lang(lang_key, code, pair["stdin"], tmpdir)
    if stdout.strip() == pair["expected_stdout"].strip():
        passed_results.append({"task_type": lang_key, "instruction": e["task"].get("instruction", ""),
                                "full_response": e["full_response"]})
    if (i + 1) % 100 == 0:
        print(f"  {i+1}/{len(my_shard)}件処理済み", flush=True)

with open(f"output_shard_{args.shard}.jsonl", "w") as f:
    for r in passed_results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"シャード{args.shard}完了: {len(passed_results)}/{len(my_shard)}件合格", flush=True)
