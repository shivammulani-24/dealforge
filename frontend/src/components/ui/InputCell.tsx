/**
 * Financial input cell (plan section 7): blue text on a white cell with a thin blue underline;
 * an unsaved draft cell gets a faint blue background; an invalid cell gets a red outline and an
 * inline message. Percent input is parsed string-exactly by lib/parse ("18.5" → 0.185), and a
 * blank field is reported as missing, never as zero (R3).
 */
import { useId, useState } from "react";

import { cn } from "@/lib/cn";
import { parseDecimal, parsePercent, type ParseResult } from "@/lib/parse";

export function InputCell({
  label,
  kind,
  initial,
  draft = false,
  error,
  onParsed,
}: {
  label: string;
  kind: "percent" | "decimal";
  /** The text as the user typed it (the field never reformats what they type). */
  initial: string;
  draft?: boolean;
  /** A server-side validation message for this field. */
  error?: string;
  onParsed?: (result: ParseResult) => void;
}) {
  const id = useId();
  const [text, setText] = useState(initial);
  const parsed = kind === "percent" ? parsePercent(text) : parseDecimal(text);
  const localError = !parsed.ok && parsed.reason === "invalid" ? "Not a number." : undefined;
  const message = error ?? localError;
  return (
    <div className="flex flex-col gap-0.5">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          inputMode="decimal"
          value={text}
          aria-invalid={message === undefined ? undefined : true}
          aria-describedby={message === undefined ? undefined : `${id}-msg`}
          onChange={(e) => {
            setText(e.target.value);
            onParsed?.(
              kind === "percent" ? parsePercent(e.target.value) : parseDecimal(e.target.value),
            );
          }}
          className={cn(
            "df-num h-7 w-28 border-0 border-b bg-white px-2 pr-6 text-table text-accent",
            draft && "bg-accent-subtle",
            message === undefined ? "border-accent-line" : "rounded-sm border border-status-error",
          )}
        />
        {kind === "percent" ? (
          <span className="pointer-events-none absolute right-2 top-1 text-table text-accent">
            %
          </span>
        ) : null}
      </div>
      {message === undefined ? null : (
        <span id={`${id}-msg`} role="alert" className="text-label text-status-error">
          {message}
        </span>
      )}
    </div>
  );
}
