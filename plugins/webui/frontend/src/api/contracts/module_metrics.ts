import type {
  ModuleMetricChart,
  ModuleMetricDetailPayload,
  ModuleMetricKpi,
  ModuleMetricModulesPayload,
  ModuleMetricOptionsPayload,
  ModuleMetricOverviewPayload,
} from "@/types/module_metrics";

const CONTRACT_PREFIX = "[module-metrics-contract]";

type LooseRecord = Record<string, unknown>;

const isPlainObject = (value: unknown): value is LooseRecord =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const fail = (path: string, message: string): never => {
  throw new Error(`${CONTRACT_PREFIX} ${path} ${message}`);
};

const ensureObject = (value: unknown, path: string): LooseRecord => {
  if (!isPlainObject(value)) {
    fail(path, "must be an object");
  }
  return value as LooseRecord;
};

const ensureArray = (value: unknown, path: string): unknown[] => {
  if (!Array.isArray(value)) {
    fail(path, "must be an array");
  }
  return value as unknown[];
};

const ensureString = (
  value: unknown,
  path: string,
  options: { allowEmpty?: boolean } = {},
): string => {
  const { allowEmpty = false } = options;
  if (typeof value !== "string") {
    fail(path, "must be a string");
  }
  const parsed = value as string;
  if (!allowEmpty && parsed.trim() === "") {
    fail(path, "must be a non-empty string");
  }
  return parsed;
};

const ensureOptionalString = (value: unknown, path: string): void => {
  if (value == null) {
    return;
  }
  ensureString(value, path, { allowEmpty: true });
};

const ensureStringArray = (value: unknown, path: string): string[] => {
  const list = ensureArray(value, path);
  list.forEach((item, index) => {
    ensureString(item, `${path}[${index}]`, { allowEmpty: false });
  });
  return list as string[];
};

const ensureChart = (chart: unknown, path: string): ModuleMetricChart => {
  const parsed = ensureObject(chart, path);
  ensureString(parsed.type, `${path}.type`, { allowEmpty: false });
  ensureOptionalString(parsed.chart_id, `${path}.chart_id`);
  ensureOptionalString(parsed.title, `${path}.title`);
  if ("dataset" in parsed && !Array.isArray(parsed.dataset)) {
    fail(`${path}.dataset`, "must be an array when provided");
  }
  if ("series" in parsed && !Array.isArray(parsed.series)) {
    fail(`${path}.series`, "must be an array when provided");
  }
  return parsed as ModuleMetricChart;
};

const ensureKpi = (kpi: unknown, path: string): ModuleMetricKpi => {
  const parsed = ensureObject(kpi, path);
  if ("key" in parsed) {
    ensureOptionalString(parsed.key, `${path}.key`);
  }
  if ("label" in parsed) {
    ensureOptionalString(parsed.label, `${path}.label`);
  }
  if ("format" in parsed) {
    ensureOptionalString(parsed.format, `${path}.format`);
  }
  return parsed as ModuleMetricKpi;
};

export const validateModuleMetricModulesPayload = (
  payload: unknown,
): ModuleMetricModulesPayload => {
  const root = ensureObject(payload, "payload");
  const items = ensureArray(root.items, "payload.items");
  items.forEach((item, index) => {
    const node = ensureObject(item, `payload.items[${index}]`);
    ensureString(node.module_id, `payload.items[${index}].module_id`, {
      allowEmpty: false,
    });
    ensureOptionalString(node.title, `payload.items[${index}].title`);
    ensureOptionalString(node.description, `payload.items[${index}].description`);
    ensureOptionalString(node.plugin_name, `payload.items[${index}].plugin_name`);
    ensureOptionalString(node.module_name, `payload.items[${index}].module_name`);
  });
  return root as ModuleMetricModulesPayload;
};

export const validateModuleMetricOverviewPayload = (
  payload: unknown,
): ModuleMetricOverviewPayload => {
  const root = ensureObject(payload, "payload");
  const items = ensureArray(root.items, "payload.items");
  items.forEach((item, index) => {
    const node = ensureObject(item, `payload.items[${index}]`);
    ensureString(node.module_id, `payload.items[${index}].module_id`, {
      allowEmpty: false,
    });
    ensureOptionalString(node.title, `payload.items[${index}].title`);
    ensureOptionalString(node.description, `payload.items[${index}].description`);

    if ("kpis" in node) {
      const kpis = ensureArray(node.kpis, `payload.items[${index}].kpis`);
      kpis.forEach((kpi, kpiIndex) => {
        ensureKpi(kpi, `payload.items[${index}].kpis[${kpiIndex}]`);
      });
    }

    if (node.main_chart != null) {
      ensureChart(node.main_chart, `payload.items[${index}].main_chart`);
    }
  });
  return root as ModuleMetricOverviewPayload;
};

export const validateModuleMetricDetailPayload = (
  payload: unknown,
): ModuleMetricDetailPayload => {
  const root = ensureObject(payload, "payload");
  ensureString(root.module_id, "payload.module_id", { allowEmpty: false });
  ensureOptionalString(root.title, "payload.title");
  const charts = ensureArray(root.charts, "payload.charts");
  charts.forEach((chart, index) => {
    ensureChart(chart, `payload.charts[${index}]`);
  });
  return root as ModuleMetricDetailPayload;
};

export const validateModuleMetricOptionsPayload = (
  payload: unknown,
): ModuleMetricOptionsPayload => {
  const root = ensureObject(payload, "payload");
  ensureStringArray(root.plugin_names, "payload.plugin_names");
  ensureStringArray(root.module_names, "payload.module_names");
  ensureStringArray(root.operations, "payload.operations");
  ensureStringArray(root.conv_ids, "payload.conv_ids");
  return root as ModuleMetricOptionsPayload;
};
