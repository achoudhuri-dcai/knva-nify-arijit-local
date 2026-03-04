import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import AutorenewRoundedIcon from "@mui/icons-material/AutorenewRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import FolderOpenRoundedIcon from "@mui/icons-material/FolderOpenRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import SmartToyRoundedIcon from "@mui/icons-material/SmartToyRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  ButtonBase,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  downloadNifFile,
  fetchNifStepOptions,
  fetchSavedNifFiles,
  loadNifSession,
  reloadNifConfig,
  saveNifSession,
  selectModule,
  startNewNifSession,
  submitChatTurn,
} from "../api/client";
import NifProgressGridDialog from "./NifProgressGridDialog";
import type { ChatMessage, ModuleConfig, NifSessionActionResponse, NifStepOption, SavedNifFileOption } from "../types";

interface NifStepSessionPageProps {
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

const DEFAULT_ACTIONS: NifStepOption[] = [
  { id: "new", label: "New NIF chat session" },
  { id: "load", label: "Load NIF from previous chat" },
];

interface OptionChoice {
  id: string;
  label: string;
}

interface ParsedOptionPrompt {
  promptText: string;
  options: OptionChoice[];
  allowMulti: boolean;
}

function parseAssistantOptionPrompt(content: string): ParsedOptionPrompt | null {
  const raw = String(content || "").replace(/\r/g, "").trim();
  if (!raw) {
    return null;
  }

  const flattened = raw.replace(/\n+/g, " ").replace(/\s+/g, " ").trim();
  const optionRegex = /(?:^|\s)(\d{1,3})\.\s+(.+?)(?=(?:\s+\d{1,3}\.\s+)|$)/g;

  const options: OptionChoice[] = [];
  let match: RegExpExecArray | null = null;
  while ((match = optionRegex.exec(flattened)) !== null) {
    const id = String(match[1] || "").trim();
    const label = String(match[2] || "")
      .replace(/\s+/g, " ")
      .replace(/reply with the option number or option text\.?$/i, "")
      .trim();
    if (id && label) {
      options.push({ id, label });
    }
  }

  // Remove duplicate labels while preserving first-seen order/id.
  const dedupedOptions: OptionChoice[] = [];
  const seenLabels = new Set<string>();
  for (const option of options) {
    const norm = option.label.toLowerCase().replace(/\s+/g, " ").trim();
    if (!norm || seenLabels.has(norm)) {
      continue;
    }
    seenLabels.add(norm);
    dedupedOptions.push(option);
  }

  const optionsToUse = dedupedOptions.length ? dedupedOptions : options;

  if (optionsToUse.length < 2) {
    return null;
  }

  // Preserve full question/instruction text from original lines, removing only
  // numbered option rows and the reply hint row.
  const rawLines = raw.split("\n");
  const nonOptionLines = rawLines.filter((line) => {
    const lineText = String(line || "").trim();
    if (!lineText) {
      return false;
    }
    if (/^\d{1,3}\.\s+/.test(lineText)) {
      return false;
    }
    if (/^reply with the option number or option text\.?$/i.test(lineText)) {
      return false;
    }
    return true;
  });

  let promptText = nonOptionLines.join("\n").trim();
  if (!promptText) {
    const firstMarker = flattened.match(/(?:^|\s)\d{1,3}\.\s+/);
    promptText = firstMarker && typeof firstMarker.index === "number"
      ? flattened.slice(0, firstMarker.index).trim()
      : "";
  }
  if (!promptText) {
    promptText = "Select from the options below:";
  }

  const lower = flattened.toLowerCase();
  const allowMulti = [
    "one or more",
    "select one or more",
    "multiple options",
    "multiple choice",
    "select multiple",
    "all that apply",
    "choose multiple",
    "more than one",
  ].some((marker) => lower.includes(marker));

  return {
    promptText,
    options: optionsToUse,
    allowMulti,
  };
}

export default function NifStepSessionPage({
  module,
  sessionId,
  setSessionId,
  submitClicks,
  setSubmitClicks,
  nifProgressJson,
  setNifProgressJson,
  activeTaskName,
  setActiveTaskName,
}: NifStepSessionPageProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);

