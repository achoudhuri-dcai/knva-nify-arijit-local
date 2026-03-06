import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import FilterAltOutlinedIcon from "@mui/icons-material/FilterAltOutlined";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import KeyboardArrowUpRoundedIcon from "@mui/icons-material/KeyboardArrowUpRounded";
import {
  Alert,
  Box,
  Button,
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
import { DataGrid, type GridColDef, type GridPaginationModel } from "@mui/x-data-grid";
import { useEffect, useMemo, useState } from "react";
import * as XLSX from "xlsx";

import type { ColumnType, FilterState } from "../filtering";
import {
  EMPTY_FILTER_STATE,
  evaluateFilterCondition,
  inferColumnType,
} from "../filtering";
import FilterBuilderDialog from "./FilterBuilderDialog";

interface NifSearchQueryPanelProps {
  queryResult: Record<string, unknown> | null;
  responseMarkdown: string;
  promptPayload: Record<string, unknown> | null;
}

interface QueryResultNormalized {
  sql: string;
  rowCount: number;
  displayedRowCount: number;
  truncated: boolean;
  error: string;
  columns: string[];
  rows: Array<Record<string, unknown>>;
}

function parseNumberLike(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function parseSqlFromMarkdown(markdown: string): string {
  const text = String(markdown || "");
  const match = text.match(/```sql\s*([\s\S]*?)```/i);
  if (!match || !match[1]) {
    return "";
  }
  return String(match[1]).trim();
}

function toExportCell(value: unknown): unknown {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return value;
}

function createExportFilename(hasFilters: boolean): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  return `nif_output_data_explorer_${hasFilters ? "filtered" : "all"}_${stamp}.xlsx`;
}

function normalizeQueryResult(
  queryResult: Record<string, unknown> | null,
  responseMarkdown: string,
): QueryResultNormalized {
  const payload = queryResult && typeof queryResult === "object" ? queryResult : {};

  const rowsRaw = Array.isArray(payload.rows) ? payload.rows : [];
  const rows = rowsRaw
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)));

  let columns = Array.isArray(payload.columns)
    ? payload.columns.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (!columns.length && rows.length) {
    columns = Object.keys(rows[0]);
  }

  const sqlFromPayload = String(payload.sql || "").trim();

  return {
    sql: sqlFromPayload || parseSqlFromMarkdown(responseMarkdown),
    rowCount: parseNumberLike(payload.row_count, rows.length),
    displayedRowCount: parseNumberLike(payload.displayed_row_count, rows.length),
    truncated: Boolean(payload.truncated),
    error: String(payload.error || "").trim(),
    columns,
    rows,
  };
}

