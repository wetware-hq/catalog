import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const srcDir = dirname(fileURLToPath(import.meta.url));
/** Repository / package root (parent of `src`). */
export const packageRoot = join(srcDir, "..", "..");

export function repoPath(...segments: string[]): string {
  return join(packageRoot, ...segments);
}
