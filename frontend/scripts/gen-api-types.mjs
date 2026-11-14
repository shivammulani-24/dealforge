// Generate src/api/schema.d.ts from the committed docs/openapi.json (D4-08).
//   node scripts/gen-api-types.mjs          write the file
//   node scripts/gen-api-types.mjs --check  fail if the committed file is stale (CI drift check)
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const spec = new URL("../../docs/openapi.json", import.meta.url);
const out = new URL("../src/api/schema.d.ts", import.meta.url);
const HEADER =
  "/**\n * GENERATED FILE — do not edit by hand.\n" +
  " * Source: docs/openapi.json (committed; the backend CI checks it is current).\n" +
  " * Regenerate with `npm run gen:api`; CI fails if this file is stale.\n */\n\n";

const ast = await openapiTS(JSON.parse(await readFile(spec, "utf8")));
const generated = HEADER + astToString(ast);

if (process.argv.includes("--check")) {
  let current = "";
  try {
    current = await readFile(out, "utf8");
  } catch {
    // missing file is stale by definition
  }
  if (current !== generated) {
    console.error(`${fileURLToPath(out)} is stale: run \`npm run gen:api\` and commit the result.`);
    process.exit(1);
  }
  console.log(`${fileURLToPath(out)} is up to date with docs/openapi.json.`);
} else {
  await writeFile(out, generated);
  console.log(`wrote ${fileURLToPath(out)}`);
}
