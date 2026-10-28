import type { X402Config } from "./config.js";

/** x402 v1 PaymentRequirements (HTTP transport body field). */
export type PaymentRequirements = {
  scheme: string;
  network: string;
  maxAmountRequired: string;
  resource: string;
  description: string;
  mimeType?: string;
  outputSchema?: Record<string, unknown> | null;
  payTo: string;
  maxTimeoutSeconds: number;
  asset: string;
  extra?: Record<string, unknown> | null;
};

export type PaymentRequiredResponse = {
  x402Version: 1;
  error: string;
  accepts: PaymentRequirements[];
};

export type PaymentPayload = {
  x402Version: 1;
  scheme: string;
  network: string;
  payload: Record<string, unknown>;
};

export type SettlementResponse = {
  success: boolean;
  transaction?: string;
  network?: string;
  payer?: string;
  errorReason?: string;
};

export function buildPaymentRequirements(
  cfg: X402Config,
  resourceUrl: string,
): PaymentRequirements {
  return {
    scheme: cfg.scheme,
    network: cfg.network,
    maxAmountRequired: cfg.maxAmountRequired,
    asset: cfg.asset,
    payTo: cfg.payTo,
    resource: resourceUrl,
    description: cfg.description,
    mimeType: "application/json",
    outputSchema: null,
    maxTimeoutSeconds: cfg.maxTimeoutSeconds,
    extra: { catalog: "wetware-rank-v1" },
  };
}

export function paymentRequiredBody(
  cfg: X402Config,
  resourceUrl: string,
  error = "Payment required to access this resource",
): PaymentRequiredResponse {
  return {
    x402Version: 1,
    error,
    accepts: [buildPaymentRequirements(cfg, resourceUrl)],
  };
}

export function encodeHeaderJson(obj: unknown): string {
  return Buffer.from(JSON.stringify(obj), "utf8").toString("base64");
}

export function decodeHeaderJson<T>(header: string): T {
  return JSON.parse(Buffer.from(header, "base64").toString("utf8")) as T;
}

export type Facilitator = {
  verify(payload: PaymentPayload, requirements: PaymentRequirements): Promise<{ valid: boolean; payer?: string; reason?: string }>;
  settle(payload: PaymentPayload, requirements: PaymentRequirements): Promise<SettlementResponse>;
};

/** Offline test facilitator — never touches chain; accepts mock authorizations only. */
export function createMockFacilitator(): Facilitator {
  return {
    async verify(payload, requirements) {
      const auth = payload.payload?.authorization as { from?: string; to?: string; value?: string } | undefined;
      if (!auth?.from || !auth.to) {
        return { valid: false, reason: "missing_authorization" };
      }
      if (auth.to.toLowerCase() !== requirements.payTo.toLowerCase()) {
        return { valid: false, reason: "pay_to_mismatch" };
      }
      if (auth.value !== requirements.maxAmountRequired) {
        return { valid: false, reason: "amount_mismatch" };
      }
      return { valid: true, payer: auth.from };
    },
    async settle(payload, requirements) {
      const v = await this.verify(payload, requirements);
      if (!v.valid) {
        return {
          success: false,
          errorReason: v.reason ?? "invalid_payment",
          network: requirements.network,
          payer: v.payer,
          transaction: "",
        };
      }
      return {
        success: true,
        transaction: "mock_tx_" + Buffer.from(JSON.stringify(payload.payload)).toString("hex").slice(0, 16),
        network: requirements.network,
        payer: v.payer,
      };
    },
  };
}

export function createHttpFacilitator(baseUrl: string): Facilitator {
  return {
    async verify(payload, requirements) {
      const res = await fetch(`${baseUrl.replace(/\/$/, "")}/verify`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ payload, requirements }),
      });
      if (!res.ok) return { valid: false, reason: `facilitator_http_${res.status}` };
      return (await res.json()) as { valid: boolean; payer?: string; reason?: string };
    },
    async settle(payload, requirements) {
      const res = await fetch(`${baseUrl.replace(/\/$/, "")}/settle`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ payload, requirements }),
      });
      if (!res.ok) {
        return { success: false, errorReason: `facilitator_http_${res.status}`, network: requirements.network };
      }
      return (await res.json()) as SettlementResponse;
    },
  };
}

export function createFacilitator(cfg: X402Config): Facilitator {
  if (cfg.facilitatorMode === "http" && cfg.facilitatorUrl) {
    return createHttpFacilitator(cfg.facilitatorUrl);
  }
  return createMockFacilitator();
}

/** Test helper: build a mock X-PAYMENT header value for integration tests. */
export function mockPaymentHeader(cfg: X402Config, payer = "0x0000000000000000000000000000000000000abc"): string {
  const payload: PaymentPayload = {
    x402Version: 1,
    scheme: cfg.scheme,
    network: cfg.network,
    payload: {
      signature: "0xmock",
      authorization: {
        from: payer,
        to: cfg.payTo,
        value: cfg.maxAmountRequired,
        validAfter: String(Math.floor(Date.now() / 1000) - 60),
        validBefore: String(Math.floor(Date.now() / 1000) + cfg.maxTimeoutSeconds),
        nonce: "0xmocknonce",
      },
    },
  };
  return encodeHeaderJson(payload);
}
