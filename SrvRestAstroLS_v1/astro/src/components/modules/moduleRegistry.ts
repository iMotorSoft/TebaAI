/**
 * Breslov Research module registry — central, single source of truth for the
 * pre-auth module selector and the safe post-login destination allowlist.
 *
 * Adding a future module (e.g. Administración) only requires appending a
 * definition here; the Home and the login redirect resolve from this registry,
 * so no scattered `if module === ... else ...` logic exists.
 */

export interface ModuleDefinition {
  id: string;
  label: string;
  description: string;
  destination: string;
  ctaLabel: string;
  /** null = any authenticated user; otherwise the role must be listed. */
  requiredRoles: string[] | null;
  enabled: boolean;
}

export const MODULES: ReadonlyArray<ModuleDefinition> = [
  {
    id: "research",
    label: "Investigación",
    description: "Consultá, buscá y relacioná las fuentes del corpus de Breslov.",
    destination: "/research",
    ctaLabel: "Entrar a Investigación",
    requiredRoles: null,
    enabled: true,
  },
  {
    id: "edition",
    label: "Edición",
    description: "Administrá las fuentes documentales, su incorporación y revisión.",
    destination: "/admin/content",
    ctaLabel: "Entrar a Edición",
    requiredRoles: ["admin", "editor"],
    enabled: true,
  },
];

/** Historical default used by /login when no destination is requested. */
export const DEFAULT_POST_LOGIN_DESTINATION = "/research";

/** Exact destinations the auth flow is allowed to navigate to. */
const ALLOWED_DESTINATIONS: ReadonlySet<string> = new Set(
  MODULES.filter((m) => m.enabled).map((m) => m.destination),
);

/**
 * Resolve a raw `?next=` value into a same-origin, allowlisted destination.
 * Rejects external, protocol-relative, scheme-based and backslash-trick URLs;
 * falls back to the historical default on any mismatch.
 */
export function resolveSafePostLoginDestination(
  raw: string | null | undefined,
): string {
  if (!raw) return DEFAULT_POST_LOGIN_DESTINATION;
  const value = raw.trim();
  // Only clean absolute paths beginning with a single slash are candidates.
  if (!value.startsWith("/") || value.startsWith("//")) {
    return DEFAULT_POST_LOGIN_DESTINATION;
  }
  // Backslash tricks (`/\evil`, `/admin\..`) are never valid same-origin paths.
  if (value.includes("\\")) {
    return DEFAULT_POST_LOGIN_DESTINATION;
  }
  // Strip query string and fragment before matching the allowlist.
  const path = value.split(/[?#]/)[0];
  if (!ALLOWED_DESTINATIONS.has(path)) {
    return DEFAULT_POST_LOGIN_DESTINATION;
  }
  return path;
}

export function findModuleByDestination(
  destination: string,
): ModuleDefinition | undefined {
  return MODULES.find((m) => m.destination === destination);
}

/** True when a role may enter the module (null requiredRoles = any authenticated). */
export function roleCanAccessModule(
  role: string,
  module: ModuleDefinition,
): boolean {
  if (!module.requiredRoles) return true;
  return module.requiredRoles.includes(role);
}
