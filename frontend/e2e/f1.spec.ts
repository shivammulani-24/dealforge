/**
 * F1 end-to-end checks against the real backend at both viewports (D4-09):
 * - auth flows (redirect with next, register, login, wrong password, logout, 401 on a revoked
 *   token) through the generated typed client;
 * - the design system renders under the production CSP with no console errors;
 * - layout rules: no page-level horizontal scroll; compact rail at 1024; side panels move below;
 *   KPI strip wraps; wide tables scroll inside their container with a sticky first column;
 * - review screenshots of the design-system page.
 */
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, type Page, test } from "@playwright/test";

const PASSWORD = "e2e-password-123";
const SCREENSHOTS = resolve(import.meta.dirname, "../../docs/screenshots/f1");

function uniqueEmail(tag: string): string {
  return `e2e.${tag}.${String(Date.now())}.${String(Math.floor(Math.random() * 1e6))}@example.com`;
}

/** Collect console errors and CSP violations for the whole test. */
function watchConsole(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") problems.push(`${m.type()}: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  return problems;
}

async function registerViaApi(page: Page, email: string): Promise<void> {
  const r = await page.request.post("/api/v1/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(r.status()).toBe(201);
}

async function logInViaUi(page: Page, email: string, next = "/style-guide"): Promise<void> {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(`**${next}`);
}

async function sessionToken(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const raw = window.sessionStorage.getItem("dealforge.session.v1");
    return raw === null ? null : (JSON.parse(raw) as { token: string }).token;
  });
}

test.describe("authentication against the real backend", () => {
  test("an unauthenticated visit goes to login, registration returns to the page", async ({
    page,
  }) => {
    const problems = watchConsole(page);
    const email = uniqueEmail("register");
    await page.goto("/style-guide");
    await expect(page).toHaveURL(/\/login\?next=%2Fstyle-guide$/);
    await page.getByRole("link", { name: "Create one" }).click();
    await expect(page).toHaveURL(/\/register\?next=%2Fstyle-guide$/);
    await expect(page.getByRole("heading", { name: "Create an account" })).toBeVisible();
    await page.getByLabel("Email").fill(email);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL("**/style-guide");
    // Typed client ↔ FastAPI: health and the signed-in user come from the live backend.
    await expect(page.getByTestId("health-status")).toHaveText("ok");
    await expect(page.getByTestId("engine-version")).toContainText("0.1.0");
    await expect(page.getByTestId("engine-version")).toContainText("matches recorded data");
    await expect(page.getByTestId("me-email")).toHaveText(email);
    await expect(page.getByTestId("current-user")).toHaveText(email);
    expect(await page.evaluate(() => window.localStorage.length)).toBe(0);
    expect(problems).toEqual([]);
  });

  test("a wrong password is refused with a clear message", async ({ page }) => {
    const email = uniqueEmail("wrong");
    await registerViaApi(page, email);
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page.getByText("The email or password is incorrect.")).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test("logout revokes the token server-side and clears the client", async ({ page }) => {
    const email = uniqueEmail("logout");
    await registerViaApi(page, email);
    await logInViaUi(page, email);
    const token = await sessionToken(page);
    expect(token).not.toBeNull();
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login\?next=%2Fstyle-guide&reason=logout$/);
    await expect(page.getByText("You have logged out.")).toBeVisible();
    expect(await sessionToken(page)).toBeNull();
    const me = await page.request.get("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${token ?? ""}` },
    });
    expect(me.status()).toBe(401);
  });

  test("a token revoked elsewhere ends the session on the next request (401 flow)", async ({
    page,
  }) => {
    const email = uniqueEmail("revoked");
    await registerViaApi(page, email);
    await logInViaUi(page, email, "/runs");
    const token = await sessionToken(page);
    const revoke = await page.request.post("/api/v1/auth/logout", {
      headers: { Authorization: `Bearer ${token ?? ""}` },
    });
    expect(revoke.status()).toBe(204);
    await page.reload(); // the restored session's first call gets 401
    await expect(page).toHaveURL(/\/login\?next=%2Fruns&reason=unauthorized$/);
    await expect(page.getByText(/no longer valid/)).toBeVisible();
    expect(await sessionToken(page)).toBeNull();
  });
});

