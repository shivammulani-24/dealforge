import { Component, type ReactNode } from "react";

import { StatusIndicator } from "@/components/ui/Badge";

interface State {
  error: Error | null;
}

/**
 * Catches render errors, including the FinancialValue basis guard, so a broken screen says what
 * failed instead of showing a blank page or a wrong number. Errors are not logged or sent
 * anywhere.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override render(): ReactNode {
    if (this.state.error === null) return this.props.children;
    return (
      <div
        role="alert"
        className="m-6 rounded border border-status-error bg-status-error-subtle p-4"
      >
        <StatusIndicator tone="error">
          <span className="font-semibold">This screen failed to render.</span>
        </StatusIndicator>
        <p className="mt-1 text-table text-slate-800">{this.state.error.message}</p>
      </div>
    );
  }
}
