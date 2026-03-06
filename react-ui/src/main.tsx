import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./styles.css";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#8401FF" },
    secondary: { main: "#0f2548" },
    background: { default: "#f8f9fa", paper: "#ffffff" },
    text: { primary: "#000000", secondary: "#444444" },
  },
  typography: {
    fontFamily: '"Gilroy", "Segoe UI", sans-serif',
    h6: { fontWeight: 700, letterSpacing: "0.01em", fontSize: "1.05rem" },
    subtitle1: { fontSize: "0.9rem" },
    subtitle2: { fontSize: "0.82rem" },
    body1: { fontSize: "0.84rem", lineHeight: 1.35 },
    body2: { fontSize: "0.8rem", lineHeight: 1.35 },
    caption: { fontSize: "0.75rem" },
    button: { textTransform: "none", fontWeight: 700, fontSize: "0.78rem" },
  },
  shape: { borderRadius: 10 },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
);
