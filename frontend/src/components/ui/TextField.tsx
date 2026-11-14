import { forwardRef, type InputHTMLAttributes, useId } from "react";

import { cn } from "@/lib/cn";

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  /** Inline error (e.g. mapped from a validation `loc`); the field keeps its value. */
  error?: string | undefined;
  hint?: string;
}

/** A labelled form field for non-financial input (names, email, passwords). */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, error, hint, className, ...rest },
  ref,
) {
  const id = useId();
  const describedBy = [
    error === undefined ? null : `${id}-error`,
    hint === undefined ? null : `${id}-hint`,
  ]
    .filter((x) => x !== null)
    .join(" ");
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label htmlFor={id} className="text-table font-medium text-slate-700">
        {label}
      </label>
      <input
        ref={ref}
        id={id}
        aria-invalid={error === undefined ? undefined : true}
        aria-describedby={describedBy === "" ? undefined : describedBy}
        className={cn(
          "h-8 rounded border bg-white px-2.5 text-body text-slate-900 placeholder:text-slate-400",
          error === undefined ? "border-slate-300" : "border-status-error",
        )}
        {...rest}
      />
      {hint === undefined ? null : (
        <p id={`${id}-hint`} className="text-label text-slate-500">
          {hint}
        </p>
      )}
      {error === undefined ? null : (
        <p id={`${id}-error`} role="alert" className="text-label font-medium text-status-error">
          {error}
        </p>
      )}
    </div>
  );
});
