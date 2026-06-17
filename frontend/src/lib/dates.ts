import { useAuth } from "@/auth/AuthContext";

export type DateFormat = "dd.mm.yyyy" | "dd/mm/yyyy" | "mm/dd/yyyy" | "yyyy-mm-dd";

export const DATE_FORMATS: DateFormat[] = ["dd.mm.yyyy", "dd/mm/yyyy", "mm/dd/yyyy", "yyyy-mm-dd"];

const pad = (n: number) => String(n).padStart(2, "0");

/** Format a date-only value ("YYYY-MM-DD" or ISO) per the chosen pattern. */
export function formatDate(value: string | null | undefined, fmt: DateFormat): string {
  if (!value) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return value;
  const [, y, mo, d] = m;
  switch (fmt) {
    case "dd.mm.yyyy":
      return `${d}.${mo}.${y}`;
    case "dd/mm/yyyy":
      return `${d}/${mo}/${y}`;
    case "mm/dd/yyyy":
      return `${mo}/${d}/${y}`;
    default:
      return `${y}-${mo}-${d}`;
  }
}

/** Format a datetime: the date part follows the chosen pattern, time appended (local). */
export function formatDateTime(
  value: string | null | undefined,
  fmt: DateFormat,
  withTime = true,
): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const datePart = formatDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, fmt);
  if (!withTime) return datePart;
  return `${datePart} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

/** Formatters bound to the current user's preferred date format. */
export function useDateFormat() {
  const { me } = useAuth();
  const fmt = (me?.date_format ?? "dd.mm.yyyy") as DateFormat;
  return {
    fmt,
    formatDate: (v: string | null | undefined) => formatDate(v, fmt),
    formatDateTime: (v: string | null | undefined, withTime = true) =>
      formatDateTime(v, fmt, withTime),
  };
}
