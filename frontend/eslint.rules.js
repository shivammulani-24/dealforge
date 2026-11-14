/**
 * Financial-integrity and security lint rules (plan sections 1 and 6), shared by
 * eslint.config.js and the rule tests in src/test/lintRules.test.ts.
 */
// R3: missing stays missing. `x ?? 0` and `x || 0` would turn a missing value into a zero.
export const noNullishZero = [
  {
    selector: "LogicalExpression[operator='??'][right.type='Literal'][right.value=0]",
    message: "Missing values must stay missing (R3): render '—' via lib/format, never `?? 0`.",
  },
  {
    selector: "LogicalExpression[operator='||'][right.type='Literal'][right.value=0]",
    message: "Missing values must stay missing (R3): render '—' via lib/format, never `|| 0`.",
  },
];

// D4-01 hardening: no raw HTML injection.
export const noRawHtml = [
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: "dangerouslySetInnerHTML is banned (CSP / XSS hardening, plan section 1).",
  },
  {
    selector: "MemberExpression[property.name=/^(innerHTML|outerHTML)$/]",
    message: "Writing raw HTML is banned (CSP / XSS hardening, plan section 1).",
  },
];

// Section 6: no financial arithmetic in TypeScript. Outside src/lib (the only module allowed to
// transform numbers, for DISPLAY only) every arithmetic operator and Math.* call is banned.
// This is deliberately broader than "arithmetic on API fields": UI code needs none at all.
export const noArithmetic = [
  {
    selector: "BinaryExpression[operator=/^([-*/%+]|\\*\\*)$/]",
    message:
      "No arithmetic outside src/lib (plan section 6). Financial values come from the API; use template literals for strings.",
  },
  {
    selector: "AssignmentExpression[operator=/^([-*/%+]|\\*\\*)=$/]",
    message: "No arithmetic outside src/lib (plan section 6).",
  },
  {
    selector: "UnaryExpression[operator=/^[-+]$/][argument.type!='Literal']",
    message: "No arithmetic outside src/lib (plan section 6).",
  },
  {
    selector: "MemberExpression[object.name='Math']",
    message: "No Math.* outside src/lib (plan section 6).",
  },
];

// D4-01: the token never goes to localStorage.
export const noLocalStorageGlobals = [
  { name: "localStorage", message: "The token is never stored in localStorage (D4-01)." },
];
export const noLocalStorageProperties = [
  { object: "window", property: "localStorage", message: "Never use localStorage (D4-01)." },
];
