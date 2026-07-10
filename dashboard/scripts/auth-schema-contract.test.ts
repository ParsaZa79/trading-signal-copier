import { readFile } from "node:fs/promises";
import { getMigrations } from "better-auth/db/migration";
import {
  DummyDriver,
  PostgresAdapter,
  PostgresQueryCompiler,
} from "kysely";
import { describe, expect, it } from "vitest";
import {
  buildBetterAuthOptions,
  type BetterAuthSettings,
} from "../src/lib/auth";
import { prepareAuthMigration } from "./auth-schema";

class EmptyPostgresDialect {
  createAdapter() {
    return new PostgresAdapter();
  }

  createDriver() {
    return new DummyDriver();
  }

  createQueryCompiler() {
    return new PostgresQueryCompiler();
  }

  createIntrospector() {
    return { getTables: async () => [] };
  }
}

describe("committed Better Auth schema", () => {
  it("matches SQL compiled from the pinned auth configuration", async () => {
    const settings: BetterAuthSettings = {
      baseURL: "https://schema-contract.invalid",
      captchaAllowedHostnames: ["schema-contract.invalid"],
      databaseURL: "postgresql://schema-contract.invalid/auth",
      jwtAudience: "https://api.schema-contract.invalid",
      openSignupEnabled: false,
      secret: "schema-contract-only-secret-123456789",
      secureCookies: true,
      smtp: {
        from: "auth@schema-contract.invalid",
        host: "localhost",
        password: "unused",
        port: 587,
        secure: false,
        user: "unused",
      },
      trustedOrigins: ["https://schema-contract.invalid"],
      turnstileSecretKey: "schema-contract-only",
    };
    const options = buildBetterAuthOptions(
      settings,
      {} as never,
      async () => undefined,
    );
    options.database = {
      dialect: new EmptyPostgresDialect(),
      type: "postgres",
    } as never;

    const generated = await getMigrations(options);
    const committed = await readFile(
      new URL("../migrations/auth/0001_better_auth.sql", import.meta.url),
      "utf8",
    );

    expect(prepareAuthMigration(await generated.compileMigrations())).toBe(committed);
  });
});
