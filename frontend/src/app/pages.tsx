import { Link } from "react-router-dom";

import { Tag } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/Feedback";
import { PageHeader } from "@/components/ui/Panel";

/**
 * Placeholder for a screen that a later milestone builds. F1 delivers the shell and the design
 * system only; no screen or business workflow is implemented here.
 */
export function PlannedScreen({ title, milestone }: { title: string; milestone: string }) {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={title} meta={<Tag>Planned · {milestone}</Tag>} />
      <EmptyState
        title={`${title} is built in milestone ${milestone}`}
        action={
          <Link to="/style-guide" className="text-body font-medium text-accent hover:underline">
            Open the design system
          </Link>
        }
      >
        This milestone (F1) delivers the frontend foundation, the application shell and the design
        system. Screens are added from F2 onwards, after the design system is approved.
      </EmptyState>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Page not found" />
      <EmptyState
        title="There is no page at this address"
        action={
          <Link to="/" className="text-body font-medium text-accent hover:underline">
            Go to the dashboard
          </Link>
        }
      />
    </div>
  );
}
