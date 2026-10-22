import { useEffect, useState } from "react";

type Props = {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  integer?: boolean;
};

/** Number input that keeps the user's text while they type and only commits valid values. */
export function NumberField({ label, value, onChange, unit, min, max, step, integer }: Props) {
  const [text, setText] = useState(String(value));

  // Follow outside changes (presets, reset) without clobbering e.g. "61." mid-typing.
  useEffect(() => setText((t) => (Number(t) === value ? t : String(value))), [value]);

  const check = (s: string) => {
    const n = Number(s);
    const ok =
      s.trim() !== "" &&
      Number.isFinite(n) &&
      (min === undefined || n >= min) &&
      (max === undefined || n <= max) &&
      (!integer || Number.isInteger(n));
    return ok ? n : null;
  };

  return (
    <label className={`field ${check(text) === null ? "invalid" : ""}`}>
      <span>{label}</span>
      <div className="input">
        <input
          type="number"
          inputMode="decimal"
          value={text}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            setText(e.target.value);
            const n = check(e.target.value);
            if (n !== null) onChange(n);
          }}
          onBlur={() => setText(String(value))}
        />
        {unit && <em>{unit}</em>}
      </div>
    </label>
  );
}

export function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" aria-hidden />
      <span>{label}</span>
    </label>
  );
}
