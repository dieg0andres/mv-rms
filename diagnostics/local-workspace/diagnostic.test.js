import assert from "node:assert/strict";
import test from "node:test";

import { classifyNumber } from "./diagnostic.js";

test("classifies deterministic integer samples", () => {
  assert.deepEqual(
    [-3, 0, 8].map((value) => classifyNumber(value)),
    ["odd", "even", "even"],
  );
});

test("rejects non-integer input", () => {
  assert.throws(() => classifyNumber(1.5), {
    name: "TypeError",
    message: "value must be an integer",
  });
});
