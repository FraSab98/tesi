/**
 * Layout principale della dashboard medica.
 * Sidebar fissa a sinistra, header sottile con branding,
 * contenuto principale a destra.
 */

import React from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Icon } from "./ui";
import { colors, font, radius } from "../styles/theme";

interface NavItem {
  to: string;
  label: string;
  icon: "home" | "user" | "clipboard" | "plus" | "mic" | "trend";
}

const NAV_ITEMS: NavItem[] = [
  { to: "/",             label: "Panoramica",      icon: "home" },
  { to: "/patients",     label: "Pazienti",        icon: "user" },
  { to: "/sessions",     label: "Sessioni",        icon: "clipboard" },
  { to: "/sessions/new", label: "Nuova sessione",  icon: "plus" },
  { to: "/analyze",      label: "Analisi singola", icon: "mic" },
  { to: "/longitudinal", label: "Longitudinale",   icon: "trend" },
];

export function Layout() {
  const location = useLocation();

  return (
    <div style={styles.app}>
      {/* Sidebar */}
      <aside style={styles.sidebar}>
        <div style={styles.brand}>
          <div style={styles.brandMark}>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
              {/* simbolo: "cervello + griglia dati" — semplice ma riconoscibile */}
              <circle cx="14" cy="14" r="13" stroke={colors.surface} strokeOpacity="0.35" strokeWidth="1" />
              <path
                d="M9 9c0-2 2-3 3-3s3 1 3 3c2 0 3 1 3 3 0 1-0.5 2-1 2 1 0.5 1 1.5 1 2 0 2-1 3-3 3s-3-1-3-3c-2 0-3-1-3-3 0-1 0.5-2 1-2-1-0.5-1-1.5-1-2z"
                stroke={colors.surface}
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <div style={styles.brandTitle}>Cognitive Lab</div>
            <div style={styles.brandSub}>Assessment platform</div>
          </div>
        </div>

        <nav style={styles.nav}>
          <div style={styles.navLabel}>Area clinica</div>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              style={({ isActive }) => ({
                ...styles.navLink,
                ...(isActive ? styles.navLinkActive : {}),
              })}
            >
              <Icon name={item.icon} size={17} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div style={styles.sidebarFooter}>
          <div style={styles.footerLabel}>Clinico</div>
          <div style={styles.footerName}>dr_default</div>
          <div style={styles.footerHint}>
            Set static nel MVP — mappare su auth in produzione.
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={styles.main}>
        <div style={styles.topbar}>
          <Breadcrumb path={location.pathname} />
          <div style={styles.topbarRight}>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              style={styles.topLink}
            >
              API docs ↗
            </a>
          </div>
        </div>
        <div style={styles.content} className="fadeIn" key={location.pathname}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function Breadcrumb({ path }: { path: string }) {
  const parts = path.split("/").filter(Boolean);
  const labelMap: Record<string, string> = {
    patients: "Pazienti",
    sessions: "Sessioni",
    new: "Nuova",
    analyze: "Analisi singola",
    longitudinal: "Longitudinale",
    report: "Report",
  };
  return (
    <div style={styles.breadcrumb}>
      <span style={{ color: colors.muted }}>Dashboard</span>
      {parts.map((p, i) => {
        const label = labelMap[p] || p;
        return (
          <React.Fragment key={i}>
            <span style={{ color: colors.soft }}>›</span>
            <span style={i === parts.length - 1 ? { color: colors.ink } : { color: colors.muted }}>
              {label}
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );
}

const SIDEBAR_WIDTH = 248;

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: "grid",
    gridTemplateColumns: `${SIDEBAR_WIDTH}px 1fr`,
    minHeight: "100vh",
    background: colors.surface2,
  },
  sidebar: {
    background: colors.ink,
    color: "#E2E8F0",
    padding: "1.2rem 0",
    display: "flex",
    flexDirection: "column",
    position: "sticky",
    top: 0,
    height: "100vh",
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    padding: "0 1.25rem 1.25rem 1.25rem",
    borderBottom: "1px solid rgba(255,255,255,0.08)",
  },
  brandMark: {
    width: 40, height: 40,
    borderRadius: radius.md,
    background: `linear-gradient(135deg, ${colors.ink2}, ${colors.accent})`,
    display: "grid",
    placeItems: "center",
  },
  brandTitle: {
    fontFamily: font.display,
    fontSize: "1.05rem",
    fontWeight: 600,
    color: "#fff",
    letterSpacing: "-0.01em",
  },
  brandSub: {
    fontSize: "0.72rem",
    color: "#94A3B8",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  nav: {
    padding: "1rem 0.75rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.15rem",
    flex: 1,
  },
  navLabel: {
    fontSize: "0.7rem",
    color: "#64748B",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    padding: "0.3rem 0.75rem 0.5rem 0.75rem",
  },
  navLink: {
    display: "flex",
    alignItems: "center",
    gap: "0.7rem",
    padding: "0.55rem 0.75rem",
    borderRadius: radius.md,
    color: "#CBD5E1",
    fontSize: "0.92rem",
    textDecoration: "none",
    transition: "background 150ms, color 150ms",
  },
  navLinkActive: {
    background: "rgba(13, 148, 136, 0.15)",
    color: "#5EEAD4",
  },
  sidebarFooter: {
    padding: "1rem 1.25rem",
    borderTop: "1px solid rgba(255,255,255,0.08)",
    fontSize: "0.8rem",
  },
  footerLabel: {
    color: "#64748B",
    fontSize: "0.7rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: "0.25rem",
  },
  footerName: {
    color: "#fff",
    fontFamily: font.mono,
    fontSize: "0.85rem",
  },
  footerHint: {
    color: "#64748B",
    fontSize: "0.72rem",
    marginTop: "0.35rem",
    lineHeight: 1.4,
  },
  main: {
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  topbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.9rem 2rem",
    background: colors.surface,
    borderBottom: `1px solid ${colors.border}`,
    position: "sticky",
    top: 0,
    zIndex: 10,
  },
  breadcrumb: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    fontSize: "0.85rem",
  },
  topbarRight: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
  },
  topLink: {
    fontSize: "0.85rem",
    color: colors.muted,
  },
  content: {
    padding: "2rem",
    maxWidth: 1280,
    width: "100%",
    margin: "0 auto",
    boxSizing: "border-box",
  },
};
