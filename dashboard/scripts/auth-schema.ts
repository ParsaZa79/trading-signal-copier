import { createHash } from "node:crypto";

export const AUTH_SCHEMA = "auth";

const PREPARED_PREFIX = `BEGIN;\nSET LOCAL search_path TO "${AUTH_SCHEMA}", pg_catalog;\n\n`;
const PREPARED_SUFFIX = `\n\nCOMMIT;\n`;
const QUALIFIED_IDENTIFIER =
  /(?:^|[\s,(])(?:"(?:[^"]|"")*"|[a-z_][a-z0-9_$]*)\s*\.\s*(?:"(?:[^"]|"")*"|[a-z_][a-z0-9_$]*)/im;
const IDENTIFIER = String.raw`(?:"(?:[^"]|"")*"|[a-z_][a-z0-9_$]*)`;
const CREATE_TABLE_STATEMENT = new RegExp(
  String.raw`^CREATE\s+TABLE\s+${IDENTIFIER}\s*\([\s\S]+\)$`,
  "i",
);
const ALTER_TABLE_STATEMENT = new RegExp(
  String.raw`^ALTER\s+TABLE\s+${IDENTIFIER}\s+ADD\s+COLUMN\s+${IDENTIFIER}\s+[\s\S]+$`,
  "i",
);
const CREATE_INDEX_STATEMENT = new RegExp(
  String.raw`^CREATE\s+(?:UNIQUE\s+)?INDEX\s+${IDENTIFIER}\s+ON\s+${IDENTIFIER}\s*\(\s*${IDENTIFIER}(?:\s*,\s*${IDENTIFIER})*\s*\)$`,
  "i",
);

export function validateRawBetterAuthSql(sql: string) {
  const normalized = sql.trim();
  if (!normalized || normalized === ";") {
    throw new Error("Better Auth generated empty SQL");
  }
  if (!normalized.endsWith(";")) {
    throw new Error("Better Auth SQL must end with a semicolon");
  }
  if (/(?:^|\s)--|\/\*|\*\//m.test(normalized)) {
    throw new Error("Comments are not allowed in generated Better Auth SQL");
  }
  if (/^\s*\\/m.test(normalized)) {
    throw new Error("psql meta commands are not allowed");
  }
  if (/\b(?:BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b/i.test(normalized)) {
    throw new Error("Generated Better Auth SQL cannot control transactions");
  }
  if (/\b(?:SET|RESET)\s+(?:LOCAL\s+|SESSION\s+)?search_path\b/i.test(normalized)) {
    throw new Error("Generated Better Auth SQL cannot change search_path");
  }
  if (/\b(?:CREATE|ALTER|DROP)\s+SCHEMA\b/i.test(normalized)) {
    throw new Error("Generated Better Auth SQL cannot mutate schemas");
  }
  if (QUALIFIED_IDENTIFIER.test(normalized)) {
    throw new Error("Generated Better Auth SQL must use unqualified identifiers");
  }

  const statements = normalized
    .split(";")
    .map((statement) => statement.trim())
    .filter(Boolean);
  if (
    statements.length === 0 ||
    statements.some(
      (statement) =>
        !CREATE_TABLE_STATEMENT.test(statement) &&
        !ALTER_TABLE_STATEMENT.test(statement) &&
        !CREATE_INDEX_STATEMENT.test(statement),
    )
  ) {
    throw new Error("Generated Better Auth SQL contains an unsupported statement");
  }
  return normalized;
}

export function prepareAuthMigration(sql: string) {
  const validated = validateRawBetterAuthSql(sql);
  return `${PREPARED_PREFIX}${validated}${PREPARED_SUFFIX}`;
}

export function extractPreparedAuthSql(sql: string) {
  if (!sql.startsWith(PREPARED_PREFIX) || !sql.endsWith(PREPARED_SUFFIX)) {
    throw new Error("Auth migration transaction/search_path envelope is invalid");
  }
  const raw = sql.slice(PREPARED_PREFIX.length, -PREPARED_SUFFIX.length);
  validateRawBetterAuthSql(raw);
  return raw;
}

export function validatePreparedAuthMigration(sql: string) {
  extractPreparedAuthSql(sql);
}

export function validateAuthSchemaBootstrap(sql: string) {
  if (!/^\s*CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+"auth"\s*;\s*$/i.test(sql)) {
    throw new Error("Auth bootstrap may only create the auth schema");
  }
}

export function authMigrationChecksum(sql: string) {
  return createHash("sha256").update(sql, "utf8").digest("hex");
}
