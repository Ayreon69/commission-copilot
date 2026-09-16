import type { components } from "./api-types";

type Schemas = components["schemas"];

export type AmountOut = Schemas["AmountOut"];
export type CalculationOut = Schemas["CalculationOut"];
export type ChatMessage = Schemas["ChatMessage"];
export type ChatResponse = Schemas["ChatResponse"];
export type CitationOut = Schemas["CitationOut"];
export type CommissionLineOut = Schemas["CommissionLineOut"];
export type ContractRecordOut = Schemas["ContractRecordOut"];
export type ExclusionOut = Schemas["ExclusionOut"];
export type HealthOut = Schemas["HealthOut"];
export type PerimeterDetailsOut = Schemas["PerimeterDetailsOut"];
export type PerimeterSummaryOut = Schemas["PerimeterSummaryOut"];
export type SimulationRequest = Schemas["SimulationRequest"];
export type ToolCallTrace = Schemas["ToolCallTrace"];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const UNREACHABLE = `API injoignable sur ${API_URL}. Lancez-la avec : uvicorn commission_api.main:create_app --factory`;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg: string }) => item.msg).join(" ; ");
    }
  } catch {
    // corps absent ou non JSON : message générique ci-dessous
  }
  return `Erreur ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(UNREACHABLE, 0);
  }
  if (!response.ok) throw new ApiError(await errorDetail(response), response.status);
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthOut>("/api/health"),
  perimeters: () => request<PerimeterSummaryOut[]>("/api/perimeters"),
  perimeter: (code: string) => request<PerimeterDetailsOut>(`/api/perimeters/${encodeURIComponent(code)}`),
  simulate: (body: SimulationRequest) =>
    request<CalculationOut>("/api/simulate", { method: "POST", body: JSON.stringify(body) }),
};

export type StreamHandlers = {
  onDelta: (text: string) => void;
  onToolCall: (name: string, args: Record<string, unknown>) => void;
  onToolResult: (trace: ToolCallTrace) => void;
  onDone: (response: ChatResponse) => void;
  onError: (status: number, detail: string) => void;
};

/** Pose une question en suivant le flux Server-Sent Events de /api/chat/stream. */
export async function streamChat(messages: ChatMessage[], handlers: StreamHandlers, signal?: AbortSignal) {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
      signal,
    });
  } catch {
    if (!signal?.aborted) handlers.onError(0, UNREACHABLE);
    return;
  }
  if (!response.ok || !response.body) {
    handlers.onError(response.status, await errorDetail(response));
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value.replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        dispatch(buffer.slice(0, boundary), handlers);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch {
    if (!signal?.aborted) handlers.onError(0, "La connexion a été interrompue pendant la réponse.");
  }
}

function dispatch(block: string, handlers: StreamHandlers) {
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data += line.slice(6);
  }
  if (!event) return;
  const payload = JSON.parse(data || "{}");
  switch (event) {
    case "delta":
      handlers.onDelta(payload.text);
      break;
    case "tool_call":
      handlers.onToolCall(payload.name, payload.arguments);
      break;
    case "tool_result":
      handlers.onToolResult(payload as ToolCallTrace);
      break;
    case "done":
      handlers.onDone(payload as ChatResponse);
      break;
    case "error":
      handlers.onError(payload.status, payload.detail);
      break;
  }
}
