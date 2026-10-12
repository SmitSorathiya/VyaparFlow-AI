export type WorkflowState =
  | "RECEIVED"
  | "PROCESSING"
  | "CLASSIFIED"
  | "EXTRACTED"
  | "VALIDATING"
  | "NEEDS_CLARIFICATION"
  | "READY_FOR_ACTION"
  | "HUMAN_REVIEW"
  | "APPROVED"
  | "COMPLETED"
  | "FAILED"
  | "ERROR_RECOVERY";

export interface DocumentInfo {
  type: string;
  confidence: number;
  reason: string;
}

export interface OCRInfo {
  raw_text: string;
}

export interface Workflow {
  id: number;
  state: WorkflowState;
  original_filename: string;
  file_hash?: string;
  file_size?: number;
  image_width?: number;
  image_height?: number;
  ocr_provider?: string;
  document?: DocumentInfo;
  ocr?: OCRInfo;
  normalized_text?: string;
  extraction?: Record<string, any>;
  field_confidence?: Record<string, { score: number; status: string; evidence?: string }>;
  provenance?: Record<string, any>;
  missing_info?: string[];
  recommended_action?: string;
  draft_message?: string;
  created_at: string;
  updated_at: string;
  error_message?: string;
}

export interface AuditLog {
  id: number;
  workflow_id: number;
  state: string;
  message: string;
  created_at: string;
}

export interface DashboardStats {
  processed: number;
  completed: number;
  needs_review: number;
  blocked: number;
  recent_workflows: Workflow[];
}
