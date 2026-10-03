const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../static/rms/record_form.js"), "utf8");

function inventedDocument() {
  const handlers = {};
  const status = { textContent: "No new save confirmed." };
  const form = { dataset: {}, addEventListener: (name, callback) => { handlers[name] = callback; }, querySelector: () => status };
  let focused = null;
  const document = {
    querySelector: () => ({ focus: () => { focused = "summary"; } }),
    querySelectorAll: () => [form],
    addEventListener: (name, callback) => { handlers[name] = callback; },
    getElementById: () => ({ focus: () => { focused = "context"; } }),
  };
  const window = { addEventListener: (name, callback) => { handlers[name] = callback; } };
  vm.runInNewContext(source, { document, window });
  return { form, status, handlers, focused: () => focused };
}

test("duplicate submit is blocked while first native submit retains named operation", () => {
  const page = inventedDocument();
  const submitter = { name: "operation", value: "create_case", disabled: false };
  let prevented = 0;
  const event = { submitter, preventDefault: () => { prevented += 1; } };
  page.handlers.submit(event);
  assert.equal(prevented, 0);
  assert.equal(submitter.disabled, false);
  assert.match(page.status.textContent, /awaiting server confirmation/);
  page.handlers.submit(event);
  assert.equal(prevented, 1);
  assert.doesNotMatch(page.status.textContent, /Saved/);
});

test("context focus and back-forward restore preserve input and transport key", () => {
  const page = inventedDocument();
  const input = { value: "invented losing draft" };
  const key = { value: "invented-original-key" };
  assert.equal(page.focused(), "summary");
  page.handlers.click({ target: { closest: () => ({ dataset: { focusTarget: "research-context" } }) } });
  assert.equal(page.focused(), "context");
  page.handlers.submit({ preventDefault: () => {} });
  page.handlers.pageshow();
  assert.equal(page.form.dataset.submitting, undefined);
  assert.equal(input.value, "invented losing draft");
  assert.equal(key.value, "invented-original-key");
  assert.equal(page.status.textContent, "No new save confirmed.");
});

test("non-form pages and unrelated clicks need no browser storage or transport", () => {
  const handlers = {};
  vm.runInNewContext(source, { document: {
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: (name, callback) => { handlers[name] = callback; },
  }, window: { addEventListener: (name, callback) => { handlers[name] = callback; } } });
  handlers.click({ target: { closest: () => null } });
  handlers.pageshow();
});
