import { readdir, readFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "pg";
import {
  authMigrationChecksum,
  extractPreparedAuthSql,
  validateAuthSchemaBootstrap,
  validatePreparedAuthMigration,
} from "./auth-schema";

const MIGRATIONS_DIRECTORY = fileURLToPath(
  new URL("../migrations/auth", import.meta.url),
);
const BOOTSTRAP_FILE = "0000_create_auth_schema.sql";
const MIGRATION_NAME = /^\d{4}_[a-z0-9_]+\.sql$/;

interface QueryResultLike {
  rows: Array<Record<string, unknown>>;
}

export interface MigrationClient {
  query(sql: string, values?: unknown[]): Promise<QueryResultLike>;
}

export interface AuthMigrationFile {
  name: string;
  sql: string;
}

export async function loadAuthSchemaFiles(
  directory = MIGRATIONS_DIRECTORY,
): Promise<{ bootstrap: string; migrations: AuthMigrationFile[] }> {
  const bootstrap = await readFile(join(directory, BOOTSTRAP_FILE), "utf8");
  validateAuthSchemaBootstrap(bootstrap);
  const entries = await readdir(directory);
  const unexpectedSql = entries.filter(
    (name) =>
      name.endsWith(".sql") &&
      name !== BOOTSTRAP_FILE &&
      !MIGRATION_NAME.test(name),
  );
  if (unexpectedSql.length > 0) {
    throw new Error(`Invalid auth migration filename: ${unexpectedSql.sort()[0]}`);
  }
  const names = entries
    .filter((name) => name !== BOOTSTRAP_FILE && MIGRATION_NAME.test(name))
    .sort();
  const migrations = await Promise.all(
    names.map(async (name) => {
      const sql = await readFile(join(directory, name), "utf8");
      validatePreparedAuthMigration(sql);
      return { name, sql };
    }),
  );
  return { bootstrap, migrations };
}

export async function applyAuthSchemaBootstrap(
  client: MigrationClient,
  bootstrapSql: string,
) {
  validateAuthSchemaBootstrap(bootstrapSql);
  await inTransaction(client, async () => {
    await client.query(bootstrapSql);
  });
}

export async function applyPreparedAuthMigration(
  client: MigrationClient,
  migration: AuthMigrationFile,
) {
  if (basename(migration.name) !== migration.name || !MIGRATION_NAME.test(migration.name)) {
    throw new Error("Invalid auth migration filename");
  }
  const rawSql = extractPreparedAuthSql(migration.sql);
  const checksum = authMigrationChecksum(migration.sql);

  return inTransaction(client, async () => {
    await client.query("SELECT pg_advisory_xact_lock(20260710, 32056)");
    await client.query(`
      CREATE TABLE IF NOT EXISTS "auth"."_better_auth_migrations" (
        "name" text PRIMARY KEY,
        "sha256" text NOT NULL,
        "appliedAt" timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
      )
    `);
    const existing = await client.query(
      'SELECT "sha256" FROM "auth"."_better_auth_migrations" WHERE "name" = $1',
      [migration.name],
    );
    if (existing.rows.length > 0) {
      if (existing.rows[0]?.sha256 !== checksum) {
        throw new Error(`Auth migration checksum mismatch: ${migration.name}`);
      }
      return false;
    }

    await client.query('SET LOCAL search_path TO "auth", pg_catalog');
    await client.query(rawSql);
    await client.query(
      'INSERT INTO "auth"."_better_auth_migrations" ("name", "sha256") VALUES ($1, $2)',
      [migration.name, checksum],
    );
    return true;
  });
}

export async function applyAuthSchemaMigrations(
  client: MigrationClient,
  files: { bootstrap: string; migrations: AuthMigrationFile[] },
  schemaOnly = false,
) {
  await applyAuthSchemaBootstrap(client, files.bootstrap);
  if (schemaOnly) return { applied: 0, skipped: files.migrations.length };

  let applied = 0;
  let skipped = 0;
  for (const migration of files.migrations) {
    if (await applyPreparedAuthMigration(client, migration)) applied += 1;
    else skipped += 1;
  }
  return { applied, skipped };
}

async function inTransaction<T>(
  client: MigrationClient,
  operation: () => Promise<T>,
) {
  await client.query("BEGIN");
  try {
    const result = await operation();
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  }
}

async function main() {
  const schemaOnly = process.argv.includes("--schema-only");
  const useTestDatabase = process.argv.includes("--test-database");
  const databaseURL = useTestDatabase
    ? process.env.TEST_DATABASE_URL
    : process.env.BETTER_AUTH_DATABASE_URL;
  const variable = useTestDatabase ? "TEST_DATABASE_URL" : "BETTER_AUTH_DATABASE_URL";
  if (!databaseURL) throw new Error(`${variable} is required`);

  const client = new Client({ connectionString: databaseURL });
  try {
    await client.connect();
    const result = await applyAuthSchemaMigrations(
      client as unknown as MigrationClient,
      await loadAuthSchemaFiles(),
      schemaOnly,
    );
    console.log(`Auth schema migrations: ${result.applied} applied, ${result.skipped} skipped`);
  } finally {
    await client.end().catch(() => undefined);
  }
}

if ((import.meta as ImportMeta & { main?: boolean }).main) {
  await main();
}
