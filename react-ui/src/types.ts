export type ModuleKey = "training" | "step" | "search" | "field";

export interface ModuleConfig {
  key: ModuleKey;
  label: string;
  path: string;
  selectedQuestion: string;
}

export interface SessionResponse {
  session_id: string;
  active_task_name: string;
  nif_progress_data_json: string;
  llm_provider?: string;
  llm_model?: string;
  llm_header_text?: string;
}

export interface HealthLiveResponse {
  status: string;
  version: string;
  llm_provider: string;
  llm_model: string;
  llm_header_text?: string;
  timestamp_utc: string;
}

export interface ModuleSelectResponse {
  session_id: string;
  selected_question: string;
  human_chat_value: string;
  submit_clicks: number;
  nif_progress_data_json: string;
  active_task_name: string;
  simple_message: string;
  auto_submit: boolean;
}

export interface ChatTurnResponse {
  session_id: string;
  active_task_name: string;
  response_markdown: string;
  nif_progress_data_json: string;
  nif_query_result: Record<string, unknown> | null;
  nif_llm_prompt: Record<string, unknown> | null;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface NifStepOption {
  id: "new" | "load";
  label: string;
}

export interface NifStepOptionsResponse {
  actions: NifStepOption[];
}

export interface SavedNifFileOption {
  label: string;
  value: string;
}

export interface SavedNifFilesResponse {
  files: SavedNifFileOption[];
  message: string;
}

export interface NifSessionActionResponse {
  ok: boolean;
  code: string;
  message: string;
  session_id: string;
  active_task_name: string;
  submit_clicks: number;
  human_chat_value: string;
  nif_progress_data_json: string;
  simple_message: string;
  auto_submit: boolean;
  loaded_filename?: string;
}

export interface NifSaveSessionResponse {
  ok: boolean;
  code: string;
  message: string;
  saved_filename: string;
  saved_label: string;
  files: SavedNifFileOption[];
}

export interface NifSimpleMessageResponse {
  ok: boolean;
  code: string;
  message: string;
}

export interface NifProgressPreviewResponse {
  ok: boolean;
  code: string;
  message: string;
  progress_text: string;
}

export type HistoryRange = "current" | "past_30_days";

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp_utc: string;
}

export interface HistoryResponse {
  session_id: string;
  range: HistoryRange;
  messages: HistoryMessage[];
}

export interface HistoryClearResponse {
  ok: boolean;
  code: string;
  message: string;
  session_id: string;
  removed_history_files: number;
  removed_nif_files: number;
  nif_progress_data_json: string;
}
