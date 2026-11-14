/**
 * Login and registration. React Hook Form + Zod check form STRUCTURE only (required, shape,
 * length); the backend remains the authority (e.g. the 10-character password rule is enforced
 * server-side and its message is shown as returned).
 */
import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactNode, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { type ApiError, isApiError } from "@/api/errors";
import { StatusIndicator } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorPanel } from "@/components/ui/Feedback";
import { TextField } from "@/components/ui/TextField";

import { useAuth } from "./AuthProvider";
import { safeNext } from "./tokenStore";

const loginSchema = z.object({
  email: z.string().trim().min(1, "Enter your email address."),
  password: z.string().min(1, "Enter your password."),
});

const registerSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Choose a password."),
});

type Credentials = z.infer<typeof loginSchema>;

const REASONS: Record<string, string> = {
  expired: "Your session expired. Log in again to continue where you left off.",
  unauthorized: "Your session is no longer valid. Log in again to continue.",
  logout: "You have logged out.",
};

function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex h-header items-center bg-navy-900 px-6">
        <span className="flex h-7 w-7 items-center justify-center rounded-sm border border-navy-700 text-table font-semibold text-white">
          DF
        </span>
        <span className="ml-2.5 text-section font-semibold text-white">DealForge</span>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pt-16">
        <section className="w-full max-w-sm rounded border border-slate-200 bg-white">
          <h1 className="border-b border-slate-200 px-5 py-3 text-section font-semibold">
            {title}
          </h1>
          <div className="px-5 py-4">{children}</div>
        </section>
      </main>
    </div>
  );
}

/** Field-level messages from a backend validation error (`loc` = ["body", field]). */
function fieldErrors(error: ApiError | null): Partial<Record<keyof Credentials, string>> {
  if (error?.errorType !== "validation") return {};
  const out: Partial<Record<keyof Credentials, string>> = {};
  for (const e of error.errors) {
    const field = e.loc?.[1];
    if (field === "email" || field === "password") out[field] = e.message;
  }
  return out;
}

function useCredentialsForm(schema: typeof loginSchema | typeof registerSchema) {
  return useForm<Credentials>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });
}

export function LoginPage() {
  const { session, login } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const reason = REASONS[params.get("reason") ?? ""];
  const [error, setError] = useState<ApiError | null>(null);
  const form = useCredentialsForm(loginSchema);

  if (session !== null) return <Navigate to={next} replace />;

  const onSubmit = form.handleSubmit(async ({ email, password }) => {
    setError(null);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (e) {
      if (isApiError(e)) setError(e);
      else throw e;
    }
  });

  const server = fieldErrors(error);
  const badCredentials = error?.errorType === "authentication";
  return (
    <AuthLayout title="Log in">
      {reason === undefined ? null : (
        <div className="mb-4">
          <StatusIndicator tone="info">{reason}</StatusIndicator>
        </div>
      )}
      <form className="flex flex-col gap-3" onSubmit={(e) => void onSubmit(e)} noValidate>
        <TextField
          label="Email"
          type="email"
          autoComplete="username"
          {...form.register("email")}
          error={form.formState.errors.email?.message ?? server.email}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          {...form.register("password")}
          error={form.formState.errors.password?.message ?? server.password}
        />
        {badCredentials ? (
          <p role="alert" className="text-table text-status-error">
            The email or password is incorrect.
          </p>
        ) : null}
        {error !== null && !badCredentials && Object.keys(server).length === 0 ? (
          <ErrorPanel error={error} />
        ) : null}
        <Button type="submit" pending={form.formState.isSubmitting} pendingLabel="Logging in…">
          Log in
        </Button>
      </form>
      <p className="mt-4 text-table text-slate-600">
        No account?{" "}
        <Link
          to={`/register?${new URLSearchParams({ next }).toString()}`}
          className="font-medium text-accent hover:underline"
        >
          Create one
        </Link>
      </p>
    </AuthLayout>
  );
}

export function RegisterPage() {
  const { session, register } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [error, setError] = useState<ApiError | null>(null);
  const form = useCredentialsForm(registerSchema);

  if (session !== null) return <Navigate to={next} replace />;

  const onSubmit = form.handleSubmit(async ({ email, password }) => {
    setError(null);
    try {
      await register(email, password);
      navigate(next, { replace: true });
    } catch (e) {
      if (isApiError(e)) setError(e);
      else throw e;
    }
  });

  const server = fieldErrors(error);
  return (
    <AuthLayout title="Create an account">
      <form className="flex flex-col gap-3" onSubmit={(e) => void onSubmit(e)} noValidate>
        <TextField
          label="Email"
          type="email"
          autoComplete="username"
          {...form.register("email")}
          error={form.formState.errors.email?.message ?? server.email}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 10 characters."
          {...form.register("password")}
          error={form.formState.errors.password?.message ?? server.password}
        />
        {error !== null && Object.keys(server).length === 0 ? <ErrorPanel error={error} /> : null}
        <Button
          type="submit"
          pending={form.formState.isSubmitting}
          pendingLabel="Creating account…"
        >
          Create account
        </Button>
      </form>
      <p className="mt-4 text-table text-slate-600">
        Already registered?{" "}
        <Link
          to={`/login?${new URLSearchParams({ next }).toString()}`}
          className="font-medium text-accent hover:underline"
        >
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
