export type ClientSessionTranscriptTurn = {
  role: string;
  text: string;
  at?: string;
};

export type ClientSessionState = {
  clarification_options?: string[];
  agent_todos?: { id: string; text: string; status: string }[];
  events?: { at?: string; type?: string; summary?: string }[];
  transcript?: ClientSessionTranscriptTurn[];
};
