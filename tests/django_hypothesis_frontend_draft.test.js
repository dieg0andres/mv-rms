const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../static/rms/draft_shell.js"), "utf8");

test("summary and context focus preserve input; preview submission has no transport", () => {
  const handlers = {};
  const input = { value: "invented unsaved input" };
  let focused = null;
  const summary = { focus: () => { focused = "summary"; } };
  const target = { focus: () => { focused = "context"; } };
  const document = {
    querySelector: () => summary,
    addEventListener: (name, handler) => { handlers[name] = handler; },
    getElementById: id => id === "research-context" ? target : null,
  };
  vm.runInNewContext(source, { document });
  assert.equal(focused, "summary");
  handlers.click({ target: { closest: () => ({ dataset: { focusTarget: "research-context" } }) } });
  assert.equal(focused, "context");
  assert.equal(input.value, "invented unsaved input");
  let prevented = false;
  const status = { textContent: "No save attempted." };
  handlers.submit({
    target: { matches: () => true, querySelector: () => status },
    preventDefault: () => { prevented = true; },
  });
  assert.equal(prevented, true);
  assert.match(status.textContent, /Not saved/);
  assert.equal(input.value, "invented unsaved input");
});

test("unrelated interactions and pages without summaries are safe", () => {
  const handlers = {};
  vm.runInNewContext(source, { document: {
    querySelector: () => null,
    addEventListener: (name, handler) => { handlers[name] = handler; },
    getElementById: () => null,
  } });
  handlers.click({ target: { closest: () => null } });
  handlers.submit({ target: { matches: () => false }, preventDefault: () => { throw Error("Unexpected submit interception"); } });
});
