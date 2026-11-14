/**
 * Design-system preview (milestone F1, plan section 9). A representative reference, not an
 * application screen: no business workflow, no writes, no financial calculation. All figures
 * are responses recorded from the real backend (synthetic sample); the "Backend connection"
 * panel calls the running API through the generated typed client.
 */
import { Tag } from "@/components/ui/Badge";
import { SyntheticBanner } from "@/components/ui/Feedback";
import { PageHeader } from "@/components/ui/Panel";

import { Composite } from "./Composite";
import {
  BadgeSection,
  ColourSection,
  ControlsSection,
  NumberFormatSection,
  Section,
  SensitivitySection,
  SpacingSection,
  StatesSection,
  TableSection,
  TypographySection,
} from "./Sections";

const TOC: { id: string; label: string }[] = [
  { id: "composite", label: "Composite" },
  { id: "colour", label: "Colour" },
  { id: "typography", label: "Typography" },
  { id: "spacing", label: "Spacing" },
  { id: "numbers", label: "Numbers" },
  { id: "badges", label: "Basis & status" },
  { id: "controls", label: "Controls" },
  { id: "tables", label: "Tables" },
  { id: "sensitivity", label: "Sensitivity" },
  { id: "states", label: "States" },
];

export default function StyleGuidePage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        breadcrumbs={<span>DealForge › Design system</span>}
        title="Design system"
        meta={<Tag>Milestone F1 · for review</Tag>}
      />
      <SyntheticBanner subject="Every figure on this page is a recorded API response for the synthetic sample company." />
      <nav aria-label="Sections" className="-mt-2 flex flex-wrap gap-x-4 gap-y-1 text-table">
        {TOC.map((t) => (
          <a key={t.id} href={`#${t.id}`} className="text-accent hover:underline">
            {t.label}
          </a>
        ))}
      </nav>
      <Section
        id="composite"
        title="Composite: valuation workspace layout"
        description="KPI strip, chart and side panels, and a wide statement table, at the density screens will use. At 1280 px and above the side panels sit beside the chart; at 1024–1279 px they move below and the KPI strip wraps to two rows."
      >
        <Composite />
      </Section>
      <ColourSection />
      <TypographySection />
      <SpacingSection />
      <NumberFormatSection />
      <BadgeSection />
      <ControlsSection />
      <TableSection />
      <SensitivitySection />
      <StatesSection />
    </div>
  );
}
