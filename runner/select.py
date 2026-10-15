import json, random, sys
from datasets import load_dataset
used = set(json.load(open('runner/used_ids.json')))
ds = load_dataset('princeton-nlp/SWE-bench_Verified', split='test')
rows = [r for r in ds if r['instance_id'] not in used]
rows.sort(key=lambda r: r['instance_id'])
random.Random(int(sys.argv[1])).shuffle(rows)
n = int(sys.argv[2]); sel = rows[:n]
json.dump([{k: r[k] for k in ('instance_id','repo','base_commit','problem_statement','test_patch','FAIL_TO_PASS','PASS_TO_PASS','version','patch')} for r in sel], open('run/tasks.json','w'))
print(json.dumps([r['instance_id'] for r in sel]))
