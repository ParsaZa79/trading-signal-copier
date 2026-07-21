import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: [
      {
        find: /^@workos-inc\/authkit-nextjs\/components$/,
        replacement: fileURLToPath(
          new URL("./src/test/workos-authkit-components.ts", import.meta.url)
        ),
      },
      {
        find: /^@workos-inc\/authkit-nextjs$/,
        replacement: fileURLToPath(
          new URL("./src/test/workos-authkit-server.ts", import.meta.url)
        ),
      },
      { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
    ],
  },
  test: {
    environment: "node",
  },
});
