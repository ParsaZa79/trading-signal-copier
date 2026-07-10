import { createAccessControl } from "better-auth/plugins/access";
import { defaultStatements } from "better-auth/plugins/admin/access";

export const AUTH_ROLES = ["owner", "admin", "trader", "viewer"] as const;
export type AuthRole = (typeof AUTH_ROLES)[number];

export const DEFAULT_ROLE = "trader" satisfies AuthRole;
export const ADMIN_ROLES = ["owner", "admin"] as const satisfies readonly AuthRole[];

export const authAccessControl = createAccessControl({
  ...defaultStatements,
});

const owner = authAccessControl.newRole({
  ...defaultStatements,
});
const admin = authAccessControl.newRole({
  // Admins may create a default-role trader and inspect users, but every
  // existing-user mutation (including role assignment) is owner-only. Session
  // listing is intentionally excluded because Better Auth returns raw tokens.
  user: ["create", "list", "get"],
  session: [],
});
const trader = authAccessControl.newRole({
  user: [],
  session: [],
});
const viewer = authAccessControl.newRole({
  user: [],
  session: [],
});

export const authRoles = {
  owner,
  admin,
  trader,
  viewer,
};

export function isAuthRole(value: unknown): value is AuthRole {
  return typeof value === "string" && AUTH_ROLES.some((role) => role === value);
}