  const [showStarter, setShowStarter] = useState(true);
  const [showLoadPanel, setShowLoadPanel] = useState(false);
  const [actions, setActions] = useState<NifStepOption[]>(DEFAULT_ACTIONS);
  const [savedFiles, setSavedFiles] = useState<SavedNifFileOption[]>([]);
  const [savedFilesMessage, setSavedFilesMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState<SavedNifFileOption | null>(null);
  const [saveFilename, setSaveFilename] = useState("My In-progress NIF");
  const [statusEvents, setStatusEvents] = useState<string[]>([]);

  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showProgressDialog, setShowProgressDialog] = useState(false);
  const [inlineSelectedSingle, setInlineSelectedSingle] = useState<OptionChoice | null>(null);
  const [inlineSelectedMulti, setInlineSelectedMulti] = useState<OptionChoice[]>([]);
  const [inlineOptionFilter, setInlineOptionFilter] = useState("");

  const isAnyBusy = busy || actionBusy;
  const loadDisabled = useMemo(
    () => isAnyBusy || !selectedFile || savedFiles.length === 0,
    [isAnyBusy, selectedFile, savedFiles.length],
  );
  const saveDisabled = useMemo(
    () => isAnyBusy || !saveFilename.trim(),
    [isAnyBusy, saveFilename],
  );
  const activeOptionPrompt = useMemo(() => {
    if (!messages.length) {
      return null;
    }
    const lastIndex = messages.length - 1;
    const lastMessage = messages[lastIndex];
    if (lastMessage.role !== "assistant") {
      return null;
    }
    const parsed = parseAssistantOptionPrompt(lastMessage.content);
    if (!parsed) {
      return null;
    }
    return {
      ...parsed,
      index: lastIndex,
    };
  }, [messages]);
  const filteredInlineOptions = useMemo(() => {
    if (!activeOptionPrompt) {
      return [];
    }
    const query = inlineOptionFilter.trim().toLowerCase();
    if (!query) {
      return activeOptionPrompt.options;
    }
    return activeOptionPrompt.options.filter((option) => (
      `${option.id} ${option.label}`.toLowerCase().includes(query)
    ));
  }, [activeOptionPrompt, inlineOptionFilter]);

  function appendStatus(message: string) {
    const text = String(message || "").trim();
    if (!text) {
      return;
    }
    setStatusEvents((prev) => {
      const next = [...prev, text];
      return next.slice(-4);
    });
  }

  async function bootstrapStepPage() {
    const selected = await selectModule({
      selected_question: module.selectedQuestion,
      session_id: sessionId,
      current_clicks: submitClicks,
      nif_progress_data_json: nifProgressJson,
      active_task_name: activeTaskName,
    });

    setSessionId(selected.session_id);
    setSubmitClicks(selected.submit_clicks);
    setNifProgressJson(selected.nif_progress_data_json || nifProgressJson);
    setActiveTaskName(selected.active_task_name || activeTaskName);
  }

  async function fetchStepActionsAndFiles() {
    try {
      const options = await fetchNifStepOptions();
      if (Array.isArray(options.actions) && options.actions.length > 0) {
        setActions(options.actions);
      }
    } catch {
      setActions(DEFAULT_ACTIONS);
    }

    try {
      const saved = await fetchSavedNifFiles();
      setSavedFiles(saved.files || []);
      setSavedFilesMessage(saved.message || "");
      const nextFiles = saved.files || [];
      setSelectedFile((current) => {
        if (!current) {
          return null;
        }
        return nextFiles.some((file) => file.value === current.value) ? current : null;
      });
    } catch (err) {
      setSavedFiles([]);
      setSavedFilesMessage(err instanceof Error ? err.message : "Failed to fetch saved NIF files.");
      setSelectedFile(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) {
      return () => {
        cancelled = true;
      };
    }

    async function init() {
      setBusy(true);
      setError(null);
      try {
        await bootstrapStepPage();
        await fetchStepActionsAndFiles();
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to initialize NIF step page.");
        }
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    }

    void init();
    return () => {
      cancelled = true;
    };
  }, [module.selectedQuestion, sessionId]);

  useEffect(() => {
    if (!chatScrollRef.current) {
      return;
    }
    const el = chatScrollRef.current;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, busy, actionBusy]);

  useEffect(() => {
    setInlineSelectedSingle(null);
    setInlineSelectedMulti([]);
    setInlineOptionFilter("");
  }, [activeOptionPrompt?.index]);

  function isInlineOptionSelected(optionId: string): boolean {
    if (activeOptionPrompt?.allowMulti) {
      return inlineSelectedMulti.some((option) => option.id === optionId);
    }
    return inlineSelectedSingle?.id === optionId;
  }

