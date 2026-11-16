const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync('src/backend/initialize.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const sandbox = { exports: {} };
vm.runInNewContext(code, sandbox);
const { initializeAfterSettings } = sandbox.exports;
const tick = () => new Promise(resolve => setImmediate(resolve));

function setup() {
  let resolve, reject;
  const loaded = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  const events = [];
  const cleanup = initializeAfterSettings(
    () => loaded,
    saved => events.push(['restore', saved.mode]),
    () => { events.push(['listen']); return () => events.push(['unsubscribe']); },
    error => events.push(['error', error.message]),
  );
  return { resolve, reject, events, cleanup };
}

test('slow settings load cannot start listeners that overwrite saved Xbox mode', async () => {
  const s = setup();
  await tick();
  assert.deepEqual(s.events, []);
  s.resolve({ mode: 'xbox-elite' });
  await tick();
  assert.deepEqual(s.events, [['restore', 'xbox-elite'], ['listen']]);
  s.cleanup();
  assert.deepEqual(s.events.at(-1), ['unsubscribe']);
});

test('unmount before load prevents stale state and listener resurrection', async () => {
  const s = setup();
  s.cleanup();
  s.resolve({ mode: 'xbox-elite' });
  await tick();
  assert.deepEqual(s.events, []);
});

test('failed load does not activate listeners or persist defaults', async () => {
  const s = setup();
  s.reject(new Error('backend unavailable'));
  await tick();
  assert.deepEqual(s.events, [['error', 'backend unavailable']]);
});