test.describe("design system and layout", () => {
  test("serves the SPA with the strict CSP and renders without console errors", async ({
    page,
  }) => {
    const problems = watchConsole(page);
    const email = uniqueEmail("csp");
    await registerViaApi(page, email);
    const nav = await page.goto("/style-guide");
    expect(nav?.headers()["content-security-policy"]).toContain("default-src 'self'");
    expect(nav?.headers()["content-security-policy"]).toContain("style-src 'self'");
    await logInViaUi(page, email);
    await expect(page.getByRole("heading", { name: "Design system", level: 1 })).toBeVisible();
    await expect(page.getByTestId("engine-version")).toContainText("0.1.0");
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    expect(problems).toEqual([]);
  });

  test("layout rules at this viewport, and review screenshots", async ({ page }, info) => {
    // Readable address for the review screenshots; the database is fresh on every run.
    const email = `analyst.${info.project.name}@example.com`;
    await registerViaApi(page, email);
    await logInViaUi(page, email);
    await expect(page.getByTestId("me-email")).toHaveText(email);
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    const viewport = page.viewportSize();
    if (viewport === null) throw new Error("viewport size unknown");
    const width = viewport.width;
    const compact = width < 1280;

    // The page itself never scrolls sideways.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);

    // Rail: expanded with labels at >= 1280; icons with tooltips at 1024–1279.
    const rail = page.locator("[data-rail]");
    const railBox = await rail.boundingBox();
    expect(railBox?.width).toBe(compact ? 56 : 224);
    const designLink = rail.getByRole("link", { name: "Design system" });
    await expect(designLink).toBeVisible();
    const tooltip = designLink.locator("[data-rail-tooltip]");
    if (compact) {
      await designLink.hover();
      await expect(tooltip).toBeVisible();
    } else {
      await expect(tooltip).toBeHidden();
    }
    await expect(page.locator("[data-viewport-notice]")).toBeHidden();

    // KPI strip: one row of five at >= 1280, two rows at 1024–1279.
    const tops = await page
      .locator('dl[aria-label="Valuation summary"] > div')
      .evaluateAll((els) => [
        ...new Set(els.map((e) => Math.round(e.getBoundingClientRect().top))),
      ]);
    expect(tops).toHaveLength(compact ? 2 : 1);

    // Side panels: beside the chart at >= 1280, below it at 1024–1279.
    const chart = await page.locator('[data-chart="ufcf"]').boundingBox();
    const side = await page.getByTestId("backend-panel").boundingBox();
    expect(chart && side).toBeTruthy();
    if (compact) expect(side!.y).toBeGreaterThan(chart!.y + chart!.height);
    else expect(side!.x).toBeGreaterThan(chart!.x + chart!.width);

    // Wide table: scrolls inside its container; first column and header are sticky.
    // Whether the table happens to overflow at a given viewport depends on font metrics, so the
    // scroll path is exercised deterministically by narrowing the container to 640 px.
    const region = page.getByRole("region", { name: "Operating summary, historical and forecast" });
    expect(await region.evaluate((el) => getComputedStyle(el).overflowX)).toBe("auto");
    const firstCell = region.locator("tbody tr").first().locator("td").first();
    expect(await firstCell.evaluate((el) => getComputedStyle(el).position)).toBe("sticky");
    expect(
      await region
        .locator("thead th")
        .first()
        .evaluate((el) => getComputedStyle(el).position),
    ).toBe("sticky");
    await region.evaluate((el) => {
      el.style.maxWidth = "640px";
    });
    const dims = await region.evaluate((el) => ({ sw: el.scrollWidth, cw: el.clientWidth }));
    expect(dims.cw).toBe(640);
    expect(dims.sw).toBeGreaterThan(dims.cw); // the table scrolls inside its container...
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
    ).toBeLessThanOrEqual(0); // ...and the page itself still does not
    const before = await firstCell.boundingBox();
    await region.evaluate((el) => {
      el.scrollLeft = el.scrollWidth;
    });
    expect(await region.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
    const after = await firstCell.boundingBox();
    expect(after?.x).toBe(before?.x); // label column pinned while the numbers scroll
    await region.evaluate((el) => {
      el.scrollLeft = 0;
      el.style.maxWidth = "";
    });

    // Review screenshots (synthetic data, labelled on the page).
    mkdirSync(SCREENSHOTS, { recursive: true });
    await page.mouse.move(0, 0);
    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: resolve(SCREENSHOTS, `design-system-${String(width)}.png`),
      fullPage: true,
    });
    await page.screenshot({ path: resolve(SCREENSHOTS, `design-system-${String(width)}-top.png`) });
    info.annotations.push({
      type: "screenshot",
      description: `design-system-${String(width)}.png`,
    });
  });

  test("below 1024 px a non-blocking notice appears and the page still renders", async ({
    page,
  }, info) => {
    test.skip(info.project.name !== "laptop-1024", "runs once");
    const email = uniqueEmail("narrow");
    await registerViaApi(page, email);
    await logInViaUi(page, email);
    await page.setViewportSize({ width: 900, height: 700 });
    await expect(page.locator("[data-viewport-notice]")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Design system", level: 1 })).toBeVisible();
  });
});
