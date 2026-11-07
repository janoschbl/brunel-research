import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import vm from 'node:vm';

const root = fileURLToPath(new URL('../', import.meta.url));
const html = readFileSync(join(root, 'main/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const tick = () => new Promise(resolve => setImmediate(resolve));

async function page() {
  const nodes = Object.fromEntries(['state', 'error', 'sent', 'start', 'stop'].map(id => [id, { id, textContent: '', disabled: false }]));
  const calls = [];
  let response = { running: false, sent: 0, error: '' }, ok = true, failure;
  let poll, period, nextGate;
  vm.runInNewContext(script, {
    document: {
      querySelector: selector => nodes[selector.slice(1)],
      querySelectorAll: () => [nodes.start, nodes.stop],
    },
    fetch: async (path, options) => {
      calls.push({ path, options });
      const current = response, currentOk = ok;
      const gate = nextGate;
      nextGate = undefined;
      if (gate) await gate;
      if (failure) throw Error(failure);
      return { ok: currentOk, json: async () => current };
    },
    setInterval: (fn, ms) => { poll = fn; period = ms; },
  });
  await tick();
  return { nodes, calls, poll, period,
    reply: (value, success = true) => { response = value; ok = success; },
    fail: message => { failure = message; },
    holdNext: () => { let release; nextGate = new Promise(resolve => { release = resolve; }); return release; },
  };
}

test('literal payload compiles and matches all 259 bytes', () => {
  const dir = mkdtempSync(join(tmpdir(), 'buscheck-payload-'));
  try {
    const result = spawnSync('cc', ['-std=c11', '-Wall', '-Wextra', '-Werror', '-I', join(root, 'main'), join(root, 'tests/payload_test.c'), '-o', join(dir, 'payload')], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const run = spawnSync(join(dir, 'payload'), [], { encoding: 'utf8' });
    assert.equal(run.status, 0, run.stderr);
    assert.match(run.stdout, /PASS: 259 fixed bytes/);
  } finally { rmSync(dir, { recursive: true }); }
});

test('page uses only local requests and has phone viewport', () => {
  assert.doesNotMatch(html, /https?:\/\/|<link|<script\s+src|@import/);
  assert.match(html, /name="viewport"/);
  assert.ok(Buffer.byteLength(html) < 4096);
});

test('loads stopped status and polls once per second without caching', async () => {
  const p = await page();
  assert.equal(p.nodes.state.textContent, 'Stopped');
  assert.equal(p.calls[0].path, '/status');
  assert.equal(p.calls[0].options.cache, 'no-store');
  assert.equal(p.period, 1000);
  p.reply({ running: true, sent: 2, error: '' });
  await p.poll();
  assert.equal(p.nodes.state.textContent, 'Running');
  assert.equal(p.nodes.sent.textContent, 2);
});

test('Start and Stop use POST and show confirmed state', async () => {
  const p = await page();
  p.reply({ running: true, sent: 1, error: '' });
  await p.nodes.start.onclick();
  assert.equal(p.calls.at(-1).path, '/start');
  assert.equal(p.calls.at(-1).options.method, 'POST');
  assert.equal(p.nodes.state.textContent, 'Running');
  p.reply({ running: false, sent: 1, error: '' });
  await p.nodes.stop.onclick();
  assert.equal(p.calls.at(-1).path, '/stop');
  assert.equal(p.nodes.state.textContent, 'Stopped');
  assert.equal(p.nodes.stop.disabled, false);
});

test('controller errors remain visible and buttons recover', async () => {
  const p = await page();
  p.reply({ running: false, sent: 0, error: 'Bluetooth not ready' }, false);
  await p.nodes.start.onclick();
  assert.equal(p.nodes.error.textContent, 'Bluetooth not ready');
  assert.equal(p.nodes.state.textContent, 'Stopped');
  assert.equal(p.nodes.start.disabled, false);
});

test('network errors display unavailable, not a false running state', async () => {
  const p = await page();
  p.fail('Connection lost');
  await p.poll();
  assert.equal(p.nodes.state.textContent, 'Unavailable');
  assert.equal(p.nodes.error.textContent, 'Connection lost');
});

test('a slow status poll cannot overwrite a newer Start confirmation', async () => {
  const p = await page();
  const release = p.holdNext();
  const oldPoll = p.poll();
  p.reply({ running: true, sent: 1, error: '' });
  await p.nodes.start.onclick();
  assert.equal(p.nodes.state.textContent, 'Running');
  release();
  await oldPoll;
  assert.equal(p.nodes.state.textContent, 'Running');
  assert.equal(p.nodes.sent.textContent, 1);
});
