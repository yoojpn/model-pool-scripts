// Inference engines. All expose:
//   chat({messages, tools, thinking, max_tokens, temperature, lora, signal, onDelta}) -> {content, reasoning, tool_calls, usage, finish}
//   complete({prompt, stop, max_tokens, temperature, lora, signal, onDelta}) -> {text, usage}
// `lora` is an adapter id (number) or null for the base model.
const N_LORA = (typeof process !== 'undefined' && process.env && +process.env.N_LORA) || 2; // adapters loaded: 0 = plan_verify, 1 = tool_execution (2 = honest, when loaded; set N_LORA=3 then)
const loraField = (id, n = N_LORA) => Array.from({ length: n }, (_, i) => ({ id: i, scale: i === id ? 1 : 0 })); // always explicit: never rely on the server's initial scales

export function parseToolArgs(s) {
  if (s && typeof s === 'object') return s;
  try { return JSON.parse(s || '{}'); } catch { return { _raw: String(s) }; }
}

class Meter {
  constructor() { this.t0 = 0; this.n = 0; this.first = 0; }
  tick() { const now = performance.now(); if (!this.n) { this.first = now; } this.n++; this.t0 = now; return this.rate(); }
  rate() { return this.n > 1 ? (this.n - 1) / ((this.t0 - this.first) / 1000) : 0; }
}

/* ---------- Browser engine: llama.cpp (WebGPU/WASM) via wllama, runtime LoRA ---------- */

// WebGPU diagnostics: try several requestAdapter option sets on the main thread and inside a worker.
const PROBE_SRC = `
const out = {}; const tries = { default: undefined, high: { powerPreference: 'high-performance' }, low: { powerPreference: 'low-power' }, compat: { featureLevel: 'compatibility' }, core: { featureLevel: 'core' } };
(async () => { try { if (!self.navigator?.gpu) { postMessage({ gpu: false }); return; }
  for (const [k, o] of Object.entries(tries)) { try { const a = await navigator.gpu.requestAdapter(o); out[k] = a ? 'ok' : 'null';
    if (a && !out.info) { const i = a.info || {}; out.info = [i.vendor, i.architecture, i.device, i.description].filter(Boolean).join('/'); out.limits = { maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize }; } } catch (e) { out[k] = 'err ' + e.message; } }
  postMessage({ gpu: true, out }); } catch (e) { postMessage({ error: String(e) }); } })();`;
export async function gpuProbe() {
  const run = (w) => new Promise((res) => { w.onmessage = (e) => res(e.data); w.onerror = (e) => res({ error: String(e.message || e) }); setTimeout(() => res({ error: 'timeout' }), 8000); });
  const r = { main: null, worker: null };
  try { if (!navigator.gpu) r.main = { gpu: false }; else { const a = await navigator.gpu.requestAdapter(); r.main = { gpu: true, adapter: a ? 'ok' : 'null', info: a ? [a.info?.vendor, a.info?.architecture, a.info?.description].filter(Boolean).join('/') : '' }; } } catch (e) { r.main = { error: String(e) }; }
  try { const url = URL.createObjectURL(new Blob([PROBE_SRC], { type: 'text/javascript' })); const w = new Worker(url); r.worker = await run(w); w.terminate(); } catch (e) { r.worker = { error: String(e) }; }
  return r;
}

