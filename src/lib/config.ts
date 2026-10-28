export type X402Config = {
  enabled: boolean;
  /** x402 v1 HTTP transport */
  version: 1;
  scheme: string;
  network: string;
  maxAmountRequired: string;
  asset: string;
  payTo: string;
  maxTimeoutSeconds: number;
  description: string;
  facilitatorMode: "mock" | "http";
  facilitatorUrl?: string;
};

export type CatalogConfig = {
  host: string;
  port: number;
  publicBaseUrl: string;
  x402: X402Config;
};

function envBool(name: string, defaultValue = false): boolean {
  const v = process.env[name];
  if (v === undefined) return defaultValue;
  return /^(1|true|yes|on)$/i.test(v);
}

export function loadConfig(overrides?: Partial<CatalogConfig>): CatalogConfig {
  const port = overrides?.port ?? Number(process.env.CATALOG_PORT ?? "8787");
  const host = overrides?.host ?? process.env.CATALOG_HOST ?? "127.0.0.1";
  const publicBaseUrl =
    overrides?.publicBaseUrl ??
    process.env.CATALOG_PUBLIC_BASE_URL ??
    `http://${host}:${port}`;

  const x402: X402Config = {
    enabled: overrides?.x402?.enabled ?? envBool("CATALOG_X402_ENABLED", false),
    version: 1,
    scheme: process.env.CATALOG_X402_SCHEME ?? "exact",
    network: process.env.CATALOG_X402_NETWORK ?? "base-sepolia",
    maxAmountRequired: process.env.CATALOG_X402_AMOUNT ?? "1000",
    asset:
      process.env.CATALOG_X402_ASSET ??
      "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    payTo:
      process.env.CATALOG_X402_PAY_TO ??
      "0x0000000000000000000000000000000000000001",
    maxTimeoutSeconds: Number(process.env.CATALOG_X402_TIMEOUT ?? "120"),
    description: "Wetware catalog rank operation (peptide agent routing)",
    facilitatorMode:
      (process.env.CATALOG_X402_FACILITATOR_MODE as "mock" | "http") ?? "mock",
    facilitatorUrl: process.env.CATALOG_X402_FACILITATOR_URL,
  };

  return {
    host,
    port,
    publicBaseUrl,
    x402: { ...x402, ...overrides?.x402 },
  };
}
