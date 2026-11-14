/**
 * The financial-integrity lint rules really fire (plan section 6): the same rule definitions
 * eslint.config.js uses are run on small code samples.
 */
import { Linter } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

import {
  noArithmetic,
  noLocalStorageGlobals,
  noLocalStorageProperties,
  noNullishZero,
  noRawHtml,
} from "../../eslint.rules.js";

function lint(code: string, { arithmetic }: { arithmetic: boolean }): string[] {
  const linter = new Linter({ configType: "flat" });
  const messages = linter.verify(
    code,
    [
      {
        files: ["**/*.tsx"],
        languageOptions: {
          parser: tseslint.parser,
          parserOptions: { ecmaFeatures: { jsx: true } },
          globals: { window: "readonly", localStorage: "readonly" },
        },
        rules: {
          "no-restricted-syntax": [
            "error",
            ...noNullishZero,
            ...noRawHtml,
            ...(arithmetic ? noArithmetic : []),
          ],
          "no-restricted-globals": ["error", ...noLocalStorageGlobals],
          "no-restricted-properties": ["error", ...noLocalStorageProperties],
        },
      },
    ],
    "probe.tsx",
  );
  return messages.map((m) => m.message);
}

const UI = { arithmetic: true }; // components, features, app, auth, api
const LIB = { arithmetic: false }; // src/lib: display formatting may do arithmetic

describe("integrity lint rules", () => {
  it.each(["const x = api.value ?? 0;", "const x = api.value || 0;"])(
    "R3 bans %s everywhere",
    (code) => {
      expect(lint(code, UI).join()).toMatch(/Missing values must stay missing/);
      expect(lint(code, LIB).join()).toMatch(/Missing values must stay missing/);
    },
  );

  it.each([
    "const ev = pv + tv;",
    "const margin = ebit / revenue;",
    "const g = r.revenue * 1.05;",
    "const d = a - b;",
    "let t = 0; t += x;",
    "const n = -value;",
    "const m = Math.max(a, b);",
    "const p = a ** 2;",
  ])("bans arithmetic outside src/lib: %s", (code) => {
    expect(lint(code, UI).join()).toMatch(/No (arithmetic|Math\.\*) outside src\/lib/);
    expect(lint(code, LIB)).toEqual([]);
  });

  it.each([
    "const label = `${name} (${unit})`;",
    "const ok = value < 0;",
    "const last = rows.at(-1);",
    "const neg = -1;",
    "for (const r of rows) { void r; }",
  ])("allows non-arithmetic UI code: %s", (code) => {
    expect(lint(code, UI)).toEqual([]);
  });

  it("bans raw HTML injection", () => {
    expect(
      lint('const el = <div dangerouslySetInnerHTML={{ __html: "x" }} />;', UI).join(),
    ).toMatch(/dangerouslySetInnerHTML is banned/);
    expect(lint('node.innerHTML = "<b>x</b>";', UI).join()).toMatch(/raw HTML is banned/);
  });

  it("bans localStorage (D4-01)", () => {
    expect(lint('localStorage.setItem("t", token);', UI).join()).toMatch(
      /never stored in localStorage/,
    );
    expect(lint('window.localStorage.setItem("t", token);', UI).join()).toMatch(
      /Never use localStorage/,
    );
  });
});
