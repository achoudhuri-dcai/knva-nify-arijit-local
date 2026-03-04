export type FilterJoinMode = "and" | "or";
export type ColumnType = "text" | "number" | "date";
export type FilterOperator =
  | "contains"
  | "equals"
  | "not_equals"
  | "starts_with"
  | "ends_with"
  | "in"
  | "not_in"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "before"
  | "after"
  | "between"
  | "on";

export interface FilterCondition {
  id: string;
  column: string;
  operator: FilterOperator;
  value: string;
  secondaryValue: string;
  /** Multi-value for "in" and "not_in" operators. */
  values?: string[];
}

export interface FilterFieldOption {
  key: string;
  label: string;
  type: ColumnType;
  suggestions?: string[];
  operators?: FilterOperator[];
}

export interface FilterState {
  joinMode: FilterJoinMode;
  conditions: FilterCondition[];
}

export interface FilterOperatorOption {
  value: FilterOperator;
  label: string;
}

export const EMPTY_FILTER_STATE: FilterState = {
  joinMode: "and",
  conditions: [],
};

export const TEXT_OPERATOR_OPTIONS: FilterOperatorOption[] = [
  { value: "contains", label: "Contains" },
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not equals" },
  { value: "starts_with", label: "Starts with" },
  { value: "ends_with", label: "Ends with" },
  { value: "in", label: "In (any of)" },
  { value: "not_in", label: "Not in" },
];

export const NUMBER_OPERATOR_OPTIONS: FilterOperatorOption[] = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not equals" },
  { value: "gt", label: "Greater than" },
  { value: "gte", label: "Greater or equal" },
  { value: "lt", label: "Less than" },
  { value: "lte", label: "Less or equal" },
  { value: "between", label: "Between" },
];

export const DATE_OPERATOR_OPTIONS: FilterOperatorOption[] = [
  { value: "on", label: "On" },
  { value: "before", label: "Before" },
  { value: "after", label: "After" },
  { value: "between", label: "Between" },
];

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeText(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim().toLowerCase();
}

function parseNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parseDate(value: unknown): Date | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value;
  }
  if (typeof value === "string" || typeof value === "number") {
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed;
    }
  }
  return null;
}

function toDateKey(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

export function inferColumnType(values: unknown[]): ColumnType {
  if (!values.length) {
    return "text";
  }

  let numericCount = 0;
  let dateCount = 0;
  for (const value of values) {
    if (parseNumber(value) !== null) {
      numericCount += 1;
      continue;
    }
    if (parseDate(value) !== null) {
      dateCount += 1;
    }
  }

  const total = values.length;
  if (numericCount / total >= 0.8) {
    return "number";
  }
  if (dateCount / total >= 0.8) {
    return "date";
  }
  return "text";
}

export function operatorOptionsForType(type: ColumnType): FilterOperatorOption[] {
  if (type === "number") {
    return NUMBER_OPERATOR_OPTIONS;
  }
  if (type === "date") {
    return DATE_OPERATOR_OPTIONS;
  }
  return TEXT_OPERATOR_OPTIONS;
}

export function defaultOperatorForType(type: ColumnType, operators?: FilterOperator[]): FilterOperator {
  if (operators && operators.length > 0) {
    return operators[0];
  }
  return operatorOptionsForType(type)[0].value;
}

export function requiresSecondaryValue(operator: FilterOperator): boolean {
  return operator === "between";
}

export function isMultiValueOperator(operator: FilterOperator): boolean {
  return operator === "in" || operator === "not_in";
}

export function createFilterCondition(
  column: string,
  type: ColumnType,
  operators?: FilterOperator[],
): FilterCondition {
  const op = defaultOperatorForType(type, operators);
  return {
    id: createId(),
    column,
    operator: op,
    value: "",
    secondaryValue: "",
    ...(isMultiValueOperator(op) ? { values: [] } : {}),
  };
}

export function isConditionComplete(condition: FilterCondition): boolean {
  if (!condition.column || !condition.operator) {
    return false;
  }
  if (isMultiValueOperator(condition.operator)) {
    const vals = condition.values ?? [];
    return vals.length > 0 && vals.some((v) => String(v).trim().length > 0);
  }
  if (!condition.value.trim()) {
    return false;
  }
  if (requiresSecondaryValue(condition.operator)) {
    return Boolean(condition.secondaryValue.trim());
  }
  return true;
}

export function evaluateFilterCondition(
  rowValue: unknown,
  condition: FilterCondition,
  columnType: ColumnType,
): boolean {
  if (!isConditionComplete(condition)) {
    return true;
  }

  if (columnType === "number") {
    const left = parseNumber(rowValue);
    const right = parseNumber(condition.value);
    const right2 = parseNumber(condition.secondaryValue);
    if (left === null || right === null) {
      return false;
    }
    switch (condition.operator) {
      case "equals":
        return left === right;
      case "not_equals":
        return left !== right;
      case "gt":
        return left > right;
      case "gte":
        return left >= right;
      case "lt":
        return left < right;
      case "lte":
        return left <= right;
      case "between":
        if (right2 === null) {
          return false;
        }
        return left >= Math.min(right, right2) && left <= Math.max(right, right2);
      default:
        return false;
    }
  }

  if (columnType === "date") {
    const leftDate = parseDate(rowValue);
    const rightDate = parseDate(condition.value);
    const rightDate2 = parseDate(condition.secondaryValue);
    if (!leftDate || !rightDate) {
      return false;
    }
    const left = toDateKey(leftDate);
    const right = toDateKey(rightDate);
    const right2 = rightDate2 ? toDateKey(rightDate2) : null;

    switch (condition.operator) {
      case "on":
      case "equals":
        return left === right;
      case "before":
      case "lt":
        return left < right;
      case "after":
      case "gt":
        return left > right;
      case "between":
        if (right2 === null) {
          return false;
        }
        return left >= Math.min(right, right2) && left <= Math.max(right, right2);
      default:
        return false;
    }
  }

  const leftText = normalizeText(rowValue);
  if (condition.operator === "in" || condition.operator === "not_in") {
    const vals = condition.values ?? [];
    const valueSet = new Set(vals.map((v) => normalizeText(v)).filter(Boolean));
    const isIn = valueSet.has(leftText) || (leftText === "" && valueSet.size === 0);
    return condition.operator === "in" ? isIn : !isIn;
  }
  const rightText = normalizeText(condition.value);
  switch (condition.operator) {
    case "contains":
      return leftText.includes(rightText);
    case "equals":
      return leftText === rightText;
    case "not_equals":
      return leftText !== rightText;
    case "starts_with":
      return leftText.startsWith(rightText);
    case "ends_with":
      return leftText.endsWith(rightText);
    default:
      return false;
  }
}
