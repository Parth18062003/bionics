/**
 * AADAP — Chat Types
 * ===================
 * TypeScript types for chat functionality.
 */

export type Role = 'user' | 'assistant' | 'system';

export interface FieldWithConfidence {
  value: string | string[] | null;
  confidence: number;
  source?: string;
}

export interface ExtractedRequirements {
  task_name: FieldWithConfidence | null;
  description: FieldWithConfidence | null;
  target_table: FieldWithConfidence | null;
  objective: FieldWithConfidence | null;
  success_criteria: FieldWithConfidence | null;
  constraints: FieldWithConfidence | null;
  overall_confidence: number;
  is_complete: boolean;
  extraction_notes?: string[];
}

export interface ChatMessage {
  role: Role;
  content: string;
  timestamp: string;
  extracted_requirements?: ExtractedRequirements;
}

export interface ChatSession {
  session_id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  current_requirements: ExtractedRequirements | null;
  completeness?: [number, number];
}

// SSE Event Types
export type SSEEventType = 'content' | 'requirements' | 'done' | 'error';

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  requirements?: ExtractedRequirements;
  session_id?: string;
  message?: string;
}

// API Request/Response Types
export interface SessionCreateResponse {
  session_id: string;
  created_at: string;
}

export interface MessageRequest {
  message: string;
}

export interface RequirementsUpdateRequest {
  task_name?: { value: string; confidence: number };
  description?: { value: string; confidence: number };
  target_table?: { value: string; confidence: number };
  objective?: { value: string; confidence: number };
  success_criteria?: { value: string[]; confidence: number };
  constraints?: { value: string[]; confidence: number };
}

export interface TaskCreateResponse {
  task_id: string;
  redirect_url: string;
}
