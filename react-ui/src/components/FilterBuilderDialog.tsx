import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import ClearAllOutlinedIcon from "@mui/icons-material/ClearAllOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";

import type {
  FilterCondition,
  FilterFieldOption,
  FilterState,
  FilterOperator,
  FilterOperatorOption,
} from "../filtering";
import {
  createFilterCondition,
  defaultOperatorForType,
  isConditionComplete,
  isMultiValueOperator,
  operatorOptionsForType,
  requiresSecondaryValue,
} from "../filtering";

interface FilterBuilderDialogProps {
  open: boolean;
  title: string;
  fields: FilterFieldOption[];
  initialState: FilterState;
  onClose: () => void;
  onApply: (state: FilterState) => void;
  onClear: () => void;
}

function resolveOperators(field: FilterFieldOption): FilterOperatorOption[] {
  const defaults = operatorOptionsForType(field.type);
  if (!field.operators?.length) {
    return defaults;
  }
  const allowed = new Set(field.operators);
  const filtered = defaults.filter((option) => allowed.has(option.value));
  if (filtered.length) {
    return filtered;
  }
  return defaults;
}

export default function FilterBuilderDialog({
  open,
  title,
  fields,
  initialState,
  onClose,
  onApply,
  onClear,
}: FilterBuilderDialogProps) {
  const [draftJoinMode, setDraftJoinMode] = useState<FilterState["joinMode"]>("and");
  const [draftConditions, setDraftConditions] = useState<FilterCondition[]>([]);

  const fieldsByKey = useMemo(
    () => new Map(fields.map((field) => [field.key, field])),
    [fields],
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    const nextJoinMode = initialState.joinMode ?? "and";
    let nextConditions = initialState.conditions;
    if (!nextConditions.length && fields.length) {
      const firstField = fields[0];
      nextConditions = [
        createFilterCondition(
          firstField.key,
          firstField.type,
          firstField.operators,
        ),
      ];
    }
    setDraftJoinMode(nextJoinMode);
    setDraftConditions(nextConditions);
  }, [fields, initialState.conditions, initialState.joinMode, open]);

  const addDraftFilter = () => {
    const firstField = fields[0];
    if (!firstField) {
      return;
    }
    setDraftConditions((prev) => [
      ...prev,
      createFilterCondition(firstField.key, firstField.type, firstField.operators),
    ]);
  };

  const updateDraftFilter = (id: string, updates: Partial<FilterCondition>) => {
    setDraftConditions((prev) =>
      prev.map((condition) => (condition.id === id ? { ...condition, ...updates } : condition)),
    );
  };

  const removeDraftFilter = (id: string) => {
    setDraftConditions((prev) => prev.filter((condition) => condition.id !== id));
  };

  const clearDraftFilters = () => {
    setDraftJoinMode("and");
    setDraftConditions([]);
    onClear();
    onClose();
  };

  const applyDraftFilters = () => {
    const completeConditions = draftConditions.filter(isConditionComplete);
    onApply({
      joinMode: draftJoinMode,
      conditions: completeConditions,
    });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={1.5}>
          <TextField
            select
            label="Combine filters with"
            value={draftJoinMode}
            onChange={(event) => {
              setDraftJoinMode(event.target.value as FilterState["joinMode"]);
            }}
            sx={{ maxWidth: 220 }}
            size="small"
          >
            <MenuItem value="and">AND</MenuItem>
            <MenuItem value="or">OR</MenuItem>
          </TextField>

          {draftConditions.map((condition, index) => {
            const field = fieldsByKey.get(condition.column) ?? fields[0];
            if (!field) {
              return null;
            }
            const operators = resolveOperators(field);
            const needsSecond = requiresSecondaryValue(condition.operator);
            return (
              <Paper key={condition.id} variant="outlined" sx={{ p: 1.2 }}>
                <Stack spacing={1}>
                  <Typography variant="caption" color="text.secondary">
                    Condition {index + 1}
                  </Typography>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems="flex-start">
                    <TextField
                      select
                      label="Column"
                      value={condition.column}
                      onChange={(event) => {
                        const nextColumn = event.target.value;
                        const nextField = fieldsByKey.get(nextColumn);
                        if (!nextField) {
                          return;
                        }
                        const nextOp = defaultOperatorForType(nextField.type, nextField.operators);
                        const isMulti = nextOp === "in" || nextOp === "not_in";
                        updateDraftFilter(condition.id, {
                          column: nextColumn,
                          operator: nextOp,
                          value: "",
                          secondaryValue: "",
                          ...(isMulti ? { values: [] } : { values: undefined }),
                        });
                      }}
                      size="small"
                      sx={{ minWidth: 200 }}
                    >
                      {fields.map((item) => (
                        <MenuItem key={item.key} value={item.key}>
                          {item.label}
                        </MenuItem>
                      ))}
                    </TextField>

                    <TextField
                      select
                      label="Operator"
                      value={condition.operator}
                      onChange={(event) => {
                        const nextOp = event.target.value as FilterOperator;
                        const isMulti = nextOp === "in" || nextOp === "not_in";
                        updateDraftFilter(condition.id, {
                          operator: nextOp,
                          value: "",
                          secondaryValue: "",
                          ...(isMulti ? { values: [] } : { values: undefined }),
                        });
                      }}
                      size="small"
                      sx={{ minWidth: 170 }}
                    >
                      {operators.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </TextField>

                    {field.type === "text" && isMultiValueOperator(condition.operator) ? (
                      <Box sx={{ flex: 1, minWidth: 220 }}>
                        <Autocomplete
                          multiple
                          disableCloseOnSelect
                          options={field.suggestions ?? []}
                          value={(condition.values ?? []).filter(Boolean)}
                          getOptionLabel={(opt) => String(opt)}
                          isOptionEqualToValue={(opt, val) => String(opt) === String(val)}
                          onChange={(_event, newValues) => {
                            updateDraftFilter(condition.id, {
                              values: newValues.map((v) => String(v).trim()).filter(Boolean),
                              value: "",
                            });
                          }}
                          renderInput={(params) => (
                            <TextField
                              {...params}
                              size="small"
                              label="Values"
                              placeholder="Select one or more"
                            />
                          )}
                        />
                      </Box>
                    ) : field.type === "text" ? (
                      <Box sx={{ flex: 1, minWidth: 220 }}>
                        <Autocomplete
                          freeSolo
                          options={field.suggestions ?? []}
                          inputValue={condition.value}
                          onInputChange={(_event, newInputValue) => {
                            updateDraftFilter(condition.id, { value: newInputValue });
                          }}
                          onChange={(_event, newValue) => {
                            updateDraftFilter(condition.id, {
                              value: typeof newValue === "string" ? newValue : newValue ?? "",
                            });
                          }}
                          renderInput={(params) => (
                            <TextField
                              {...params}
                              size="small"
                              label="Value"
                              placeholder="Type to search values"
                            />
                          )}
                        />
                      </Box>
                    ) : null}

                    {field.type === "number" ? (
                      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ flex: 1, minWidth: 220 }}>
                        <TextField
                          size="small"
                          label="Value"
                          type="number"
                          value={condition.value}
                          onChange={(event) => {
                            updateDraftFilter(condition.id, { value: event.target.value });
                          }}
                          fullWidth
                        />
                        {needsSecond ? (
                          <TextField
                            size="small"
                            label="To"
                            type="number"
                            value={condition.secondaryValue}
                            onChange={(event) => {
                              updateDraftFilter(condition.id, { secondaryValue: event.target.value });
                            }}
                            fullWidth
                          />
                        ) : null}
                      </Stack>
                    ) : null}

                    {field.type === "date" ? (
                      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ flex: 1, minWidth: 220 }}>
                        <TextField
                          size="small"
                          label="Date"
                          type="date"
                          value={condition.value}
                          onChange={(event) => {
                            updateDraftFilter(condition.id, { value: event.target.value });
                          }}
                          InputLabelProps={{ shrink: true }}
                          fullWidth
                        />
                        {needsSecond ? (
                          <TextField
                            size="small"
                            label="To Date"
                            type="date"
                            value={condition.secondaryValue}
                            onChange={(event) => {
                              updateDraftFilter(condition.id, { secondaryValue: event.target.value });
                            }}
                            InputLabelProps={{ shrink: true }}
                            fullWidth
                          />
                        ) : null}
                      </Stack>
                    ) : null}

                    <Tooltip title="Remove condition">
                      <IconButton
                        onClick={() => {
                          removeDraftFilter(condition.id);
                        }}
                        color="error"
                      >
                        <DeleteOutlineIcon />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Stack>
              </Paper>
            );
          })}

          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              startIcon={<AddCircleOutlineIcon />}
              variant="outlined"
              onClick={addDraftFilter}
              disabled={!fields.length}
            >
              Add filter
            </Button>
            {initialState.conditions.length ? (
              <Typography variant="caption" color="text.secondary">
                Active filters: {initialState.conditions.length}
              </Typography>
            ) : null}
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={clearDraftFilters}
          startIcon={<ClearAllOutlinedIcon />}
          disabled={!initialState.conditions.length && !draftConditions.length}
        >
          Clear filters
        </Button>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          onClick={applyDraftFilters}
          variant="contained"
          disabled={!draftConditions.length || !draftConditions.every(isConditionComplete)}
        >
          Apply
        </Button>
      </DialogActions>
    </Dialog>
  );
}
