// Types for eslint.rules.js, so the rule tests can import the exact rule definitions.
interface SyntaxRule {
  selector: string;
  message: string;
}
export const noNullishZero: SyntaxRule[];
export const noRawHtml: SyntaxRule[];
export const noArithmetic: SyntaxRule[];
export const noLocalStorageGlobals: { name: string; message: string }[];
export const noLocalStorageProperties: { object: string; property: string; message: string }[];
