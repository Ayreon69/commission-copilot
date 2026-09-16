import type { ChatResponse, ToolCallTrace } from "@/lib/api";

export type ToolStep = {
  name: string;
  arguments: Record<string, unknown>;
  trace?: ToolCallTrace;
};

export type UserTurn = {
  id: string;
  role: "user";
  content: string;
};

export type AssistantTurn = {
  id: string;
  role: "assistant";
  status: "streaming" | "done" | "error";
  draft: string;
  steps: ToolStep[];
  response?: ChatResponse;
  error?: string;
  startedAt: number;
  durationMs?: number;
};

export type Turn = UserTurn | AssistantTurn;
