import { test } from "node:test";
import assert from "node:assert/strict";
import { greet, name } from "../src/index.js";

test("the package names itself", () => {
  assert.equal(name, "__RK_PROJECT__");
});

test("greet greets", () => {
  assert.equal(greet("tests"), `Hello, tests, from ${name}.`);
});