export default function NifSearchQueryPanel({
  queryResult,
  responseMarkdown,
  promptPayload,
}: NifSearchQueryPanelProps) {
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [promptDialogOpen, setPromptDialogOpen] = useState(false);
  const [filterState, setFilterState] = useState<FilterState>(EMPTY_FILTER_STATE);
  const [showSql, setShowSql] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });

  const normalized = useMemo(
    () => normalizeQueryResult(queryResult, responseMarkdown),
    [queryResult, responseMarkdown],
  );
  const hasPromptPayload = Boolean(promptPayload && typeof promptPayload === "object");
  const formattedPrompt = useMemo(() => {
    if (!hasPromptPayload || !promptPayload) {
      return "No prompt payload is available for this turn.";
    }

    const capturedAt = String(promptPayload.captured_at || "").trim();
    const sessionId = String(promptPayload.session_id || "").trim();
    const systemPrompt = String(promptPayload.system_prompt || "").trim() || "(System prompt not available for this run.)";
    const userPrompt = String(promptPayload.user_prompt || "").trim() || "(User prompt was empty.)";

    const headerLines: string[] = [];
    if (capturedAt) {
      headerLines.push(`Captured at: ${capturedAt}`);
    }
    if (sessionId) {
      headerLines.push(`Session ID: ${sessionId}`);
    }

    const header = headerLines.length ? `${headerLines.join("\n")}\n\n` : "";
    return `${header}=== SYSTEM PROMPT ===\n${systemPrompt}\n\n=== USER PROMPT ===\n${userPrompt}\n`;
  }, [hasPromptPayload, promptPayload]);

  useEffect(() => {
    setFilterState(EMPTY_FILTER_STATE);
    setPaginationModel({ page: 0, pageSize: 25 });
    setShowSql(false);
  }, [normalized.sql, normalized.rowCount, normalized.displayedRowCount]);

  const columnProfiles = useMemo<Record<string, { type: ColumnType; suggestions: string[] }>>(() => {
    const profiles: Record<string, { type: ColumnType; suggestions: string[] }> = {};
    for (const column of normalized.columns) {
      const values = normalized.rows.map((row) => row[column]);
      const suggestions = Array.from(
        new Set(
          values
            .map((value) => {
              if (value === null || value === undefined) {
                return "";
              }
              if (typeof value === "object") {
                try {
                  return JSON.stringify(value);
                } catch {
                  return String(value);
                }
              }
              return String(value);
            })
            .filter(Boolean),
        ),
      ).slice(0, 300);

      profiles[column] = {
        type: inferColumnType(values),
        suggestions,
      };
    }
    return profiles;
  }, [normalized.columns, normalized.rows]);

  const filterFields = useMemo(
    () =>
      normalized.columns.map((column) => ({
        key: column,
        label: column,
        type: columnProfiles[column]?.type ?? "text",
        suggestions: columnProfiles[column]?.suggestions ?? [],
      })),
    [columnProfiles, normalized.columns],
  );

  const filteredRows = useMemo(() => {
    if (!filterState.conditions.length) {
      return normalized.rows;
    }
    return normalized.rows.filter((row) => {
      const matches = filterState.conditions.map((condition) => {
        const profile = columnProfiles[condition.column];
        if (!profile) {
          return true;
        }
        return evaluateFilterCondition(row[condition.column], condition, profile.type);
      });
      return filterState.joinMode === "and" ? matches.every(Boolean) : matches.some(Boolean);
    });
  }, [columnProfiles, filterState.conditions, filterState.joinMode, normalized.rows]);

  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [filteredRows.length]);

  const gridColumns = useMemo<GridColDef[]>(
    () =>
      normalized.columns.map((column) => ({
        field: column,
        headerName: column,
        minWidth: 220,
        flex: 1,
        valueGetter: (_value, row) => {
          const rowValue = row[column];
          if (rowValue === null || rowValue === undefined) {
            return "";
          }
          if (typeof rowValue === "object") {
            try {
              return JSON.stringify(rowValue);
            } catch {
              return String(rowValue);
            }
          }
          return String(rowValue);
        },
        renderCell: (params) => {
          const cellText = String(params.value ?? "");
          return (
            <Box
              sx={{
                whiteSpace: "normal",
                wordBreak: "break-word",
                lineHeight: 1.35,
                py: 0.5,
              }}
            >
              {cellText}
            </Box>
          );
        },
      })),
    [normalized.columns],
  );

  const gridRows = useMemo(
    () =>
      filteredRows.map((row, index) => ({
        id: (row.id as string | number | undefined) ?? `${index + 1}`,
        ...row,
      })),
    [filteredRows],
  );

  const exportRows = useMemo(
    () =>
      filteredRows.map((row) => {
        const shaped: Record<string, unknown> = {};
        for (const column of normalized.columns) {
          shaped[column] = toExportCell(row[column]);
        }
        return shaped;
      }),
    [filteredRows, normalized.columns],
  );

  function downloadExcel(): void {
    if (!normalized.columns.length) {
      return;
    }

    const worksheet = exportRows.length
      ? XLSX.utils.json_to_sheet(exportRows, { header: normalized.columns })
      : XLSX.utils.aoa_to_sheet([normalized.columns]);

    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Output Data Explorer");

    const data = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = createExportFilename(filterState.conditions.length > 0);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  const shouldRenderPanel = Boolean(
    normalized.rows.length || normalized.sql || normalized.error,
  );
  if (!shouldRenderPanel) {
    return null;
  }

  return (
    <Paper className={`sql-query-panel ${collapsed ? "sql-query-panel-collapsed" : ""}`} elevation={0}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", sm: "center" }}
        spacing={1}
        sx={{ px: 1.2, pt: 1.2 }}
      >
        <Stack spacing={0.2}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Output Data Explorer
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Rows: {filteredRows.length}
            {filterState.conditions.length ? ` (filtered from ${normalized.rows.length})` : ""}
            {normalized.truncated ? ` | Showing first ${normalized.displayedRowCount} of ${normalized.rowCount}` : ""}
          </Typography>
        </Stack>

        <Stack direction="row" spacing={0.5} alignItems="center">
          {!collapsed ? (
            <>
              <Tooltip
                title={
                  filterState.conditions.length
                    ? `Filters (${filterState.conditions.length})`
                    : "Filters"
                }
              >
                <span>
                  <Button
                    variant={filterState.conditions.length ? "contained" : "outlined"}
                    onClick={() => setFilterDialogOpen(true)}
                    disabled={!normalized.rows.length}
                    sx={{ minWidth: 40, width: 40, px: 0 }}
                    aria-label="Open filters"
                  >
                    <FilterAltOutlinedIcon fontSize="small" />
                  </Button>
                </span>
              </Tooltip>

              <Tooltip
                title={
                  filterState.conditions.length
                    ? "Download filtered rows to Excel"
                    : "Download all rows to Excel"
                }
              >
                <span>
                  <Button
                    variant="outlined"
                    onClick={downloadExcel}
                    disabled={!normalized.columns.length}
                    sx={{ minWidth: 40, width: 40, px: 0 }}
                    aria-label="Download Excel"
                  >
                    <DownloadRoundedIcon fontSize="small" />
                  </Button>
                </span>
              </Tooltip>

              <Button
                variant="outlined"
                size="small"
                onClick={() => setShowSql((prev) => !prev)}
                disabled={!normalized.sql}
              >
                {showSql ? "Hide SQL" : "Show SQL"}
              </Button>

              <Button
                variant="outlined"
                size="small"
                onClick={() => setPromptDialogOpen(true)}
                disabled={!hasPromptPayload}
              >
                Show Prompt
              </Button>
            </>
          ) : null}

          <Tooltip title={collapsed ? "Expand Output Data Explorer" : "Collapse Output Data Explorer"}>
            <IconButton
              size="small"
              onClick={() => setCollapsed((prev) => !prev)}
              aria-label={collapsed ? "Expand output data explorer" : "Collapse output data explorer"}
              sx={{
                border: "1px solid var(--panel-border)",
                borderRadius: 1,
                color: "text.secondary",
              }}
            >
              {collapsed ? <KeyboardArrowDownRoundedIcon fontSize="small" /> : <KeyboardArrowUpRoundedIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>

      {!collapsed && normalized.error ? (
        <Alert severity="warning" sx={{ mx: 1.2, mt: 1 }}>
          {normalized.error}
        </Alert>
      ) : null}

      {!collapsed && showSql && normalized.sql ? (
        <Box
          component="pre"
          sx={{
            mx: 1.2,
            mt: 1,
            p: 1,
            borderRadius: 1,
            border: "1px solid rgba(15, 23, 42, 0.12)",
            background: "rgba(15, 23, 42, 0.04)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontSize: "12px",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          }}
        >
          {normalized.sql}
        </Box>
      ) : null}

      {!collapsed ? (
        <Box className="sql-grid-resizer" sx={{ px: 1.2, pb: 1.2, pt: 1 }}>
          <DataGrid
            rows={gridRows}
            columns={gridColumns}
            pagination
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            pageSizeOptions={[25, 50, 100]}
            getRowHeight={() => "auto"}
            disableRowSelectionOnClick
            density="compact"
            sx={{
              width: "100%",
              height: "100%",
              maxWidth: "100%",
              border: "1px solid rgba(15, 23, 42, 0.08)",
              "& .MuiDataGrid-cell": {
                borderColor: "rgba(15, 23, 42, 0.08)",
                alignItems: "flex-start",
              },
              "& .MuiDataGrid-main, & .MuiDataGrid-virtualScroller, & .MuiDataGrid-virtualScrollerContent": {
                overflowX: "auto !important",
                overflowY: "auto !important",
              },
            }}
          />
        </Box>
      ) : null}

      <FilterBuilderDialog
        open={filterDialogOpen}
        title="Filter Output Data Explorer"
        fields={filterFields}
        initialState={filterState}
        onClose={() => setFilterDialogOpen(false)}
        onApply={(nextState) => {
          setFilterState(nextState);
          setFilterDialogOpen(false);
        }}
        onClear={() => {
          setFilterState(EMPTY_FILTER_STATE);
          setFilterDialogOpen(false);
        }}
      />

      <Dialog
        open={promptDialogOpen}
        onClose={() => setPromptDialogOpen(false)}
        fullWidth
        maxWidth="lg"
      >
        <DialogTitle>NIFDatabaseAgent Prompt</DialogTitle>
        <DialogContent dividers sx={{ maxHeight: "70vh", overflowY: "auto" }}>
          <Box
            component="pre"
            sx={{
              m: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: "12px",
              lineHeight: 1.45,
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            }}
          >
            {formattedPrompt}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button variant="contained" onClick={() => setPromptDialogOpen(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
