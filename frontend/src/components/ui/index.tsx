/**
 * Piccoli componenti UI riutilizzabili.
 */

import React from "react";
import { colors, radius, shadow, font } from "../../styles/theme";

// ============ Card ============

interface CardProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  accent?: boolean;
  style?: React.CSSProperties;
  bodyStyle?: React.CSSProperties;
  right?: React.ReactNode;
}

export function Card({ children, title, subtitle, accent, style, bodyStyle, right }: CardProps) {
  return (
    <section
      style={{
        background: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.lg,
        boxShadow: shadow.card,
        overflow: "hidden",
        position: "relative",
        ...style,
      }}
    >
      {accent && (
        <div
          style={{
            position: "absolute",
            top: 0, left: 0, right: 0,
            height: 3,
            background: `linear-gradient(90deg, ${colors.ink2}, ${colors.accent})`,
          }}
        />
      )}
      {(title || right) && (
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
            padding: "1rem 1.25rem",
            borderBottom: `1px solid ${colors.border}`,
          }}
        >
          <div>
            {title && (
              <h3 style={{ margin: 0, fontFamily: font.display, fontSize: "1.05rem" }}>
                {title}
              </h3>
            )}
            {subtitle && (
              <p style={{ margin: "0.15rem 0 0 0", color: colors.muted, fontSize: "0.85rem" }}>
                {subtitle}
              </p>
            )}
          </div>
          {right}
        </header>
      )}
      <div style={{ padding: "1.25rem", ...bodyStyle }}>{children}</div>
    </section>
  );
}

// ============ Button ============

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}

export function Button({
  variant = "primary",
  size = "md",
  style,
  children,
  ...rest
}: ButtonProps) {
  const base: React.CSSProperties = {
    fontFamily: font.body,
    border: "1px solid transparent",
    borderRadius: radius.md,
    cursor: rest.disabled ? "not-allowed" : "pointer",
    fontWeight: 500,
    transition: "background 160ms, border-color 160ms, color 160ms",
    padding: size === "sm" ? "0.35rem 0.8rem" : "0.55rem 1.1rem",
    fontSize: size === "sm" ? "0.85rem" : "0.95rem",
    opacity: rest.disabled ? 0.55 : 1,
    whiteSpace: "nowrap",
    display: "inline-flex",
    alignItems: "center",
    gap: "0.4rem",
  };

  const variants: Record<string, React.CSSProperties> = {
    primary: {
      background: colors.ink2,
      color: "#fff",
      borderColor: colors.ink2,
    },
    secondary: {
      background: colors.surface,
      color: colors.ink2,
      borderColor: colors.borderStrong,
    },
    ghost: {
      background: "transparent",
      color: colors.ink2,
      borderColor: "transparent",
    },
    danger: {
      background: "#fff",
      color: colors.risk,
      borderColor: colors.risk,
    },
  };

  return (
    <button {...rest} style={{ ...base, ...variants[variant], ...style }}>
      {children}
    </button>
  );
}

// ============ Badge ============

interface BadgeProps {
  children: React.ReactNode;
  tone?: "neutral" | "accent" | "warn" | "risk" | "sky";
  soft?: boolean;
}

export function Badge({ children, tone = "neutral", soft = true }: BadgeProps) {
  const map = {
    neutral: { fg: colors.body, bg: colors.surface3, bd: colors.border },
    accent:  { fg: "#065F46", bg: colors.accentSoft, bd: "#99F6E4" },
    warn:    { fg: "#92400E", bg: colors.warnSoft, bd: "#FDE68A" },
    risk:    { fg: "#991B1B", bg: colors.riskSoft, bd: "#FECACA" },
    sky:     { fg: "#075985", bg: colors.skySoft, bd: "#BAE6FD" },
  };
  const c = map[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.3rem",
        padding: "0.15rem 0.55rem",
        borderRadius: radius.pill,
        fontSize: "0.75rem",
        fontWeight: 500,
        color: c.fg,
        background: soft ? c.bg : "transparent",
        border: `1px solid ${c.bd}`,
        letterSpacing: "0.01em",
      }}
    >
      {children}
    </span>
  );
}

// ============ Icon ============

// SVG inline, tenute semplici; stroke currentColor perché ereditano il colore del parent.
const ICONS: Record<string, JSX.Element> = {
  home: (
    <path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1V11z" strokeLinejoin="round" />
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-7 8-7s8 3 8 7" strokeLinejoin="round" />
    </>
  ),
  clipboard: (
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4h6v3H9z" />
      <path d="M9 11h6M9 15h4" strokeLinecap="round" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" strokeLinecap="round" />,
  chart: <path d="M4 20V4M4 20h16M8 16V10M12 16V6M16 16v-4" strokeLinecap="round" />,
  mic: (
    <>
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M6 11a6 6 0 0 0 12 0M12 17v4M9 21h6" strokeLinecap="round" />
    </>
  ),
  trend: (
    <>
      <path d="M4 17l6-6 4 4 6-7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 8h6v6" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  copy: (
    <>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" />
    </>
  ),
  download: (
    <>
      <path d="M12 4v12M6 10l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 20h16" strokeLinecap="round" />
    </>
  ),
  arrow: (
    <path d="M5 12h14M13 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
  ),
  check: <path d="M5 12l5 5L20 7" strokeLinecap="round" strokeLinejoin="round" />,
  alert: (
    <>
      <path d="M12 3L2 20h20L12 3z" strokeLinejoin="round" />
      <path d="M12 10v5M12 18v.01" strokeLinecap="round" />
    </>
  ),
};

interface IconProps {
  name: keyof typeof ICONS;
  size?: number;
  strokeWidth?: number;
  style?: React.CSSProperties;
}

export function Icon({ name, size = 18, strokeWidth = 1.6, style }: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      style={{ flexShrink: 0, ...style }}
      aria-hidden="true"
    >
      {ICONS[name]}
    </svg>
  );
}

// ============ EmptyState ============

interface EmptyStateProps {
  icon?: keyof typeof ICONS;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon = "clipboard", title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "3rem 1rem",
        textAlign: "center",
        color: colors.muted,
      }}
    >
      <div
        style={{
          width: 56, height: 56,
          borderRadius: "50%",
          display: "grid",
          placeItems: "center",
          background: colors.surface3,
          color: colors.ink2,
          marginBottom: "1rem",
        }}
      >
        <Icon name={icon} size={24} />
      </div>
      <h3 style={{ margin: "0 0 0.4rem 0" }}>{title}</h3>
      {description && (
        <p style={{ margin: "0 0 1rem 0", maxWidth: 420 }}>{description}</p>
      )}
      {action}
    </div>
  );
}
