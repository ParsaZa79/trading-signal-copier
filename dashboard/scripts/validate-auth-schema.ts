import { loadAuthSchemaFiles } from "./apply-auth-schema";

const files = await loadAuthSchemaFiles();
console.log(`Validated ${files.migrations.length} prepared auth migration(s)`);
