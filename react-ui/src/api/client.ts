import type {
  ChatTurnResponse,
  HealthLiveResponse,
  HistoryClearResponse,
  HistoryRange,
  HistoryResponse,
  ModuleSelectResponse,
  NifProgressPreviewResponse,
  NifSaveSessionResponse,
  NifSessionActionResponse,
  NifSimpleMessageResponse,
  NifStepOptionsResponse,
  SavedNifFilesResponse,
  SessionResponse,
} from "../types";

function apiBaseUrl(): string {
  const configured = String(import.meta.env.VITE_API_BASE_URL ?? "").trim();
  return configured || "";
}

function devBypassHeaders(): Record<string, string> {
  const key = String(import.meta.env.VITE_AWS_DEV_AUTH_BYPASS_KEY ?? "").trim();
  if (!key) {
    return {};
  }
  return { "X-Dev-Bypass-Key": key };
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...devBypassHeaders(),
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    const raw = await response.text();
    let errMessage = "";
    try {
      const errJson = JSON.parse(raw) as { message?: string; code?: string };
      errMessage = String(errJson.message || "").trim();
    } catch {
      // If not JSON or no message field, fall through to raw text.
    }
    throw new Error(String(errMessage || raw || `Request failed (${response.status})`));
  }
  return response.json() as Promise<T>;
}

export async function createSession(): Promise<SessionResponse> {
  return requestJson<SessionResponse>("/api/v1/session", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function fetchHealthLive(): Promise<HealthLiveResponse> {
  return requestJson<HealthLiveResponse>("/api/v1/health/live", {
    method: "GET",
  });
}

export async function selectModule(payload: {
  selected_question: string;
  session_id: string;
  current_clicks: number;
  nif_progress_data_json: string;
  active_task_name: string;
}): Promise<ModuleSelectResponse> {
  return requestJson<ModuleSelectResponse>("/api/v1/modules/select", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitChatTurn(payload: {
  session_id: string;
  submit_clicks: number;
  human_chat_value: string;
  nif_progress_data_json: string;
  active_task_name: string;
}): Promise<ChatTurnResponse> {
  return requestJson<ChatTurnResponse>("/api/v1/chat/turn", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchNifStepOptions(): Promise<NifStepOptionsResponse> {
  return requestJson<NifStepOptionsResponse>("/api/v1/nif/step/options", {
    method: "GET",
  });
}

export async function fetchSavedNifFiles(): Promise<SavedNifFilesResponse> {
  return requestJson<SavedNifFilesResponse>("/api/v1/nif/saved", {
    method: "GET",
  });
}

export async function startNewNifSession(payload: {
  session_id: string;
  submit_clicks: number;
}): Promise<NifSessionActionResponse> {
  return requestJson<NifSessionActionResponse>("/api/v1/nif/new-session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loadNifSession(payload: {
  session_id: string;
  submit_clicks: number;
  filename: string;
}): Promise<NifSessionActionResponse> {
  return requestJson<NifSessionActionResponse>("/api/v1/nif/load-session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveNifSession(payload: {
  filename: string;
  nif_progress_data_json: string;
}): Promise<NifSaveSessionResponse> {
  return requestJson<NifSaveSessionResponse>("/api/v1/nif/save-session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function reloadNifConfig(payload: {
  active_task_name: string;
}): Promise<NifSimpleMessageResponse> {
  return requestJson<NifSimpleMessageResponse>("/api/v1/nif/reload-config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchNifProgressPreview(payload: {
  nif_progress_data_json: string;
}): Promise<NifProgressPreviewResponse> {
  return requestJson<NifProgressPreviewResponse>("/api/v1/nif/progress-preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function downloadNifFile(payload: {
  filename: string;
  nif_progress_data_json: string;
}): Promise<void> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/nif/download`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...devBypassHeaders(),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const raw = await response.text();
    let errMessage = "";
    try {
      const errJson = JSON.parse(raw) as { message?: string };
      errMessage = String(errJson.message || "").trim();
    } catch {
      // no-op
    }
    throw new Error(String(errMessage || raw || `Request failed (${response.status})`));
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const matched = disposition.match(/filename=\"?([^\";]+)\"?/i);
  const filename = matched?.[1] || "nif_progress.csv";

  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export async function fetchHistory(payload: {
  session_id: string;
  range: HistoryRange;
}): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    session_id: payload.session_id,
    range: payload.range,
  });
  return requestJson<HistoryResponse>(`/api/v1/history?${params.toString()}`, {
    method: "GET",
  });
}

export async function clearHistory(payload: {
  session_id: string;
}): Promise<HistoryClearResponse> {
  return requestJson<HistoryClearResponse>("/api/v1/history/clear", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
