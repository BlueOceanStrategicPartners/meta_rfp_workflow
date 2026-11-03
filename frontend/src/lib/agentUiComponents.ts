export type AgentUiComponent =
  | {
      type: "availability_table";
      title: string;
      caption?: string;
      columns: { key: string; label: string; align?: "left" | "right" }[];
      rows: Record<string, string | number>[];
      highlights?: string[];
    };

export type VoiceTurnResult = {
  reply: string;
  uiComponent: AgentUiComponent | null;
};

export function parseUiComponent(raw: unknown): AgentUiComponent | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (o.type !== "availability_table") return null;
  if (!Array.isArray(o.rows) || !Array.isArray(o.columns)) return null;
  return o as AgentUiComponent;
}
