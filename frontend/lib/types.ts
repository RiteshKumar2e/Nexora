export type Role = "system" | "user" | "assistant";

export interface Message {
  id?: string;
  role: Role;
  content: string;
  model?: string | null;
  created_at?: string;
}

export interface Conversation {
  id: string;
  title: string;
  model?: string | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

// SSE event payloads emitted by POST /api/chat
export interface MetaEvent {
  conversation_id: string;
  title: string;
  is_new: boolean;
}
export interface TokenEvent {
  delta: string;
}
export interface DoneEvent {
  conversation_id: string;
  message_id: string | null;
  usage: { prompt_tokens: number | null; completion_tokens: number | null };
}
export interface ErrorEvent {
  message: string;
}