  function toggleInlineOption(option: OptionChoice): void {
    if (!activeOptionPrompt) {
      return;
    }
    if (activeOptionPrompt.allowMulti) {
      setInlineSelectedMulti((prev) => (
        prev.some((item) => item.id === option.id)
          ? prev.filter((item) => item.id !== option.id)
          : [...prev, option]
      ));
      return;
    }
    setInlineSelectedSingle((prev) => (prev?.id === option.id ? null : option));
  }

  async function runAutoChatFromAction(actionResult: NifSessionActionResponse) {
    setSessionId(actionResult.session_id || sessionId);
    setSubmitClicks(actionResult.submit_clicks || submitClicks);
    setNifProgressJson(actionResult.nif_progress_data_json || nifProgressJson);
    setActiveTaskName(actionResult.active_task_name || "nifguide_task");

    if (actionResult.simple_message?.trim()) {
      appendStatus(actionResult.simple_message.trim());
      setMessages((prev) => [...prev, { role: "system", content: actionResult.simple_message.trim() }]);
    }

    if (actionResult.auto_submit && actionResult.human_chat_value?.trim()) {
      const userMessage = actionResult.human_chat_value.trim();
      setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

      const turn = await submitChatTurn({
        session_id: actionResult.session_id || sessionId,
        submit_clicks: actionResult.submit_clicks || submitClicks,
        human_chat_value: userMessage,
        nif_progress_data_json: actionResult.nif_progress_data_json || nifProgressJson,
        active_task_name: actionResult.active_task_name || "nifguide_task",
      });

      setSessionId(turn.session_id || sessionId);
      setNifProgressJson(turn.nif_progress_data_json || nifProgressJson);
      setMessages((prev) => [...prev, { role: "assistant", content: turn.response_markdown || "" }]);
    }
  }