export class WllamaEngine {
  constructor() { this.kind = 'browser'; this.wllama = null; this.info = {}; }
  async load({ base, loras, params = {}, onProgress }) {
    const { Wllama } = await import('./wllama/index.js');
    globalThis.__llog = globalThis.__llog || [];
    const fwd = (k) => (...a) => { globalThis.__llog.push(a.map(String).join(' ')); console[k]?.(...a); const t = a.map(String).join(' ').trim(); if (t && k !== 'debug') onProgress?.({ phase: 'log', text: t.slice(0, 160) }); };
    this.wllama = new Wllama({ default: new URL('./wllama/wllama.wasm', location.href).href }, { parallelDownloads: 4, logger: { debug: fwd('debug'), log: fwd('log'), warn: fwd('warn'), error: fwd('error') } });
    const webgpu = this.wllama.isSupportWebGPU();
    try { this.probe = await gpuProbe(); console.log('[gpuProbe]', JSON.stringify(this.probe)); onProgress?.({ phase: 'log', text: 'WebGPU診断: ' + JSON.stringify(this.probe).slice(0, 400) }); } catch {}
    const loraFiles = [];
    let done = 0;
    for (const l of loras) {
      onProgress?.({ phase: `LoRA ${l.role}`, loaded: done, total: loras.length });
      loraFiles.push({ blob: await fetchCached(l.url, (g, t) => onProgress?.({ phase: `LoRA ${l.role}`, loaded: g, total: t })), scale: 0, role: l.role });
      done++;
    }
    await this.wllama.loadModelFromUrl(base, {
      n_ctx: params.n_ctx ?? 6144, n_batch: 256, n_ubatch: 128, // wasm heap is capped at 4 GiB: keep compute buffers small
      n_gpu_layers: params.cpuOnly ? 0 : 99999,
      flash_attn: true, jinja: true, lora_files: loraFiles, warmup: false,
      progressCallback: ({ loaded, total }) => onProgress?.({ phase: 'モデル', loaded, total }),
    });
    this.info = { webgpu, cpuOnly: !!params.cpuOnly, loras: loras.map((l) => l.role) };
    return this.info;
  }
  async chat({ messages, tools, thinking, max_tokens = 2048, temperature = 0.6, lora, signal, onDelta }) {
    const m = new Meter(); let content = '', reasoning = ''; const calls = []; let finish = null, usage = null;
    const stream = await this.wllama.createChatCompletion({
      messages, tools: tools?.length ? tools : undefined, stream: true, max_tokens, temperature, top_p: 0.95, top_k: 64,
      chat_template_kwargs: { enable_thinking: !!thinking }, lora: loraField(lora), abortSignal: signal,
    });
    for await (const ch of stream) {
      const c = ch.choices?.[0]; if (!c) continue; const d = c.delta || {};
      if (d.reasoning_content) { reasoning += d.reasoning_content; onDelta?.({ reasoning: d.reasoning_content, rate: m.tick() }); }
      if (d.content) { content += d.content; onDelta?.({ content: d.content, rate: m.tick() }); }
      for (const tc of d.tool_calls || []) {
        const i = tc.index ?? 0; calls[i] ||= { id: tc.id || `call_${i}`, name: '', args: '' };
        if (tc.id) calls[i].id = tc.id; if (tc.function?.name) calls[i].name = tc.function.name; if (tc.function?.arguments) calls[i].args += tc.function.arguments;
      }
      if (c.finish_reason) finish = c.finish_reason; if (ch.usage) usage = ch.usage;
    }
    return { content, reasoning, tool_calls: calls.filter(Boolean).map((c) => ({ id: c.id, name: c.name, arguments: parseToolArgs(c.args) })), usage, finish, rate: m.rate() };
  }
  async complete({ prompt, stop, max_tokens = 600, temperature = 0, lora, signal, onDelta }) {
    const m = new Meter(); let text = '';
    const stream = await this.wllama.createCompletion({ prompt, stop, max_tokens, temperature, lora: loraField(lora), stream: true, abortSignal: signal });
    for await (const ch of stream) { const t = ch.choices?.[0]?.text; if (t) { text += t; onDelta?.({ content: t, rate: m.tick() }); } }
    return { text, rate: m.rate() };
  }
  async unload() { try { await this.wllama?.exit(); } catch {} this.wllama = null; }
}

// Resumable download: 4 MB Range chunks, 6 retries each, result cached in Cache API (survives reloads).
async function fetchChunked(url, onBytes) {
  const CH = 4 << 20; let total = null; const parts = []; let got = 0;
  while (total === null || got < total) {
    let ok = false, lastErr;
    for (let t = 0; t < 6 && !ok; t++) {
      try {
        const r = await fetch(url, { headers: { Range: `bytes=${got}-${got + CH - 1}` } });
        if (r.status === 200) { const b = await r.blob(); parts.length = 0; parts.push(b); got = total = b.size; ok = true; break; }
        if (r.status !== 206) throw new Error(`HTTP ${r.status}`);
        total = +r.headers.get('Content-Range').split('/')[1];
        const b = await r.blob(); parts.push(b); got += b.size; ok = true; onBytes?.(got, total);
      } catch (e) { lastErr = e; await new Promise((res) => setTimeout(res, 800 * (t + 1))); }
    }
    if (!ok) throw new Error(`${url}: 取得に失敗しました(通信が不安定です): ${lastErr?.message || lastErr}`);
  }
  return new Blob(parts);
}
async function fetchCached(url, onBytes) {
  let c = null; try { c = await caches.open('agent-lora-v1'); const r = await c.match(url); if (r) return await r.blob(); } catch {}
  const blob = await fetchChunked(url, onBytes);
  try { await c?.put(url, new Response(blob)); } catch {}
  return blob;
}

