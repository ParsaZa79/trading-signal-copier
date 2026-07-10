import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { getMigrations } from "better-auth/db/migration";
import { Pool } from "pg";
import {
  buildBetterAuthOptions,
  type BetterAuthSettings,
} from "../src/lib/auth";
import { AUTH_SCHEMA, prepareAuthMigration } from "./auth-schema";

const outputArgument = process.argv[2];
if (!outputArgument) {
  throw new Error(
    "Output path is required (for example migrations/auth/0002_description.sql)",
  );
}
const output = resolve(outputArgument);
if (!/^\d{4}_[a-z0-9_]+\.sql$/.test(output.split("/").at(-1) ?? "")) {
  throw new Error("Migration filename must match NNNN_lowercase_name.sql");
}
const databaseURL = process.env.TEST_DATABASE_URL;
if (!databaseURL) {
  throw new Error("TEST_DATABASE_URL is required and must point to disposable PostgreSQL");
}

const pool = new Pool({
  connectionString: databaseURL,
  options: `-c search_path=${AUTH_SCHEMA}`,
  max: 1,
  allowExitOnIdle: true,
});

try {
  const schema = await pool.query("SELECT current_schema() AS schema");
  if (schema.rows[0]?.schema !== AUTH_SCHEMA) {
    throw new Error(
      "The disposable auth schema must be bootstrapped before generation",
    );
  }
  const settings: BetterAuthSettings = {
    baseURL: "https://auth-schema.invalid",
    captchaAllowedHostnames: ["auth-schema.invalid"],
    databaseURL,
    jwtAudience: "https://auth-schema-api.invalid",
    openSignupEnabled: false,
    secret: "auth-schema-generation-only-secret",
    secureCookies: true,
    smtp: {
      from: "auth-schema@example.invalid",
      host: "localhost",
      password: "unused",
      port: 587,
      secure: false,
      user: "unused",
    },
    trustedOrigins: ["https://auth-schema.invalid"],
    turnstileSecretKey: "schema-generation-only",
  };
  const options = buildBetterAuthOptions(
    settings,
    pool,
    async () => undefined,
  );
  const migration = await getMigrations(options);
  const prepared = prepareAuthMigration(await migration.compileMigrations());
  await writeFile(output, prepared, { encoding: "utf8", flag: "wx" });
  console.log(`Prepared auth migration: ${output.split("/").at(-1)}`);
} finally {
  await pool.end().catch(() => undefined);
}
