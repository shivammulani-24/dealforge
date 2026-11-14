/**
 * Recorded fixtures must match the committed OpenAPI document: every body is validated against
 * the response schema of the operation it was recorded from. This is what makes the typed
 * casts in src/fixtures/index.ts safe, and it fails if the API drifts from the recordings.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import Ajv2020 from "ajv/dist/2020";
import { describe, expect, it } from "vitest";

import { recorded, type RecordedName } from ".";

const spec = JSON.parse(readFileSync(resolve(__dirname, "../../../docs/openapi.json"), "utf8")) as {
  paths: Record<
    string,
    Record<string, { responses: Record<string, { content?: Record<string, { schema: unknown }> }> }>
  >;
  components: { schemas: Record<string, unknown> };
};

const ajv = new Ajv2020({ strict: false, allErrors: true });
// The formats the document uses, checked rather than ignored.
ajv.addFormat("date", /^\d{4}-\d{2}-\d{2}$/);
ajv.addFormat("date-time", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/);
ajv.addSchema({ $id: "openapi", components: spec.components });

function validatorFor(schema: unknown) {
  const rewritten = JSON.parse(
    JSON.stringify(schema).replaceAll('"#/components/', '"openapi#/components/'),
  ) as object;
  return ajv.compile(rewritten);
}

const SUCCESS: RecordedName[] = [
  "health",
  "dashboard",
  "financials",
  "historicalAnalysis",
  "preview",
  "run",
  "runsPage",
  "sensitivityWaccG",
  "sensitivityInvalid",
  "sensitivityNegative",
];

describe("recorded fixtures", () => {
  it.each(SUCCESS)("%s validates against its documented response schema", (name) => {
    const fx = recorded[name];
    const { method, path, status } = fx.$recorded.operation;
    const schema =
      spec.paths[path]?.[method]?.responses[String(status)]?.content?.["application/json"]?.schema;
    expect(schema, `${method} ${path} ${String(status)} documented`).toBeDefined();
    const validate = validatorFor(schema);
    const ok = validate(fx.body);
    expect(validate.errors ?? []).toEqual([]);
    expect(ok).toBe(true);
  });

  it("the frozen run's stored inputs validate as DcfInputsIn", () => {
    const validate = validatorFor({ $ref: "#/components/schemas/DcfInputsIn" });
    expect(validate(recorded.run.body.inputs)).toBe(true);
  });

  it("strict validation really rejects drift (planted extra field and wrong type)", () => {
    const validate = validatorFor({ $ref: "#/components/schemas/SensitivityCellOut" });
    const cell = recorded.sensitivityWaccG.body.cells[0]![0]!;
    expect(validate(cell)).toBe(true);
    expect(validate({ ...cell, extra: 1 })).toBe(false);
    expect(validate({ ...cell, change_abs: "1.0" })).toBe(false);
  });

  it.each(["errorCalculation", "errorValidation"] as const)(
    "%s is a well-formed error envelope",
    (name) => {
      const fx = recorded[name];
      expect(fx.$recorded.operation.status).toBe(422);
      expect(fx.body.status).toBe(422);
      expect(["calculation", "validation"]).toContain(fx.body.error_type);
      expect(fx.body.errors.length).toBeGreaterThan(0);
    },
  );

  it("all fixtures were recorded on the current engine version and are synthetic", () => {
    for (const fx of Object.values(recorded)) {
      expect(fx.$recorded.engine_version).toBe(recorded.health.body.engine_version);
      expect(fx.$recorded.source).toMatch(/synthetic/);
    }
    expect(recorded.run.body.context.company.is_synthetic).toBe(true);
  });

  it("the recorded KA-DCF-03 run ties to the Phase 3 known answer (31.2150)", () => {
    expect(recorded.run.body.result.per_share.value_per_share.toFixed(4)).toBe("31.2150");
    expect(recorded.run.body.input_hash).toBe(
      "sha256:37c66a5382d863399822cc79268966c803179e0fae0d36679fc0c867efcf8114",
    );
  });
});
