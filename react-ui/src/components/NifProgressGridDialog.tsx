import FilterAltOutlinedIcon from "@mui/icons-material/FilterAltOutlined";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TablePagination,
  Tooltip,
  Typography,
} from "@mui/material";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import { useEffect, useMemo, useState } from "react";

import { fetchNifProgressPreview } from "../api/client";
import FilterBuilderDialog from "./FilterBuilderDialog";
import type { ColumnType, FilterState } from "../filtering";
import {
  EMPTY_FILTER_STATE,
  evaluateFilterCondition,
} from "../filtering";

interface NifProgressGridDialogProps {
  open: boolean;
  onClose: () => void;
  nifProgressJson: string;
}

interface ProgressRow {
  id: number;
  field: string;
  value: string;
}

function parseProgressPreviewText(text: string): ProgressRow[] {
  const rows: ProgressRow[] = [];
  const lines = String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  let id = 1;
  for (const line of lines) {
    const idx = line.indexOf(":");
    if (idx <= 0) {
      continue;
    }
    const field = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (!field) {
      continue;
    }
    rows.push({ id, field, value });
    id += 1;
  }
  return rows;
}

function stringifyCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value) && value.length === 1) {
    return stringifyCellValue(value[0]);
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function buildProgressRows(progressJson: string): ProgressRow[] {
  if (!progressJson?.trim()) {
    return [];
  }

  try {
    const parsed = JSON.parse(progressJson) as {
      columns?: string[];
      data?: unknown[][];
    };
    const columns = Array.isArray(parsed.columns) ? parsed.columns : [];
    const row = Array.isArray(parsed.data) && parsed.data.length > 0 && Array.isArray(parsed.data[0])
      ? parsed.data[0]
      : [];

    const rows: ProgressRow[] = [];
    let id = 1;
    for (let i = 0; i < columns.length; i += 1) {
      const column = String(columns[i] ?? "").trim();
      if (!column || column.startsWith("_agentref_")) {
        continue;
      }
      rows.push({
        id,
        field: column,
        value: stringifyCellValue(row[i]),
      });
      id += 1;
    }
    return rows;
  } catch {
    return [];
  }
}

export default function NifProgressGridDialog({ open, onClose, nifProgressJson }: NifProgressGridDialogProps) {
  const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 25 });
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [filterState, setFilterState] = useState<FilterState>(EMPTY_FILTER_STATE);
  const [loadingRows, setLoadingRows] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rows, setRows] = useState<ProgressRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    if (!open) {
      return () => {
        cancelled = true;
      };
    }

    async function loadRows() {
      setLoadingRows(true);
      setLoadError(null);

      try {
        const preview = await fetchNifProgressPreview({
          nif_progress_data_json: nifProgressJson,
        });
        if (cancelled) {
          return;
        }
        const parsedRows = parseProgressPreviewText(preview.progress_text || "");
        if (parsedRows.length > 0) {
          setRows(parsedRows);
          setLoadingRows(false);
          return;
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load progress data.");
        }
      }

      if (!cancelled) {
        // Fallback to local parser if preview endpoint yields no rows.
        setRows(buildProgressRows(nifProgressJson));
      }
      if (!cancelled) {
        setLoadingRows(false);
      }
    }

    void loadRows();
    return () => {
      cancelled = true;
    };
  }, [open, nifProgressJson]);

  const columnProfiles = useMemo<Record<string, { type: ColumnType; suggestions: string[] }>>(() => {
    const fieldSuggestions = Array.from(new Set(rows.map((row) => row.field))).slice(0, 300);
    const valueSuggestions = Array.from(new Set(rows.map((row) => row.value).filter(Boolean))).slice(0, 300);
    return {
      field: { type: "text", suggestions: fieldSuggestions },
      value: { type: "text", suggestions: valueSuggestions },
    };
  }, [rows]);

  const filterFields = useMemo(
    () => [
      {
        key: "field",
        label: "Field",
        type: columnProfiles.field.type,
        suggestions: columnProfiles.field.suggestions,
      },
      {
        key: "value",
        label: "Value",
        type: columnProfiles.value.type,
        suggestions: columnProfiles.value.suggestions,
      },
    ],
    [columnProfiles],
  );

  const filteredRows = useMemo(() => {
    if (!filterState.conditions.length) {
      return rows;
    }
    return rows.filter((row) => {
      const matches = filterState.conditions.map((condition) => {
        const profile = columnProfiles[condition.column as "field" | "value"];
        if (!profile) {
          return true;
        }
        return evaluateFilterCondition(row[condition.column as "field" | "value"], condition, profile.type);
      });
      return filterState.joinMode === "and" ? matches.every(Boolean) : matches.some(Boolean);
    });
  }, [columnProfiles, filterState.conditions, filterState.joinMode, rows]);

  useEffect(() => {
    setPaginationModel((prev) => ({ ...prev, page: 0 }));
  }, [filteredRows.length]);

  useEffect(() => {
    if (!open) {
      setFilterDialogOpen(false);
      setLoadError(null);
    }
  }, [open]);

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: "field",
        headerName: "Field",
        minWidth: 340,
        flex: 1,
      },
      {
        field: "value",
        headerName: "Value",
        minWidth: 380,
        flex: 1,
      },
    ],
    [],
  );

  const openFilterDialog = () => {
    if (!rows.length) {
      return;
    }
    setFilterDialogOpen(true);
  };

  const clearFilters = () => {
    setFilterState(EMPTY_FILTER_STATE);
    setFilterDialogOpen(false);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>NIF Progress</DialogTitle>
      <DialogContent dividers sx={{ pb: 0 }}>
        {loadError ? (
          <Alert severity="warning" sx={{ mb: 1.2 }}>
            {loadError}
          </Alert>
        ) : null}

        <Stack
          direction={{ xs: "column", md: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", md: "center" }}
          spacing={1}
          sx={{ pb: 1.2 }}
        >
          <Typography variant="body2" color="text.secondary">
            Record count: {filteredRows.length}
            {filterState.conditions.length ? ` (filtered from ${rows.length})` : ""}
          </Typography>

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
                color="primary"
                onClick={openFilterDialog}
                disabled={!rows.length}
                sx={{ minWidth: 40, width: 40, px: 0 }}
                aria-label="Open filters"
              >
                <FilterAltOutlinedIcon fontSize="small" />
              </Button>
            </span>
          </Tooltip>
        </Stack>

        <Divider sx={{ mb: 1 }} />

        <Box sx={{ width: "100%", height: 500 }}>
          {loadingRows ? (
            <Stack
              alignItems="center"
              justifyContent="center"
              sx={{ height: "100%" }}
              spacing={1}
            >
              <CircularProgress size={20} />
              <Typography variant="body2" color="text.secondary">
                Loading progress...
              </Typography>
            </Stack>
          ) : (
            <DataGrid
              rows={filteredRows}
              columns={columns}
              pagination
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
              pageSizeOptions={[10, 25, 50, 100]}
              disableRowSelectionOnClick
              hideFooter
              density="compact"
              sx={{
                width: "100%",
                border: "none",
                "& .MuiDataGrid-cell": {
                  borderColor: "rgba(15, 23, 42, 0.08)",
                },
              }}
            />
          )}
        </Box>

        <Divider />

        <TablePagination
          component="div"
          count={filteredRows.length}
          page={paginationModel.page}
          onPageChange={(_event, newPage) => {
            setPaginationModel((prev) => ({ ...prev, page: newPage }));
          }}
          rowsPerPage={paginationModel.pageSize}
          onRowsPerPageChange={(event) => {
            const nextPageSize = Number.parseInt(event.target.value, 10);
            setPaginationModel({ page: 0, pageSize: nextPageSize });
          }}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} variant="contained">Close</Button>
      </DialogActions>

      <FilterBuilderDialog
        open={filterDialogOpen}
        title="Filter NIF Progress"
        fields={filterFields}
        initialState={filterState}
        onClose={() => setFilterDialogOpen(false)}
        onApply={(nextState) => {
          setFilterState(nextState);
        }}
        onClear={clearFilters}
      />
    </Dialog>
  );
}
