export type CatalogConfig = {
  host: string;
  port: number;
  publicBaseUrl: string;
};

export function loadConfig(overrides?: Partial<CatalogConfig>): CatalogConfig {
  const port = overrides?.port ?? Number(process.env.CATALOG_PORT ?? "8787");
  const host = overrides?.host ?? process.env.CATALOG_HOST ?? "127.0.0.1";
  const publicBaseUrl =
    overrides?.publicBaseUrl ??
    process.env.CATALOG_PUBLIC_BASE_URL ??
    `http://${host}:${port}`;

  return { host, port, publicBaseUrl };
}
