const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function load(path, imports = {}) {
  const code = ts.transpileModule(fs.readFileSync(path, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const sandbox = { exports: {}, require: name => imports[name] || require(name) };
  vm.runInNewContext(code, sandbox);
  return sandbox.exports;
}
const actions = load('src/redux-modules/extraActions.tsx');
const constants = load('src/backend/constants.tsx');
const { controllerSlice } = load('src/redux-modules/controllerSlice.tsx', {
  './extraActions': actions,
  '../backend/utils': { extractCurrentGameId: () => '42' },
  '@decky/ui': { Router: {} },
  '../backend/constants': constants,
});

test('hydration preserves saved Xbox mode and supplies missing game profile', () => {
  let state = controllerSlice.reducer(undefined, actions.setInitialState({
    controllerProfiles: { default: { mode: 'xbox-elite' } }, perGameProfilesEnabled: true,
  }));
  assert.equal(state.controllerProfiles.default.mode, 'xbox-elite');
  assert.equal(state.controllerProfiles['42'].mode, 'xbox-elite');
  state = controllerSlice.reducer(state, controllerSlice.actions.setControllerMode({ mode: 'ds5' }));
  assert.equal(state.controllerProfiles['42'].mode, 'ds5');
  assert.equal(state.controllerProfiles.default.mode, 'xbox-elite');
});

test('fresh install initializes a usable default profile before rendering', () => {
  const state = controllerSlice.reducer(undefined, actions.setInitialState({}));
  assert.equal(state.controllerProfiles.default.mode, 'default');
});

test('hydration honors the per-game default-mode preference', () => {
  const state = controllerSlice.reducer(undefined, actions.setInitialState({
    controllerProfiles: { default: { mode: 'xbox-elite' } }, perGameProfilesEnabled: true,
    advancedOptions: [{ statePath: 'ALWAYS_USE_DEFAULT', currentValue: true }],
  }));
  assert.equal(state.controllerProfiles['42'].mode, 'default');
  assert.equal(state.controllerProfiles.default.mode, 'xbox-elite');
});
