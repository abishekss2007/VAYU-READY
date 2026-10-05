// Sidebar screens in order. Each role sees only its own screens.
export type Role = "CO" | "ENGO" | "TECH" | "LOGO" | "BRD" | "FSO" | "ADMIN" | "AUDITOR" | "HQ";

export const ROLE_NAME: Record<Role, string> = {
  CO: "Squadron Commander", ENGO: "Engineering Officer", TECH: "Technician", LOGO: "Logistics Officer",
  BRD: "BRD Planner", FSO: "Flight Safety Officer", ADMIN: "Admin", AUDITOR: "Auditor", HQ: "Air HQ Leadership",
};

export const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/portfolio", label: "Portfolio", roles: ["HQ"] },
  { href: "/dashboard", label: "Readiness Dashboard", roles: ["CO", "ENGO", "FSO", "AUDITOR", "HQ"] },
  { href: "/aircraft", label: "Aircraft Health", roles: ["CO", "ENGO", "FSO", "AUDITOR", "HQ"] },
  { href: "/alerts", label: "Alerts", roles: ["CO", "ENGO", "FSO", "AUDITOR", "HQ"] },
  { href: "/defects", label: "Defects and Tasks", roles: ["TECH", "ENGO", "CO", "FSO"] },
  { href: "/spares", label: "Spares and Indents", roles: ["LOGO", "ENGO", "CO", "HQ"] },
  { href: "/schedule", label: "Schedule and What-If", roles: ["ENGO", "CO", "FSO", "BRD"] },
  { href: "/overhaul", label: "Overhaul Tracker", roles: ["BRD", "ENGO", "FSO"] },
  { href: "/audit", label: "Audit Trail", roles: ["AUDITOR", "CO", "ADMIN", "HQ"] },
  { href: "/admin", label: "Users & Access", roles: ["ADMIN"] },
  { href: "/compliance", label: "Compliance", roles: ["ADMIN", "CO", "AUDITOR"] },
  { href: "/models", label: "Model Cards", roles: ["CO", "ENGO", "TECH", "LOGO", "BRD", "FSO", "ADMIN", "AUDITOR", "HQ"] },
  { href: "/privacy", label: "My Data & Privacy", roles: ["CO", "ENGO", "TECH", "LOGO", "BRD", "FSO", "ADMIN", "AUDITOR", "HQ"] },
];

// Where each role lands after login.
export const HOME: Record<Role, string> = {
  CO: "/dashboard", ENGO: "/aircraft", TECH: "/defects", LOGO: "/spares", BRD: "/overhaul", FSO: "/dashboard",
  ADMIN: "/admin", AUDITOR: "/audit", HQ: "/portfolio",
};

export const canSee = (role: Role, path: string) =>
  NAV.some((n) => (path === n.href || path.startsWith(n.href + "/")) && n.roles.includes(role));
