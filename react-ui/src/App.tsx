import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SchoolRoundedIcon from "@mui/icons-material/SchoolRounded";
import ChecklistRoundedIcon from "@mui/icons-material/ChecklistRounded";
import QuizRoundedIcon from "@mui/icons-material/QuizRounded";
import DarkModeRoundedIcon from "@mui/icons-material/DarkModeRounded";
import LightModeRoundedIcon from "@mui/icons-material/LightModeRounded";
import MenuOpenRoundedIcon from "@mui/icons-material/MenuOpenRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import { Box, Button, IconButton, Paper, Stack, Tooltip, Typography } from "@mui/material";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { createSession, fetchHealthLive } from "./api/client";
import ChatModulePage from "./components/ChatModulePage";
import NifStepSessionPage from "./components/NifStepSessionPage";
import type { ModuleConfig } from "./types";

const MODULES: ModuleConfig[] = [
  {
    key: "training",
    label: "Get started On New training resources",
    path: "/training-resources",
    selectedQuestion: "Get started on training resources",
  },
  {
    key: "step",
    label: "NIF Step by Step",
    path: "/nif-step-by-step",
    selectedQuestion: "NIF step by step",
  },
  {
    key: "search",
    label: "Search NIF",
    path: "/search-nif",
    selectedQuestion: "Search NIF",
  },
  {
    key: "field",
    label: "NIF Field question",
    path: "/nif-field-question",
    selectedQuestion: "NIF field question",
  },
];