/* ---------- Server engine: any llama-server (OpenAI-compatible), e.g. on the VM or on your own PC ---------- */
export class ServerEngine {
  constructor(baseUrl, apiKey = '') { this.kind = 'server'; this.base = baseUrl.replace(/\/$/, ''); this.key = apiKey; this.info = {}; }
  get hdr() { return this.key ? { Authorization: 'Bearer ' + this.key } : {}; }
  async load() { const r = await fetch(this.base + '/health'); if (!r.ok) throw new Error('server not ready: HTTP ' + r.status); this.info = { server: this.base }; return this.info; }
  async *sse(url, body, signal) {
    let r; for (let t = 0; ; t++) {   // quick tunnels sometimes answer 502/503 under load: retry before streaming starts
      r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.hdr }, body: JSON.stringify(body), signal });
      if (r.ok || ![502, 503, 504, 429].includes(r.status) || t >= 4) break;
      await new Promise((z) => setTimeout(z, 1500 * (t + 1)));
    }
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status} ${(await r.text()).slice(0, 300)}`);
    const rd = r.body.getReader(); const dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { done, value } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf('\n\n')) >= 0) { const line = buf.slice(0, i).trim(); buf = buf.slice(i + 2);
        if (!line.startsWith('data:')) continue; const p = line.slice(5).trim(); if (p === '[DONE]') return; try { yield JSON.parse(p); } catch {} }
    }
  }
  async chat({ messages, tools, thinking, max_tokens = 2048, temperature = 0.6, lora, signal, onDelta }) {
    const m = new Meter(); let content = '', reasoning = ''; const calls = []; let finish = null, usage = null;
    const body = { messages, stream: true, max_tokens, temperature, top_p: 0.95, top_k: 64, chat_template_kwargs: { enable_thinking: !!thinking }, lora: loraField(lora, this.nLora || N_LORA) };
    if (tools?.length) body.tools = tools;
    for await (const ch of this.sse(this.base + '/v1/chat/completions', body, signal)) {
      const c = ch.choices?.[0]; if (!c) continue; const d = c.delta || {};
      if (d.reasoning_content) { reasoning += d.reasoning_content; onDelta?.({ reasoning: d.reasoning_content, rate: m.tick() }); }
      if (d.content) { content += d.content; onDelta?.({ content: d.content, rate: m.tick() }); }
      for (const tc of d.tool_calls || []) { const i = tc.index ?? 0; calls[i] ||= { id: tc.id || `call_${i}`, name: '', args: '' };
        if (tc.id) calls[i].id = tc.id; if (tc.function?.name) calls[i].name = tc.function.name; if (tc.function?.arguments) calls[i].args += tc.function.arguments; }
      if (c.finish_reason) finish = c.finish_reason; if (ch.usage) usage = ch.usage;
    }
    return { content, reasoning, tool_calls: calls.filter(Boolean).map((c) => ({ id: c.id, name: c.name, arguments: parseToolArgs(c.args) })), usage, finish, rate: m.rate() };
  }
  async complete({ prompt, stop, max_tokens = 600, temperature = 0, lora, signal, onDelta }) {
    const m = new Meter(); let text = '';
    for await (const ch of this.sse(this.base + '/completion', { prompt, stop, n_predict: max_tokens, temperature, stream: true, lora: loraField(lora, this.nLora || N_LORA), cache_prompt: true }, signal)) {
      if (ch.content) { text += ch.content; onDelta?.({ content: ch.content, rate: m.tick() }); } if (ch.stop) break;
    }
    return { text, rate: m.rate() };
  }
}


/* ---------- GPU engine: on-demand Colab T4 (started/stopped by the VM's gpu manager), same llama-server API ---------- */
export class GpuEngine extends ServerEngine {
  nLora = 3; // GPU server loads 3 adapters: 0 plan_verify, 1 tool_execution, 2 honest (final-report rewrite)
  constructor(token, ctl = 'gpu') { super('http://pending'); this.kind = 'server'; this.gpu = true; this.token = token; this.ctl = ctl; this.inflight = 0; this.timer = null; }
  async ctlCall(path, method = 'POST') {
    const r = await fetch(`${this.ctl}/${path}`, { method, headers: { 'X-Agent-Token': this.token } });
    if (r.status === 401) throw new Error('トークンが違います。');
    return await r.json();
  }
  async ensureReady(onProgress) {
    let st = await this.ctlCall('touch'); const t0 = Date.now();
    if (st.state === 'ready') { this.base = st.url; this.key = st.key; return st; }
    if (st.state === 'off') st = await this.ctlCall('start');
    for (;;) {
      const s = Math.round((Date.now() - t0) / 1000);
      onProgress?.({ phase: 'status', text: `GPU(T4)を起動中… ${s}秒(通常40〜60秒)`, frac: Math.min(0.95, s / 60) });
      await sleep(1000); st = await this.ctlCall('status', 'GET');
      if (st.state === 'ready') break;
      if (st.state === 'off') throw new Error('GPUの起動に失敗しました: ' + (st.error || '原因不明'));
      if (s > 240) throw new Error('GPUの起動がタイムアウトしました');
    }
    this.base = st.url; this.key = st.key; return st;
  }
  async load({ onProgress } = {}) {
    const st = await this.ensureReady(onProgress);
    const r = await fetch(this.base + '/health'); if (!r.ok) throw new Error('GPUサーバーに接続できません: HTTP ' + r.status);
    this.info = { server: 'Colab T4', boot_s: st.boot_s }; return this.info;
  }
  async guard(fn) {
    await this.ensureReady(); this.inflight++;
    if (!this.timer) this.timer = setInterval(() => this.ctlCall('touch').catch(() => {}), 30000);
    try { return await fn(); } finally { if (--this.inflight === 0) { clearInterval(this.timer); this.timer = null; } this.ctlCall('touch').catch(() => {}); }
  }
  chat(o) { return this.guard(() => super.chat(o)); }
  complete(o) { return this.guard(() => super.complete(o)); }
  unload() { clearInterval(this.timer); this.timer = null; }
  stopGpu() { return this.ctlCall('stop'); }
}

/* ---------- Mock engine: scripted, for UI/tool-pipeline tests (?mock=1) ---------- */
export class MockEngine {
  constructor() { this.kind = 'mock'; this.info = { mock: true }; }
  async load({ onProgress }) { for (let i = 0; i <= 10; i++) { onProgress?.({ phase: 'mock', loaded: i, total: 10 }); await sleep(30); } return this.info; }
  async stream(text, onDelta, field = 'content') { for (const w of text.match(/\S+\s*/g) || []) { await sleep(8); onDelta?.({ [field]: w, rate: 42 }); } }
  async complete({ prompt, onDelta }) {
    let t;
    if (prompt.includes('完了判定')) t = '{"verdict":"合格","reason":"ok"}';
    else if (prompt.includes('依頼を実装可能な手順へ分解')) t = '{"subtasks":["hello.pyを作成する","実行して出力を確認する"]}';
    else t = '{"tool":"run_bash","arguments":{"command":"ls -la"}}';
    await this.stream(t, onDelta); return { text: t, rate: 42 };
  }
  async chat({ messages, thinking, onDelta }) {
    const used = messages.filter((m) => m.role === 'tool').length;
    if (thinking) await this.stream('まずファイルを作り、実行して確認します。', onDelta, 'reasoning');
    const mk = (name, args) => ({ id: 'call_' + used, name, arguments: args });
    if (used === 0) { await this.stream('hello.py を作成します。', onDelta); return { content: 'hello.py を作成します。', reasoning: '', tool_calls: [mk('write_file', { path: 'hello.py', content: 'print("hello from the sandbox")\n' })], finish: 'tool_calls', rate: 42 }; }
    if (used === 1) return { content: '', reasoning: '', tool_calls: [mk('bash', { command: 'python3 hello.py' })], finish: 'tool_calls', rate: 42 };
    if (used === 2) return { content: '', reasoning: '', tool_calls: [mk('shell_task', { instruction: 'List the files in the current directory' })], finish: 'tool_calls', rate: 42 };
    const t = '`hello.py` を作成し、実行して `hello from the sandbox` と出力されることを確認しました。\n\n```python\nprint("hello from the sandbox")\n```'; await this.stream(t, onDelta);
    return { content: t, reasoning: '', tool_calls: [], finish: 'stop', rate: 42 };
  }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
