import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

import {
  noArithmetic,
  noLocalStorageGlobals,
  noLocalStorageProperties,
  noNullishZero,
  noRawHtml,
} from "./eslint.rules.js";

/**
 * Financial-integrity and security rules (plan sections 1 and 6) are enforced here, so a
 * violation fails `npm run lint` and CI rather than relying on review alone.
 */

export default tseslint.config(
  {
    ignores: [
      "dist",
      "coverage",
      "playwright-report",
      "test-results",
      "src/api/schema.d.ts",
      "eslint.rules.d.ts",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "no-console": "error",
      "no-restricted-globals": ["error", ...noLocalStorageGlobals],
      "no-restricted-properties": ["error", ...noLocalStorageProperties],
      "no-restricted-syntax": ["error", ...noNullishZero, ...noRawHtml, ...noArithmetic],
    },
  },
  {
    // src/lib is the single number-transforming module (display only): arithmetic allowed,
    // the missing-value and raw-HTML rules still apply.
    files: ["src/lib/**/*.ts"],
    rules: { "no-restricted-syntax": ["error", ...noNullishZero, ...noRawHtml] },
  },
  {
    // Tests, e2e and tooling may compute expectations; the R3 and raw-HTML rules still apply.
    files: ["src/**/*.test.{ts,tsx}", "src/test/**", "e2e/**", "scripts/**", "*.config.{ts,js}"],
    rules: {
      "no-restricted-syntax": ["error", ...noNullishZero, ...noRawHtml],
      "no-console": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      // Tests read localStorage only to assert that nothing was written to it.
      "no-restricted-globals": "off",
      "no-restricted-properties": "off",
    },
  },
  {
    files: ["scripts/**/*.mjs", "e2e/**/*.mjs", "*.config.js", "eslint.rules.js"],
    ...tseslint.configs.disableTypeChecked,
    languageOptions: {
      ...tseslint.configs.disableTypeChecked.languageOptions,
      globals: { ...globals.node },
    },
  },
  prettier,
);
