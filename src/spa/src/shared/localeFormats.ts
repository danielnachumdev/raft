/**
 * Shared ``Intl.DateTimeFormat`` instances in the default locale.
 *
 * ``Date#toLocale*String(locales, options)`` builds a fresh formatter on every
 * call, which dominated chart renders. Each entry matches the output of the
 * ``toLocale*String`` call named beside it.
 */
export type LocaleFormat = { format: (value: Date | number) => string };

function cached(options: Intl.DateTimeFormatOptions): LocaleFormat {
  let fmt: Intl.DateTimeFormat | null = null;
  return {
    format: (value) => (fmt ??= new Intl.DateTimeFormat(undefined, options)).format(value),
  };
}

export const localeFormats = {
  /** ``toLocaleString()`` */
  dateTime: cached({
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  }),
  /** ``toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })`` */
  hourMinute: cached({ hour: "2-digit", minute: "2-digit" }),
  /** ``toLocaleTimeString(undefined, { hour, minute, second: "2-digit" })`` */
  clock: cached({ hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  /** ``clock`` with ``hour12: false`` */
  clock24: cached({ hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }),
  /** ``toLocaleDateString([], { month: "short", day: "numeric" })`` */
  monthDay: cached({ month: "short", day: "numeric" }),
  /** ``toLocaleString(undefined, { month, day, hour, minute, hour12: false })`` */
  monthDayTime24: cached({
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }),
  /** ``toLocaleDateString(undefined, { weekday, month: "short", day })`` */
  weekdayMonthDay: cached({ weekday: "short", month: "short", day: "numeric" }),
} satisfies Record<string, LocaleFormat>;
