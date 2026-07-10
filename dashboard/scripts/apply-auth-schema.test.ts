import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  applyAuthSchemaBootstrap,
  applyPreparedAuthMigration,
  loadAuthSchemaFiles,
  type MigrationClient,
} from "./apply-auth-schema";
import { authMigrationChecksum, prepareAuthMigration } from "./auth-schema";

const BOOTSTRAP = 'CREATE SCHEMA IF NOT EXISTS "auth";\n';
const RAW_SQL = 'create table "user" ("id" text primary key);';
const MIGRATION = {
  name: "0001_better_auth.sql",
  sql: prepareAuthMigration(RAW_SQL),
};

class FakeClient implements MigrationClient {
  calls: Array<{ sql: string; values?: unknown[] }> = [];
  existingChecksum: string | undefined;
  failPattern: RegExp | undefined;

  async query(sql: string, values?: unknown[]) {
    this.calls.push({ sql, values });
    if (this.failPattern?.test(sql)) throw new Error("injected database failure");
    if (sql.includes('SELECT "sha256"')) {
      return {
        rows: this.existingChecksum ? [{ sha256: this.existingChecksum }] : [],
      };
    }
    return { rows: [] };
  }
}

describe("Better Auth schema application", () => {
  it("creates the schema in its own transaction", async () => {
    const client = new FakeClient();

    await applyAuthSchemaBootstrap(client, BOOTSTRAP);

    expect(client.calls.map(({ sql }) => sql)).toEqual(["BEGIN", BOOTSTRAP, "COMMIT"]);
  });

  it("rolls back a failed schema bootstrap", async () => {
    const client = new FakeClient();
    client.failPattern = /CREATE SCHEMA/;

    await expect(applyAuthSchemaBootstrap(client, BOOTSTRAP)).rejects.toThrow(
      "injected database failure",
    );
    expect(client.calls.at(-1)?.sql).toBe("ROLLBACK");
  });

  it("applies unqualified DDL and its ledger entry atomically", async () => {
    const client = new FakeClient();

    await expect(applyPreparedAuthMigration(client, MIGRATION)).resolves.toBe(true);

    const calls = client.calls.map(({ sql }) => sql.trim());
    expect(calls[0]).toBe("BEGIN");
    expect(calls).toContain('SET LOCAL search_path TO "auth", pg_catalog');
    expect(calls).toContain(RAW_SQL);
    expect(calls.at(-1)).toBe("COMMIT");
    expect(calls.findIndex((sql) => sql === RAW_SQL)).toBeGreaterThan(
      calls.findIndex((sql) => sql.startsWith("SET LOCAL")),
    );
  });

  it("rolls back DDL and does not record a failed migration", async () => {
    const client = new FakeClient();
    client.failPattern = /^create table "user"/;

    await expect(applyPreparedAuthMigration(client, MIGRATION)).rejects.toThrow(
      "injected database failure",
    );
    expect(client.calls.at(-1)?.sql).toBe("ROLLBACK");
    expect(client.calls.some(({ sql }) => sql.includes("INSERT INTO"))).toBe(false);
  });

  it("skips an applied checksum and rejects migration drift", async () => {
    const client = new FakeClient();
    client.existingChecksum = authMigrationChecksum(MIGRATION.sql);

    await expect(applyPreparedAuthMigration(client, MIGRATION)).resolves.toBe(false);
    expect(client.calls.some(({ sql }) => sql === RAW_SQL)).toBe(false);

    const drifted = new FakeClient();
    drifted.existingChecksum = "0".repeat(64);
    await expect(applyPreparedAuthMigration(drifted, MIGRATION)).rejects.toThrow(
      /checksum mismatch/i,
    );
    expect(drifted.calls.at(-1)?.sql).toBe("ROLLBACK");
  });

  it("fails closed when a SQL migration filename is not recognized", async () => {
    const directory = await mkdtemp(join(tmpdir(), "auth-schema-test-"));
    try {
      await writeFile(join(directory, "0000_create_auth_schema.sql"), BOOTSTRAP);
      await writeFile(join(directory, "bad-name.sql"), MIGRATION.sql);

      await expect(loadAuthSchemaFiles(directory)).rejects.toThrow(
        /invalid auth migration filename/i,
      );
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  });
});