const SESSION_KEY = "nifty_react_session_id";
const LLM_HEADER_KEY = "nifty_react_llm_header_text";
const THEME_KEY = "nifty_react_theme_mode";
const DCAI_HOME_URL = "https://www.demandchainai.com/";
const TERMS_OF_USE_URL = "https://www.demandchainai.com/demandchain-home-page/dcai-terms-of-use-policy/";
const LEGAL_FOOTER_TEXT = "This Chatbot can be used to query data from the Kellanova Nifty database. Always review the accuracy of the Chatbot responses as they may be incorrect. All content copyright ©2025 Demand Chain AI Inc. All rights reserved. No reproduction, transmission or display is permitted without the written permission of Demand Chain AI Inc.";

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [submitClicks, setSubmitClicks] = useState(0);
  const [nifProgressJson, setNifProgressJson] = useState('{"columns":[],"index":[0],"data":[[]]}');
  const [activeTaskName, setActiveTaskName] = useState("nifguide_task");
  const [llmHeaderText, setLlmHeaderText] = useState<string>(() => (
    window.localStorage.getItem(LLM_HEADER_KEY) || "LLM: loading"
  ));
  const [isNavExpanded, setIsNavExpanded] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    return stored === "dark";
  });

  useEffect(() => {
    let cancelled = false;

    async function bootstrapSession() {
      let resolvedLlmHeader = "";
      const cached = window.localStorage.getItem(SESSION_KEY);
      if (cached) {
        setSessionId(cached);
      } else {
        const session = await createSession();
        if (cancelled) {
          return;
        }
        setSessionId(session.session_id);
        setActiveTaskName(session.active_task_name || "nifguide_task");
        setNifProgressJson(session.nif_progress_data_json || '{"columns":[],"index":[0],"data":[[]]}');
        window.localStorage.setItem(SESSION_KEY, session.session_id);
        resolvedLlmHeader = String(session.llm_header_text || "").trim();
      }

      if (!resolvedLlmHeader) {
        resolvedLlmHeader = String(window.localStorage.getItem(LLM_HEADER_KEY) || "").trim();
      }

      if (!resolvedLlmHeader) {
        try {
          const health = await fetchHealthLive();
          if (!cancelled) {
            resolvedLlmHeader = String(health.llm_header_text || "").trim();
          }
        } catch {
          // Best effort only; keep default text if health endpoint is unavailable.
        }
      }

      if (cancelled) {
        return;
      }

      if (resolvedLlmHeader) {
        setLlmHeaderText(resolvedLlmHeader);
        window.localStorage.setItem(LLM_HEADER_KEY, resolvedLlmHeader);
      }
    }

    void bootstrapSession();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (sessionId) {
      window.localStorage.setItem(SESSION_KEY, sessionId);
    }
  }, [sessionId]);

  useEffect(() => {
    window.localStorage.setItem(THEME_KEY, isDarkMode ? "dark" : "light");
    document.body.classList.toggle("theme-dark", isDarkMode);
  }, [isDarkMode]);

  const routes = useMemo(() => MODULES.map((module) => (
    <Route
      key={module.key}
      path={module.path}
      element={(
        module.key === "step" ? (
          <NifStepSessionPage
            module={module}
            sessionId={sessionId}
            setSessionId={setSessionId}
            submitClicks={submitClicks}
            setSubmitClicks={setSubmitClicks}
            nifProgressJson={nifProgressJson}
            setNifProgressJson={setNifProgressJson}
            activeTaskName={activeTaskName}
            setActiveTaskName={setActiveTaskName}
          />
        ) : (
          <ChatModulePage
            module={module}
            sessionId={sessionId}
            setSessionId={setSessionId}
            submitClicks={submitClicks}
            setSubmitClicks={setSubmitClicks}
            nifProgressJson={nifProgressJson}
            setNifProgressJson={setNifProgressJson}
            activeTaskName={activeTaskName}
            setActiveTaskName={setActiveTaskName}
          />
        )
      )}
    />
  )), [activeTaskName, nifProgressJson, sessionId, submitClicks]);

  return (
    <Box className="app-shell">
      <Box className="ambient-shape ambient-shape-a" />
      <Box className="ambient-shape ambient-shape-b" />

      <Paper className="app-header" elevation={0}>
        <Stack spacing={0.1} className="header-brand">
          <img src="/kellanova-logo.svg" alt="Kellanova" className="header-logo" />
          <Typography component="div" className="header-title">
            New Item Form Assistant
          </Typography>
        </Stack>
        <Stack spacing={0.2} alignItems="flex-end" className="header-meta">
          <a href={DCAI_HOME_URL} target="_blank" rel="noreferrer" className="header-powered-link">
            <Typography component="span" variant="caption" color="text.secondary" className="header-powered-text">
              built and powered by
            </Typography>
            <img src="/dcai-horizontal-darkblue.png" alt="Demand Chain AI" className="header-dcai-logo header-dcai-logo-light" />
            <img src="/dcai-horizontal-whiteblue.png" alt="Demand Chain AI" className="header-dcai-logo header-dcai-logo-dark" />
          </a>
          <Stack spacing={0.1} alignItems="flex-end">
            <Stack direction="row" spacing={0.6} alignItems="center">
              <Typography variant="caption" color="text.secondary">
                Session: {sessionId || "loading"}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {llmHeaderText}
            </Typography>
          </Stack>
        </Stack>
      </Paper>

      <Box className="app-layout">
        <Paper className={`side-nav ${isNavExpanded ? "side-nav-expanded" : "side-nav-collapsed"}`} elevation={0}>
          <Stack spacing={1} width="100%" height="100%" className="side-nav-content">
            <Stack direction="row" alignItems="center" justifyContent={isNavExpanded ? "space-between" : "center"}>
              {isNavExpanded ? (
                <Typography variant="caption" sx={{ textAlign: "left", fontWeight: 700, color: "text.secondary" }}>
                  Modules
                </Typography>
              ) : null}
              <Tooltip title={isNavExpanded ? "Collapse menu" : "Expand menu"}>
                <IconButton
                  size="small"
                  className="side-nav-toggle"
                  onClick={() => setIsNavExpanded((prev) => !prev)}
                  aria-label={isNavExpanded ? "Collapse menu" : "Expand menu"}
                >
                  {isNavExpanded ? <MenuOpenRoundedIcon fontSize="small" /> : <MenuRoundedIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
            </Stack>
            <Box className="side-nav-menu-list">
              {MODULES.map((module) => {
                const icon = module.key === "training"
                  ? <SchoolRoundedIcon fontSize="small" />
                  : module.key === "step"
                    ? <ChecklistRoundedIcon fontSize="small" />
                    : module.key === "search"
                      ? <SearchRoundedIcon fontSize="small" />
                      : <QuizRoundedIcon fontSize="small" />;

                return (
                  <Button
                    key={module.key}
                    className="side-nav-btn"
                    component={NavLink}
                    to={module.path}
                    title={module.label}
                    startIcon={icon}
                    aria-label={module.label}
                    sx={{
                      justifyContent: isNavExpanded ? "flex-start" : "center",
                      textTransform: "none",
                      fontSize: "0.76rem",
                      lineHeight: 1.2,
                      minWidth: 0,
                    }}
                  >
                    {isNavExpanded ? module.label : null}
                  </Button>
                );
              })}
            </Box>
          </Stack>
          <Box className="side-nav-theme-slot">
            <Tooltip title={isDarkMode ? "Switch to day mode" : "Switch to dark mode"}>
              <IconButton
                size="small"
                className="theme-toggle-btn side-nav-theme-btn"
                onClick={() => setIsDarkMode((prev) => !prev)}
                aria-label={isDarkMode ? "Switch to day mode" : "Switch to dark mode"}
              >
                {isDarkMode ? <LightModeRoundedIcon fontSize="small" /> : <DarkModeRoundedIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>
        </Paper>

        <Box className="main-pane">
          <Box className="workspace">
            <Routes>
              <Route path="/" element={<Navigate to={MODULES[0].path} replace />} />
              {routes}
              <Route path="*" element={<Navigate to={MODULES[0].path} replace />} />
            </Routes>
          </Box>
        </Box>
      </Box>

      <Paper component="footer" className="app-footer-mini" elevation={0}>
        <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="center" className="app-footer-mini-content">
          <Typography component="p" variant="caption" color="text.secondary" className="app-footer-mini-text">
            {LEGAL_FOOTER_TEXT}
          </Typography>
          <Typography component="span" className="app-footer-mini-sep">
            |
          </Typography>
          <Typography
            component="a"
            variant="caption"
            href={TERMS_OF_USE_URL}
            target="_blank"
            rel="noreferrer"
            className="app-footer-mini-link"
          >
            Terms of Use Policy
          </Typography>
        </Stack>
      </Paper>
    </Box>
  );
}
