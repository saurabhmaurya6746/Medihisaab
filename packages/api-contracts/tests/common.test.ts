import test from "node:test";
import assert from "node:assert/strict";
import { parseRupeesToPaise, rupeesToPaise, formatRupees } from "../src/common.ts";

test("parseRupeesToPaise: standard rupee inputs", () => {
  assert.equal(parseRupeesToPaise("10.50"), 1050);
  assert.equal(parseRupeesToPaise("10.5"), 1050);
  assert.equal(parseRupeesToPaise("10.05"), 1005);
  assert.equal(parseRupeesToPaise("10"), 1000);
  assert.equal(parseRupeesToPaise("0.01"), 1);
  assert.equal(parseRupeesToPaise("0.1"), 10);
});

test("parseRupeesToPaise: edge cases and whitespace", () => {
  assert.equal(parseRupeesToPaise(""), 0);
  assert.equal(parseRupeesToPaise("   "), 0);
  assert.equal(parseRupeesToPaise("0"), 0);
  assert.equal(parseRupeesToPaise("0.00"), 0);
  assert.equal(parseRupeesToPaise("  10.50  "), 1050);
  assert.equal(parseRupeesToPaise(".50"), 50);
  assert.equal(parseRupeesToPaise(".05"), 5);
  assert.equal(parseRupeesToPaise(".5"), 50);
  assert.equal(parseRupeesToPaise(null), 0);
  assert.equal(parseRupeesToPaise(undefined), 0);
});

test("parseRupeesToPaise: fractional rounding beyond 2 decimals", () => {
  assert.equal(parseRupeesToPaise("10.125"), 1013); // rounds up
  assert.equal(parseRupeesToPaise("10.124"), 1012); // rounds down
});

test("parseRupeesToPaise: negative values", () => {
  assert.equal(parseRupeesToPaise("-10.50"), -1050);
  assert.equal(parseRupeesToPaise("-0.01"), -1);
});

test("rupeesToPaise: alias works identical to parseRupeesToPaise", () => {
  assert.equal(rupeesToPaise("10.50"), 1050);
  assert.equal(rupeesToPaise("10"), 1000);
  assert.equal(rupeesToPaise(10.5), 1050);
});

test("formatRupees: formats paise into rupee string", () => {
  assert.equal(formatRupees(1050), "10.50");
  assert.equal(formatRupees(1), "0.01");
  assert.equal(formatRupees(10), "0.10");
  assert.equal(formatRupees(0), "0.00");
  assert.equal(formatRupees(100000), "1000.00");
  assert.equal(formatRupees(-1050), "-10.50");
});
