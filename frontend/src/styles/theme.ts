/**
 * Token centrali del design system.
 * Palette "clinical serif": navy profondo + teal medicale,
 * ispirata a riviste e referti medici.
 */

export const colors = {
  ink: "#0F1F35",          // quasi nero, per titoli e logo
  ink2: "#1E3A5F",         // navy profondo, elemento forte
  body: "#334155",         // testo corrente
  muted: "#64748B",        // testo secondario
  soft: "#94A3B8",         // hint, placeholder
  surface: "#FFFFFF",
  surface2: "#F8FAFC",     // sfondo app
  surface3: "#F1F5F9",     // zone alternate
  border: "#E2E8F0",
  borderStrong: "#CBD5E1",
  accent: "#0D9488",       // teal — stato positivo clinico
  accentSoft: "#CCFBF1",
  warn: "#B45309",         // ambra più sobria
  warnSoft: "#FEF3C7",
  risk: "#B91C1C",         // crimisi, non arancione da “errore web”
  riskSoft: "#FEE2E2",
  sky: "#0369A1",
  skySoft: "#E0F2FE",
};

export const riskPalette = {
  low:    { fg: "#065F46", bg: "#D1FAE5", label: "Rischio basso" },
  medium: { fg: "#92400E", bg: "#FEF3C7", label: "Rischio moderato" },
  high:   { fg: "#991B1B", bg: "#FEE2E2", label: "Rischio elevato" },
};

export const font = {
  display: `"Source Serif 4", "Source Serif Pro", Georgia, "Times New Roman", serif`,
  body: `"IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, sans-serif`,
  mono: `"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace`,
};

export const radius = {
  sm: "4px",
  md: "6px",
  lg: "10px",
  pill: "999px",
};

export const shadow = {
  card: "0 1px 2px rgba(15, 31, 53, 0.04), 0 0 0 1px rgba(15, 31, 53, 0.04)",
  cardHover: "0 4px 12px rgba(15, 31, 53, 0.08), 0 0 0 1px rgba(15, 31, 53, 0.06)",
  raised: "0 10px 25px -10px rgba(15, 31, 53, 0.15)",
};

export const space = {
  xs: "0.25rem",
  sm: "0.5rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2rem",
  "2xl": "3rem",
};
