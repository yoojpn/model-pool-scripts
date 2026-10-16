// usage: node run_task.mjs <instance_id> <container>
import { Agent } from './agent.js';
import { ServerEngine } from './engine.js';
import fs from 'node:fs';
import { spawn } from 'node:child_process';
const [iid, ctr] = process.argv.slice(2);
const T = JSON.parse(fs.readFileSync('run/tasks.json', 'utf8')).find((t) => t.instance_id === iid);
const cfg = JSON.parse(fs.readFileSync('run/infer.json', 'utf8'));
const engine = new ServerEngine(cfg.url, cfg.key || ''); await engine.load();
const PY = process.env.CTR_PY || 'python3';
const tool = (name, args) => new Promise((res) => {
  const p = spawn('docker', ['exec', '-i', ctr, PY, '/toolrun_ctr.py', '/testbed']);
  let out = ''; p.stdout.on('data', (d) => (out += d)); p.stderr.on('data', () => {});
  p.on('close', () => { try { res(JSON.parse(out)); } catch { res({ ok: false, error: 'tool runner failed: ' + out.slice(0, 200) }); } });
  p.stdin.end(JSON.stringify({ name, args }));
});
const api = { tool };
const m = { id: iid, steps: 0, toolCalls: 0, toolFail: 0, nudges: 0, err: '', final: '', calls: [] };
const hooks = {
  onStatus() {}, onFiles() {}, onRate() {}, onPlan: (p) => { m.plan = p; },
  onAssistantStart: () => { m.steps++; return { delta() {}, done() {} }; },
  onToolStart: (c) => { m.toolCalls++; const e = { tool: c.name, a: JSON.stringify(c.arguments).slice(0, 200) }; m.calls.push(e);
    return { update() {}, finish: (r) => { const f = r.ok === false || ((c.name === 'bash' || c.name === 'shell_task') && r.exit_code !== 0); if (f) m.toolFail++; e.fail = f; e.out = (r.error || r.output || '').toString().slice(-160); } }; },
  onNudge: () => { m.nudges++; }, onReplan() {}, onDone: (d) => { m.final = d.content || ''; }, onAborted() {}, onError: (e) => { m.err = String(e.message || e); },
};
const agent = new Agent({ engine, api, hooks, settings: { maxSteps: +(process.env.MAXSTEPS || 20), maxTokens: 1500, temperature: 0.4, lora: process.env.CODER_LORA ? +process.env.CODER_LORA : null, reportLora: 2, extraSystem: null, replan: false, freePlan: !!process.env.FREE_PLAN } });
const prompt = `次の GitHub issue を解決してください。カレントディレクトリ(/testbed)に ${T.repo} のソースがあります。既存のテストファイルは変更しないでください。\n\n${T.problem_statement}`;
try { await Promise.race([agent.run({ text: prompt, history: [], thinking: false }), new Promise((_, r) => setTimeout(() => r(new Error('task timeout')), +(process.env.TASK_TIMEOUT || 900) * 1000))]); } catch (e) { m.err = String(e.message || e); agent.stop(); }
fs.mkdirSync('out', { recursive: true });
fs.writeFileSync('out/meta.json', JSON.stringify(m, null, 1));
process.exit(0);
