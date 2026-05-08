const API_BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

export type Principal = {
  user_id: string;
  tenant: string;
  email: string;
  roles: string[];
  clearance: string;
  departments: string[];
};

export type LoginResult = {
  access_token: string;
  token_type: string;
  expires_in_min: number;
  principal: Principal;
};

export type Citation = {
  index: number;
  chunk_id: string;
  document_id: string;
  document_title: string;
  ordinal: number;
  score: number;
  snippet: string;
};

export type QueryResponse = {
  request_id: string;
  answered: boolean;
  answer: string;
  citations: Citation[];
  policy_reasons: string[];
  retrieved: number;
  top_score: number;
  latency_ms: number;
  tokens: Record<string, number>;
};

export class UnauthorizedError extends Error {
  constructor(message = "No autorizado") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

function joinUrl(path: string): string {
  const base = API_BASE.replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const d = data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
    if (d && typeof d === "object") return JSON.stringify(d);
  } catch {
    /* ignore */
  }
  return res.statusText || `HTTP ${res.status}`;
}

export async function login(
  tenant: string,
  email: string,
  password: string,
): Promise<LoginResult> {
  const res = await fetch(joinUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant, email, password }),
  });
  if (!res.ok) {
    throw new Error(await readErrorDetail(res));
  }
  return res.json() as Promise<LoginResult>;
}

export async function sendQuery(
  token: string,
  query: string,
): Promise<QueryResponse> {
  const res = await fetch(joinUrl("/query"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });
  if (res.status === 401) {
    throw new UnauthorizedError(await readErrorDetail(res));
  }
  if (!res.ok) {
    throw new Error(await readErrorDetail(res));
  }
  return res.json() as Promise<QueryResponse>;
}
