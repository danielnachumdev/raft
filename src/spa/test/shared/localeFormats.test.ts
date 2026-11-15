import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { localeFormats } from "../../src/shared/localeFormats.ts";

const SAMPLES = [
  Date.parse("2026-10-03T08:05:09Z"),
  Date.parse("2026-10-03T18:24:00Z"),
  Date.parse("2026-01-31T23:59:59Z"),
];

const LEGACY: Record<keyof typeof localeFormats, (d: Date) => string> = {
  dateTime: (d) => d.toLocaleString(),
  hourMinute: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  clock: (d) =>
    d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  clock24: (d) =>
    d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }),
  monthDay: (d) => d.toLocaleDateString([], { month: "short", day: "numeric" }),
  monthDayTime24: (d) =>
    d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }),
  weekdayMonthDay: (d) =>
    d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
};

describe("localeFormats", () => {
  for (const [name, legacy] of Object.entries(LEGACY)) {
    it(`${name} matches the toLocale*String call it replaces`, () => {
      const fmt = localeFormats[name as keyof typeof localeFormats];
      for (const ms of SAMPLES) {
        assert.equal(fmt.format(ms), legacy(new Date(ms)));
        assert.equal(fmt.format(new Date(ms)), legacy(new Date(ms)));
      }
    });
  }

  it("reuses one formatter across calls", () => {
    const realCtor = Intl.DateTimeFormat;
    let built = 0;
    const counting = function (...args: ConstructorParameters<typeof Intl.DateTimeFormat>) {
      built += 1;
      return new realCtor(...args);
    } as unknown as typeof Intl.DateTimeFormat;
    Intl.DateTimeFormat = counting;
    try {
      localeFormats.hourMinute.format(SAMPLES[0]);
      const before = built;
      for (const ms of SAMPLES) localeFormats.hourMinute.format(ms);
      assert.equal(built, before);
    } finally {
      Intl.DateTimeFormat = realCtor;
    }
  });
});
