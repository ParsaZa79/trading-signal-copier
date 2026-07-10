import { readFile } from "node:fs/promises";
import { describe, expect, it } from "vitest";
import {
  AUTH_SCHEMA,
  prepareAuthMigration,
  validatePreparedAuthMigration,
} from "./auth-schema";

const GENERATED_SQL = `
create table "user" (
  "id" text primary key,
  "email" text not null unique
);

create index "user_email_idx" on "user" ("email");
`;

describe("Better Auth PostgreSQL migration preparation", () => {
  it("keeps schema creation in a separate bootstrap migration", async () => {
    const bootstrap = await readFile(
      new URL("../migrations/auth/0000_create_auth_schema.sql", import.meta.url),
      "utf8",
    );

    expect(bootstrap).toMatch(/CREATE SCHEMA IF NOT EXISTS\s+"?auth"?/i);
    expect(bootstrap).not.toMatch(/CREATE TABLE/i);
  });

  it("forces unqualified generated SQL into auth inside one transaction", () => {
    const prepared = prepareAuthMigration(GENERATED_SQL);

    expect(AUTH_SCHEMA).toBe("auth");
    expect(prepared).toMatch(/^BEGIN;/);
    expect(prepared).toContain('SET LOCAL search_path TO "auth", pg_catalog;');
    expect(prepared).toContain('create table "user"');
    expect(prepared).toMatch(/COMMIT;\s*$/);
    expect(() => validatePreparedAuthMigration(prepared)).not.toThrow();
  });

  it.each([
    ['create table public."user" (id text);', "public schema qualification"],
    ['create table "public"."user" (id text);', "quoted public schema qualification"],
    ["set search_path = public; create table x (id text);", "search_path changes"],
    ["begin; create table x (id text); commit;", "nested transactions"],
    ["create schema attacker;", "schema mutation"],
    ['create table attacker."user" (id text);', "arbitrary schema qualification"],
    ["drop table x;", "destructive DDL"],
    ['alter table "user" drop column "email";', "destructive ALTER TABLE"],
    ["create table copied as select current_user;", "CREATE TABLE AS"],
    [
      `create index "unsafe" on "user" ((pg_read_file('/etc/passwd')));`,
      "expression index",
    ],
    ["grant select on x to public;", "privilege changes"],
    ["copy x from '/tmp/input';", "filesystem COPY"],
    ["do $$ begin null; end $$;", "anonymous code blocks"],
    ["\\i /tmp/attacker.sql", "psql meta commands"],
  ])("rejects generated SQL containing %s (%s)", (sql) => {
    expect(() => prepareAuthMigration(sql)).toThrow();
  });

  it("rejects a prepared migration if its transaction/search-path envelope drifts", () => {
    const prepared = prepareAuthMigration(GENERATED_SQL);

    expect(() =>
      validatePreparedAuthMigration(prepared.replace('"auth"', '"public"')),
    ).toThrow();
    expect(() => validatePreparedAuthMigration(prepared.replace("COMMIT;", ""))).toThrow();
    expect(() =>
      validatePreparedAuthMigration(`${prepared}DROP TABLE "user";`),
    ).toThrow();
  });

  it("rejects empty generated SQL", () => {
    expect(() => prepareAuthMigration("")).toThrow();
    expect(() => prepareAuthMigration(";")).toThrow();
  });
});