  async function handleNewNifSession() {
    setBusy(true);
    setError(null);
    try {
      const result = await startNewNifSession({
        session_id: sessionId,
        submit_clicks: submitClicks,
      });
      setShowStarter(false);
      setShowLoadPanel(false);
      await runAutoChatFromAction(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start new NIF session.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadMode() {
    setShowLoadPanel(true);
    setError(null);
    await fetchStepActionsAndFiles();
  }

  async function handleLoadSelectedNif() {
    if (!selectedFile?.value) {
      setError("Please choose a saved NIF before loading.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await loadNifSession({
        session_id: sessionId,
        submit_clicks: submitClicks,
        filename: selectedFile.value,
      });
      setShowStarter(false);
      setShowLoadPanel(false);
      await runAutoChatFromAction(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load selected NIF.");
      setShowStarter(true);
      setShowLoadPanel(true);
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveNifProgress() {
    setActionBusy(true);
    setError(null);
    try {
      const result = await saveNifSession({
        filename: saveFilename,
        nif_progress_data_json: nifProgressJson,
      });

      const files = result.files || [];
      setSavedFiles(files);
      setSavedFilesMessage("");
      if (result.saved_filename) {
        const matching = files.find((item) => item.value === result.saved_filename) || null;
        setSelectedFile(matching);
      }
      if (result.message?.trim()) {
        appendStatus(result.message.trim());
      }
      setShowSaveDialog(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save NIF progress.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleRefreshPage() {
    setActionBusy(true);
    setError(null);
    try {
      setMessages([]);
      setShowStarter(true);
      setShowLoadPanel(false);
      setSelectedFile(null);
      await bootstrapStepPage();
      await fetchStepActionsAndFiles();
      appendStatus("NIF Step by Step refreshed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh NIF Step by Step.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleReloadNif() {
    setActionBusy(true);
    setError(null);
    try {
      const result = await reloadNifConfig({
        active_task_name: activeTaskName || "nifguide_task",
      });
      if (result.message?.trim()) {
        appendStatus(result.message.trim());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reload NIF rules.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleOpenShowProgress() {
    setError(null);
    setShowProgressDialog(true);
  }

  async function handleDownloadFile() {
    setActionBusy(true);
    setError(null);
    try {
      await downloadNifFile({
        filename: saveFilename,
        nif_progress_data_json: nifProgressJson,
      });
      appendStatus("NIF progress file downloaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download NIF file.");
    } finally {
      setActionBusy(false);
    }
  }

  async function submitMessageToAgent(rawMessage: string) {
    const messageToSend = String(rawMessage || "").trim();
    if (!messageToSend || isAnyBusy) {
      return;
    }

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
        active_task_name: activeTaskName || "nifguide_task",
      });

      setSessionId(turn.session_id || sessionId);
      setNifProgressJson(turn.nif_progress_data_json || nifProgressJson);
      setMessages((prev) => [...prev, { role: "assistant", content: turn.response_markdown || "" }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    if (!input.trim() || isAnyBusy) {
      return;
    }
    const messageToSend = input.trim();
    setInput("");
    await submitMessageToAgent(messageToSend);
  }

  async function handleSubmitInlineSelection() {
    if (!activeOptionPrompt || isAnyBusy) {
      return;
    }

    const payload = activeOptionPrompt.allowMulti
      ? inlineSelectedMulti.map((option) => option.id).join(", ")
      : (inlineSelectedSingle?.id || "");

    if (!payload.trim()) {
      setError(
        activeOptionPrompt.allowMulti
          ? "Select one or more options before submitting."
          : "Select an option before submitting.",
      );
      return;
    }

    await submitMessageToAgent(payload);
  }

  return (
    <Stack spacing={1.2} sx={{ height: "100%", minHeight: 0 }}>
      {statusEvents.length > 0 ? (
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          {statusEvents.map((evt, idx) => (
            <Chip key={`${evt}-${idx}`} label={evt} color="primary" variant="outlined" size="small" />
          ))}
        </Stack>
      ) : null}

      {error ? <Alert severity="error">{error}</Alert> : null}

      {showStarter ? (
        <Paper className="step-starter-card" elevation={0}>
          <Stack spacing={1.2}>
            <Typography variant="h6">Choose how to continue</Typography>
            <Typography variant="body2" color="text.secondary">
              Start a fresh NIF session or resume from a prior saved chat.
            </Typography>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <Button
                variant="contained"
                startIcon={<AddCircleOutlineRoundedIcon />}
                disabled={isAnyBusy}
                onClick={() => void handleNewNifSession()}
              >
                {actions.find((a) => a.id === "new")?.label || "New NIF chat session"}
              </Button>
              <Button
                variant="outlined"
                startIcon={<FolderOpenRoundedIcon />}
                disabled={isAnyBusy}
                onClick={() => void handleLoadMode()}
              >
                {actions.find((a) => a.id === "load")?.label || "Load NIF from previous chat"}
              </Button>
            </Stack>

            {showLoadPanel ? (
              <Paper className="step-load-panel" elevation={0}>
                <Stack spacing={1}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    Select a saved NIF
                  </Typography>

                  <Autocomplete
                    options={savedFiles}
                    value={selectedFile}
                    getOptionLabel={(option) => option.label}
                    onChange={(_event, value) => setSelectedFile(value)}
                    renderInput={(params) => <TextField {...params} size="small" placeholder="Search saved NIFs" />}
                    noOptionsText={savedFilesMessage || "No saved NIFs found."}
                  />

                  {savedFilesMessage ? (
                    <Typography variant="caption" color="text.secondary">{savedFilesMessage}</Typography>
                  ) : null}

                  <Stack direction="row" spacing={1}>
                    <Button variant="contained" disabled={loadDisabled} onClick={() => void handleLoadSelectedNif()}>
                      Load
                    </Button>
                    <Button
                      variant="text"
                      disabled={isAnyBusy}
                      onClick={() => {
                        setShowLoadPanel(false);
                        setSelectedFile(null);
                      }}
                    >
                      Cancel
                    </Button>
                  </Stack>
                </Stack>
              </Paper>
            ) : null}
          </Stack>
        </Paper>
      ) : null}

      <Paper className="chat-shell" elevation={0}>
        <Box className="chat-scroll" ref={chatScrollRef}>
          {messages.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              NIFTY is ready. Enter your next NIF step question.
            </Typography>
          ) : null}

          {messages.map((message, index) => (
            <Box
              key={`${message.role}-${index}`}
              className={`chat-message-row ${message.role === "user" ? "chat-message-row-user" : "chat-message-row-assistant"}`}
            >
              {message.role === "user" ? null : (
                <Avatar className="chat-avatar chat-avatar-bot">
                  <SmartToyRoundedIcon fontSize="small" />
                </Avatar>
              )}
              <Paper
                className={`chat-bubble ${message.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}`}
                elevation={0}
              >
                {message.role === "assistant" && activeOptionPrompt?.index === index ? (
                  <Stack spacing={0.8}>
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                      {activeOptionPrompt.promptText}
                    </Typography>

                    <TextField
                      size="small"
                      placeholder="Search options"
                      value={inlineOptionFilter}
                      onChange={(event) => setInlineOptionFilter(event.target.value)}
                      InputProps={{
                        startAdornment: (
                          <InputAdornment position="start">
                            <SearchRoundedIcon fontSize="small" />
                          </InputAdornment>
                        ),
                      }}
                    />

                    <Box className="inline-option-list">
                      {filteredInlineOptions.map((option) => {
                        const selected = isInlineOptionSelected(option.id);
                        return (
                          <ButtonBase
                            key={option.id}
                            className={`inline-option-item ${selected ? "inline-option-item-selected" : ""}`}
                            onClick={() => toggleInlineOption(option)}
                          >
                            {selected ? (
                              <CheckCircleRoundedIcon fontSize="small" className="inline-option-icon" />
                            ) : (
                              <CheckCircleOutlineRoundedIcon fontSize="small" className="inline-option-icon" />
                            )}
                            <Typography variant="caption" className="inline-option-id">
                              {option.id}.
                            </Typography>
                            <Typography variant="body2" className="inline-option-label">
                              {option.label}
                            </Typography>
                          </ButtonBase>
                        );
                      })}
                      {!filteredInlineOptions.length ? (
                        <Typography variant="caption" color="text.secondary" sx={{ px: 1, py: 0.6 }}>
                          No options matched your search.
                        </Typography>
                      ) : null}
                    </Box>

                    <Typography variant="caption" color="text.secondary">
                      {activeOptionPrompt.allowMulti
                        ? `${inlineSelectedMulti.length} option(s) selected`
                        : inlineSelectedSingle
                          ? `Selected option ${inlineSelectedSingle.id}`
                          : "No option selected"}
                    </Typography>

                    <Stack direction="row" justifyContent="flex-end">
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => void handleSubmitInlineSelection()}
                        disabled={
                          isAnyBusy
                          || (
                            activeOptionPrompt.allowMulti
                              ? inlineSelectedMulti.length === 0
                              : !inlineSelectedSingle
                          )
                        }
                      >
                        {activeOptionPrompt.allowMulti ? "Submit options" : "Submit option"}
                      </Button>
                    </Stack>
                  </Stack>
                ) : (
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                    {message.content}
                  </Typography>
                )}
              </Paper>
              {message.role === "user" ? (
                <Avatar className="chat-avatar chat-avatar-user">
                  <PersonRoundedIcon fontSize="small" />
                </Avatar>
              ) : null}
            </Box>
          ))}

          {busy ? (
            <Box className="typing-row">
              <CircularProgress size={14} />
              <Typography variant="caption" color="text.secondary">NIFTY is thinking...</Typography>
            </Box>
          ) : null}
        </Box>
      </Paper>

      <Stack spacing={0.7} className="step-action-bar">
        <Stack direction="row" spacing={1} alignItems="center" className="step-send-row">
          <TextField
            fullWidth
            size="small"
            placeholder="Type your message"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            disabled={isAnyBusy}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void onSubmit();
              }
            }}
          />

          <Button
            variant="contained"
            endIcon={busy ? <CircularProgress size={14} color="inherit" /> : <SendRoundedIcon />}
            onClick={() => void onSubmit()}
            disabled={isAnyBusy || !input.trim()}
          >
            Send
          </Button>
        </Stack>

        <Stack direction="row" spacing={1} alignItems="center" className="step-tools-row">
          <Tooltip title="Save NIF progress">
            <span>
              <IconButton className="step-action-icon" onClick={() => setShowSaveDialog(true)} disabled={isAnyBusy}>
                <SaveRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Show progress">
            <span>
              <IconButton className="step-action-icon" onClick={() => void handleOpenShowProgress()} disabled={isAnyBusy}>
                <VisibilityRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Reload NIF rules">
            <span>
              <IconButton className="step-action-icon" onClick={() => void handleReloadNif()} disabled={isAnyBusy}>
                <AutorenewRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Download file">
            <span>
              <IconButton className="step-action-icon" onClick={() => void handleDownloadFile()} disabled={isAnyBusy}>
                <DownloadRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Refresh page">
            <span>
              <IconButton className="step-action-icon" onClick={() => void handleRefreshPage()} disabled={isAnyBusy}>
                <RefreshRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>

      <Dialog open={showSaveDialog} onClose={() => setShowSaveDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>Save NIF progress</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            fullWidth
            label="Save as"
            placeholder="Enter name for this NIF in progress"
            value={saveFilename}
            onChange={(event) => setSaveFilename(event.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSaveDialog(false)} disabled={isAnyBusy}>Cancel</Button>
          <Button onClick={() => void handleSaveNifProgress()} variant="contained" disabled={saveDisabled}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <NifProgressGridDialog
        open={showProgressDialog}
        onClose={() => setShowProgressDialog(false)}
        nifProgressJson={nifProgressJson}
      />
    </Stack>
  );
}
