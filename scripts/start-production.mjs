import { cp } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const project = new URL("../", import.meta.url);
await cp(new URL(".next/static", project), new URL(".next/standalone/.next/static", project), { recursive: true });
process.env.HOSTNAME ??= "127.0.0.1";
process.env.PORT ??= "3000";
await import(fileURLToPath(new URL(".next/standalone/server.js", project)));
