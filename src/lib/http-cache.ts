import { createHash } from "node:crypto";

export function computeEtag(body: string | Buffer): string {
  const hash = createHash("sha256").update(body).digest("hex").slice(0, 16);
  return `"${hash}"`;
}

export function cacheControlPublic(maxAgeSeconds = 60): string {
  return `public, max-age=${maxAgeSeconds}`;
}

export function negotiateJson(
  accept: string | undefined,
  defaultType = "application/json",
): { ok: true; contentType: string } | { ok: false } {
  if (!accept || accept.includes("*/*") || accept.includes("application/json")) {
    return { ok: true, contentType: defaultType };
  }
  if (accept.includes("application/fhir+json")) {
    return { ok: true, contentType: "application/json" };
  }
  return { ok: false };
}
