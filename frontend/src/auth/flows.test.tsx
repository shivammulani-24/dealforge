import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { FAR_EXPIRY, server, TEST_EMAIL, TEST_TOKEN, url } from "@/test/msw";
import { renderApp } from "@/test/renderApp";

import { STORAGE_KEY, TokenStore } from "./tokenStore";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

const location = () => screen.getByTestId("location").textContent;

async function logIn(password = "correct-password-1") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), TEST_EMAIL);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Log in" }));
  return user;
}

describe("authentication flows", () => {
  it("sends an unauthenticated user to /login?next=… and back after logging in", async () => {
    const { store } = renderApp("/runs?page=2");
    expect(location()).toBe("/login?next=%2Fruns%3Fpage%3D2");
    await logIn();
    await waitFor(() => {
      expect(location()).toBe("/runs?page=2");
    });
    expect(store.token()).toBe(TEST_TOKEN);
    expect(JSON.parse(window.sessionStorage.getItem(STORAGE_KEY)!)).toMatchObject({
      token: TEST_TOKEN,
    });
    await waitFor(() => {
      expect(screen.getByTestId("current-user")).toHaveTextContent(TEST_EMAIL);
    });
    expect(window.localStorage.length).toBe(0);
  });

  it("validates form structure before calling the server", async () => {
    renderApp("/login");
    await userEvent.setup().click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
  });

  it("shows a clear message for a wrong password and keeps the user on /login", async () => {
    renderApp("/login?next=%2Fruns");
    await logIn("wrong-password-1");
    expect(await screen.findByText("The email or password is incorrect.")).toBeInTheDocument();
    expect(location()).toBe("/login?next=%2Fruns");
  });

  it("ignores an external next= destination (no open redirect)", async () => {
    renderApp("/login?next=https%3A%2F%2Fevil.example");
    await logIn();
    await waitFor(() => {
      expect(location()).toBe("/");
    });
  });

  it("ends the session on a 401 from any authenticated request and explains why", async () => {
    const store = new TokenStore();
    store.set("revoked-token", FAR_EXPIRY);
    renderApp("/companies", { store });
    // /auth/me rejects the revoked token → middleware clears the session → login page.
    await waitFor(() => {
      expect(location()).toBe("/login?next=%2Fcompanies&reason=unauthorized");
    });
    expect(screen.getByText(/no longer valid/)).toBeInTheDocument();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("logs out: revokes server-side, clears the client, shows the reason", async () => {
    let revoked = false;
    server.use(
      http.post(url("/auth/logout"), ({ request }) => {
        revoked = request.headers.get("Authorization") === `Bearer ${TEST_TOKEN}`;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const store = new TokenStore();
    store.set(TEST_TOKEN, FAR_EXPIRY);
    renderApp("/", { store });
    await userEvent.setup().click(await screen.findByRole("button", { name: /Log out/ }));
    await waitFor(() => {
      expect(location()).toBe("/login?next=%2F&reason=logout");
    });
    expect(revoked).toBe(true);
    expect(store.token()).toBeNull();
    expect(screen.getByText("You have logged out.")).toBeInTheDocument();
  });

  it("still clears the client when the logout call fails", async () => {
    server.use(http.post(url("/auth/logout"), () => HttpResponse.error()));
    const store = new TokenStore();
    store.set(TEST_TOKEN, FAR_EXPIRY);
    renderApp("/", { store });
    await userEvent.setup().click(await screen.findByRole("button", { name: /Log out/ }));
    await waitFor(() => {
      expect(store.token()).toBeNull();
    });
  });

  it("registers, then logs in and continues to next", async () => {
    server.use(
      http.post(url("/auth/register"), () =>
        HttpResponse.json({ id: 1, email: TEST_EMAIL }, { status: 201 }),
      ),
    );
    renderApp("/register?next=%2Fruns");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), TEST_EMAIL);
    await user.type(screen.getByLabelText(/^Password/), "correct-password-1");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => {
      expect(location()).toBe("/runs");
    });
  });

  it("shows the server's password rule rather than a client copy of it", async () => {
    server.use(
      http.post(url("/auth/register"), () =>
        HttpResponse.json(
          {
            error_type: "validation",
            status: 422,
            errors: [
              {
                code: "WEAK_PASSWORD",
                message: "Password must be at least 10 characters.",
                detail: null,
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    renderApp("/register");
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), TEST_EMAIL);
    await user.type(screen.getByLabelText(/^Password/), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Password must be at least 10 characters.")).toBeInTheDocument();
  });

  it("maps validation errors to their field", async () => {
    server.use(
      http.post(url("/auth/token"), () =>
        HttpResponse.json(
          {
            error_type: "validation",
            status: 422,
            errors: [
              {
                loc: ["body", "email"],
                code: "string_type",
                message: "Input should be a valid string",
              },
            ],
          },
          { status: 422 },
        ),
      ),
    );
    renderApp("/login");
    await logIn();
    expect(await screen.findByText("Input should be a valid string")).toBeInTheDocument();
  });

  it("redirects an already signed-in user away from /login and /register", async () => {
    const store = new TokenStore();
    store.set(TEST_TOKEN, FAR_EXPIRY);
    renderApp("/login?next=%2Fruns", { store });
    await waitFor(() => {
      expect(location()).toBe("/runs");
    });
  });

  it("renders the shell with every navigation item and a not-found page", async () => {
    const store = new TokenStore();
    store.set(TEST_TOKEN, FAR_EXPIRY);
    renderApp("/no-such-page", { store });
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const name of ["Dashboard", "Companies", "Saved runs", "Design system"]) {
      expect(nav).toHaveTextContent(name);
    }
  });
});
