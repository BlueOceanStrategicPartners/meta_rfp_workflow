export type ClientSessionTranscriptTurn = {
  role: string;
  text: string;
  at?: string;
};

export type ClientTurnHandoff = {
  gathered?: Record<string, string | number>;
  still_needed?: string[];
  ask_next?: string[];
  notes_for_next_turn?: string;
  updated_at?: string;
};

export type ClientSessionState = {
  clarification_options?: string[];
  agent_todos?: { id: string; text: string; status: string }[];
  events?: { at?: string; type?: string; summary?: string }[];
  transcript?: ClientSessionTranscriptTurn[];
  turn_handoff?: ClientTurnHandoff;
  intake?: Record<string, string>;
};
