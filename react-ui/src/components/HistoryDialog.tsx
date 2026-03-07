import { faRobot, faUser, faTrashCan, faXmark } from "@fortawesome/free-solid-svg-icons";
import {
  Alert,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { clearHistory, fetchHistory } from "../api/client";
import FaIcon from "./FaIcon";
import type { HistoryMessage, HistoryRange } from "../types";

interface HistoryDialogProps {
  open: boolean;
  onClose: () => void;
  sessionId: string;
  setSessionId: (sid: string) => void;
  setNifProgressJson: (value: string) => void;
}

function formatTimestamp(value: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString();
}

function dateHeader(value: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "2-digit",
    year: "numeric",
  });
}

export default function HistoryDialog({
  open,
  onClose,
  sessionId,
  setSessionId,
  setNifProgressJson,
}: HistoryDialogProps) {
  const [range, setRange] = useState<HistoryRange>("current");
  const [messages, setMessages] = useState<HistoryMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [clearBusy, setClearBusy] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function loadHistory(): Promise<void> {
      if (!open || !sessionId) return;
      setLoading(true);
      setError("");
      setStatusMessage("");
      try {
        const result = await fetchHistory({
          session_id: sessionId,
          range,
        });
        if (cancelled) return;
        setMessages(result.messages || []);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load history.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [open, range, sessionId]);

  const groupedRows = useMemo(() => {
    const rows: Array<{ type: "date"; value: string } | { type: "msg"; value: HistoryMessage }> = [];
    let lastHeader = "";
    for (const msg of messages) {
      const header = dateHeader(msg.timestamp_utc);
      if (header && header !== lastHeader) {
        rows.push({ type: "date", value: header });
        lastHeader = header;
      }
      rows.push({ type: "msg", value: msg });
    }
    return rows;
  }, [messages]);

  async function handleClearHistory(): Promise<void> {
    setClearBusy(true);
    setError("");
    try {
      const result = await clearHistory({ session_id: sessionId });
      setStatusMessage(result.message || "Chat history has been cleared successfully!");
      setMessages([]);
      if (result.session_id) setSessionId(result.session_id);
      if (result.nif_progress_data_json) setNifProgressJson(result.nif_progress_data_json);
      setClearConfirmOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear history.");
    } finally {
      setClearBusy(false);
    }
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              Chat History
            </Typography>
            <Tooltip title="Close history">
              <IconButton size="small" onClick={onClose} aria-label="Close history">
                <FaIcon icon={faXmark} />
              </IconButton>
            </Tooltip>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={1.2}>
            <Stack direction="row" spacing={1}>
              <Button
                variant={range === "current" ? "contained" : "outlined"}
                size="small"
                onClick={() => setRange("current")}
              >
                Current
              </Button>
              <Button
                variant={range === "past_30_days" ? "contained" : "outlined"}
                size="small"
                onClick={() => setRange("past_30_days")}
              >
                Past 30 days
              </Button>
            </Stack>

            {statusMessage ? <Alert severity="success">{statusMessage}</Alert> : null}
            {error ? <Alert severity="error">{error}</Alert> : null}

            <Paper className="history-chat-shell" elevation={0}>
              <Box className="history-chat-scroll">
                {loading ? (
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ p: 1.2 }}>
                    <CircularProgress size={18} />
                    <Typography variant="body2">Loading history...</Typography>
                  </Stack>
                ) : null}

                {!loading && groupedRows.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ p: 1.2 }}>
                    There is no chat history yet.
                  </Typography>
                ) : null}

                {!loading &&
                  groupedRows.map((row, idx) => {
                    if (row.type === "date") {
                      return (
                        <Typography key={`date-${idx}`} variant="caption" className="history-date-header">
                          {row.value}
                        </Typography>
                      );
                    }
                    const msg = row.value;
                    const isUser = msg.role === "user";
                    return (
                      <Box
                        key={msg.id || `msg-${idx}`}
                        className={`chat-message-row ${isUser ? "chat-message-row-user" : "chat-message-row-assistant"}`}
                      >
                        {!isUser ? (
                          <Avatar className="chat-avatar chat-avatar-bot">
                            <FaIcon icon={faRobot} />
                          </Avatar>
                        ) : null}
                        <Paper className={`chat-bubble ${isUser ? "chat-bubble-user" : "chat-bubble-assistant"}`} elevation={0}>
                          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.4 }}>
                            {isUser ? "USER" : "NIFTY"} {formatTimestamp(msg.timestamp_utc)}
                          </Typography>
                          <Box className="chat-markdown">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                          </Box>
                        </Paper>
                        {isUser ? (
                          <Avatar className="chat-avatar chat-avatar-user">
                            <FaIcon icon={faUser} />
                          </Avatar>
                        ) : null}
                      </Box>
                    );
                  })}
              </Box>
            </Paper>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            color="error"
            startIcon={<FaIcon icon={faTrashCan} />}
            onClick={() => setClearConfirmOpen(true)}
          >
            Clear History
          </Button>
          <Box sx={{ flex: 1 }} />
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={clearConfirmOpen} onClose={() => setClearConfirmOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Confirm History Clear</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2">
            Would you like to remove all chat history associated with this user and all saved NIF files?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setClearConfirmOpen(false)} disabled={clearBusy}>
            Cancel
          </Button>
          <Button color="error" onClick={handleClearHistory} disabled={clearBusy}>
            {clearBusy ? "Clearing..." : "Yes, Clear History"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
