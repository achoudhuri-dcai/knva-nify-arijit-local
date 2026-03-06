import { faPaperPlane, faRobot, faUser } from "@fortawesome/free-solid-svg-icons";
import { Alert, Avatar, Box, Button, CircularProgress, Link, Paper, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { selectModule, submitChatTurn } from "../api/client";
import FaIcon from "./FaIcon";
import NifSearchQueryPanel from "./NifSearchQueryPanel";
import type { ChatMessage, ModuleConfig } from "../types";

const TRAINING_SUMMARY_QUESTION = "What training resources are available for NIF and what are the key topics they cover?";
const FIELD_MODULE_UNAVAILABLE_BACKEND = "NIF Field module is not yet available.";
const FIELD_MODULE_UNAVAILABLE_UI = "Sorry! this module is not available at this time .. ";

interface ChatModulePageProps {
  module: ModuleConfig;
  sessionId: string;
  setSessionId: (sid: string) => void;
  submitClicks: number;
  setSubmitClicks: (value: number) => void;
  nifProgressJson: string;
  setNifProgressJson: (value: string) => void;
  activeTaskName: string;
  setActiveTaskName: (value: string) => void;
}

function stripSearchDebugSections(content: string): string {
  const text = String(content || "");
  if (!text.trim()) {
    return "";
  }

  const lower = text.toLowerCase();
  const markers = [
    "sql query output",
    "sql executed:",
    "sample output:",
    "below is a summary of the first 10",
    "below is a summary of the first 25",
    "below is a summary of the first ten",
    "below is a summary of the first twenty five",
    "first 10 rows:",
    "first 25 rows:",
    "```sql",
    "\nsql:",
  ];

  let cutIndex = text.length;
  for (const marker of markers) {
    const index = lower.indexOf(marker);
    if (index >= 0 && index < cutIndex) {
      cutIndex = index;
    }
  }

  const cleaned = cutIndex < text.length ? text.slice(0, cutIndex) : text;
  return cleaned.trim();
}

const chatMarkdownComponents: Components = {
  p: ({ children }) => (
    <Typography variant="body2" component="p" sx={{ mt: 0, mb: 0.8, whiteSpace: "pre-wrap", "&:last-of-type": { mb: 0 } }}>
      {children}
    </Typography>
  ),
  ul: ({ children }) => (
    <Box component="ul" sx={{ mt: 0.2, mb: 0.8, pl: 2.5 }}>
      {children}
    </Box>
  ),
  ol: ({ children }) => (
    <Box component="ol" sx={{ mt: 0.2, mb: 0.8, pl: 2.5 }}>
      {children}
    </Box>
  ),
  li: ({ children }) => (
    <Typography component="li" variant="body2" sx={{ mb: 0.2, whiteSpace: "pre-wrap" }}>
      {children}
    </Typography>
  ),
  a: ({ children, href }) => (
    <Link href={href || "#"} target="_blank" rel="noreferrer" underline="hover" className="chat-markdown-link">
      {children}
    </Link>
  ),
  strong: ({ children }) => (
    <Typography component="strong" variant="body2" sx={{ fontWeight: 700 }}>
      {children}
    </Typography>
  ),
};

export default function ChatModulePage({
  module,
  sessionId,
  setSessionId,
  submitClicks,
  setSubmitClicks,
  nifProgressJson,
  setNifProgressJson,
  activeTaskName,
  setActiveTaskName,
}: ChatModulePageProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQueryResult, setSearchQueryResult] = useState<Record<string, unknown> | null>(null);
  const [searchPromptPayload, setSearchPromptPayload] = useState<Record<string, unknown> | null>(null);
  const [latestResponseMarkdown, setLatestResponseMarkdown] = useState("");
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  const moduleHelp = useMemo(() => {
    if (module.key === "step") {
      return "Tip: type 'Start a new NIF with field LIM' to begin the step flow quickly.";
    }
    if (module.key === "field") {
      return "NIF Field question module is under development. Message input is currently disabled.";
    }
    return "";
  }, [module.key]);

  function normalizeModuleMessage(text: string): string {
    const raw = String(text || "").trim();
    if (!raw) {
      return "";
    }
    if (module.key === "field" && raw === FIELD_MODULE_UNAVAILABLE_BACKEND) {
      return FIELD_MODULE_UNAVAILABLE_UI;
    }
    return raw;
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrapModule() {
      setBusy(true);
      setError(null);
      setSearchQueryResult(null);
      setSearchPromptPayload(null);
      setLatestResponseMarkdown("");
      setMessages([]);
      try {
        const selected = await selectModule({
          selected_question: module.selectedQuestion,
          session_id: sessionId,
          current_clicks: submitClicks,
          nif_progress_data_json: nifProgressJson,
          active_task_name: activeTaskName,
        });

        if (cancelled) {
          return;
        }

        setSessionId(selected.session_id);
        setSubmitClicks(selected.submit_clicks);
        setNifProgressJson(selected.nif_progress_data_json || nifProgressJson);
        setActiveTaskName(selected.active_task_name || activeTaskName);

        const nextMessages: ChatMessage[] = [];
        if (module.key === "training") {
          const nextClicks = (selected.submit_clicks || 0) + 1;
          setSubmitClicks(nextClicks);
          nextMessages.push({ role: "user", content: TRAINING_SUMMARY_QUESTION });

          const turn = await submitChatTurn({
            session_id: selected.session_id,
            submit_clicks: nextClicks,
            human_chat_value: TRAINING_SUMMARY_QUESTION,
            nif_progress_data_json: selected.nif_progress_data_json || nifProgressJson,
            active_task_name: selected.active_task_name || activeTaskName,
          });

          if (cancelled) {
            return;
          }

          setSessionId(turn.session_id || selected.session_id || sessionId);
          setNifProgressJson(turn.nif_progress_data_json || nifProgressJson);
          nextMessages.push({ role: "assistant", content: turn.response_markdown || "" });
          setMessages(nextMessages);
          return;
        }

        if (selected.simple_message?.trim()) {
          nextMessages.push({ role: "system", content: normalizeModuleMessage(selected.simple_message) });
        }

        if (selected.auto_submit && selected.human_chat_value?.trim()) {
          nextMessages.push({ role: "user", content: selected.human_chat_value });
          const turn = await submitChatTurn({
            session_id: selected.session_id,
            submit_clicks: selected.submit_clicks,
            human_chat_value: selected.human_chat_value,
            nif_progress_data_json: selected.nif_progress_data_json || nifProgressJson,
            active_task_name: selected.active_task_name || activeTaskName,
          });

          if (cancelled) {
            return;
          }

          setNifProgressJson(turn.nif_progress_data_json || nifProgressJson);
          nextMessages.push({ role: "assistant", content: turn.response_markdown || "" });
          if (module.key === "search") {
            setSearchQueryResult((turn.nif_query_result ?? null) as Record<string, unknown> | null);
            setSearchPromptPayload((turn.nif_llm_prompt ?? null) as Record<string, unknown> | null);
            setLatestResponseMarkdown(turn.response_markdown || "");
          }
        }

        setMessages(nextMessages);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load module");
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    }

    void bootstrapModule();

    return () => {
      cancelled = true;
    };
  }, [module.selectedQuestion, module.key, sessionId]);

  useEffect(() => {
    if (!chatScrollRef.current) {
      return;
    }
    const el = chatScrollRef.current;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, busy]);

  async function onSubmit() {
    if (module.key === "field" || !input.trim() || busy) {
      return;
    }

    const messageToSend = input.trim();
    setInput("");
    setError(null);
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", content: messageToSend }]);

    try {
      const nextClicks = submitClicks + 1;
      setSubmitClicks(nextClicks);

      const turn = await submitChatTurn({
        session_id: sessionId,
        submit_clicks: nextClicks,
        human_chat_value: messageToSend,
        nif_progress_data_json: nifProgressJson,
        active_task_name: activeTaskName,
      });

      setSessionId(turn.session_id || sessionId);
      setNifProgressJson(turn.nif_progress_data_json || nifProgressJson);
      setMessages((prev) => [...prev, { role: "assistant", content: turn.response_markdown || "" }]);
      if (module.key === "search") {
        setSearchQueryResult((turn.nif_query_result ?? null) as Record<string, unknown> | null);
        setSearchPromptPayload((turn.nif_llm_prompt ?? null) as Record<string, unknown> | null);
        setLatestResponseMarkdown(turn.response_markdown || "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack spacing={1.2} sx={{ height: "100%", minHeight: 0 }}>
      {moduleHelp ? <Alert severity="info">{moduleHelp}</Alert> : null}
      {error ? <Alert severity="error">{error}</Alert> : null}

      <Paper className="chat-shell" elevation={0}>
        <Box className="chat-scroll" ref={chatScrollRef}>
          {messages.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {module.key === "training" ? "Getting response to - What training resources are available for NIF and what are the key topics they cover? " : "Ask a question to begin."}
            </Typography>
          ) : null}

          {messages.map((message, index) => (
            (() => {
              const renderedContent = module.key === "search" && message.role === "assistant"
                ? stripSearchDebugSections(message.content)
                : message.content;
              const renderAssistantMarkdown = message.role === "assistant" && (module.key === "search" || module.key === "training");

              if (!renderedContent.trim()) {
                return null;
              }

              return (
                <Box
                  key={`${message.role}-${index}`}
                  className={`chat-message-row ${message.role === "user" ? "chat-message-row-user" : "chat-message-row-assistant"}`}
                >
                  {message.role === "user" ? null : (
                    <Avatar className="chat-avatar chat-avatar-bot">
                      <FaIcon icon={faRobot} />
                    </Avatar>
                  )}
                  <Paper className={`chat-bubble ${message.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}`} elevation={0}>
                    {renderAssistantMarkdown ? (
                      <Box className="chat-markdown">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={chatMarkdownComponents}>
                          {renderedContent}
                        </ReactMarkdown>
                      </Box>
                    ) : (
                      <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                        {renderedContent}
                      </Typography>
                    )}
                  </Paper>
                  {message.role === "user" ? (
                    <Avatar className="chat-avatar chat-avatar-user">
                      <FaIcon icon={faUser} />
                    </Avatar>
                  ) : null}
                </Box>
              );
            })()
          ))}
        </Box>
      </Paper>

      {module.key === "search" ? (
        <NifSearchQueryPanel
          queryResult={searchQueryResult}
          responseMarkdown={latestResponseMarkdown}
          promptPayload={searchPromptPayload}
        />
      ) : null}

      <Stack direction="row" spacing={1} className="chat-action-bar">
        <TextField
          fullWidth
          size="small"
          placeholder={module.key === "field" ? "NIF Field question module is under development" : "Type your message"}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={module.key === "field"}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void onSubmit();
            }
          }}
        />
        <Button
          variant="contained"
          endIcon={busy ? <CircularProgress size={14} color="inherit" /> : <FaIcon icon={faPaperPlane} />}
          onClick={() => void onSubmit()}
          disabled={module.key === "field" || busy || !input.trim()}
        >
          Send
        </Button>
      </Stack>
    </Stack>
  );
}
