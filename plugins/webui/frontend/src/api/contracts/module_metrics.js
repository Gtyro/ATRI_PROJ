const CONTRACT_PREFIX = "[module-metrics-contract]";

const isPlainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const fail = (path, message) => {
  throw new Error(`${CONTRACT_PREFIX} ${path} ${message}`);
};

const ensureObject = (value, path) => {
  if (!isPlainObject(value)) {
    fail(path, "must be an object");
  }
  return value;
};

const ensureArray = (value, path) => {
  if (!Array.isArray(value)) {
    fail(path, "must be an array");
  }
  return value;
};

const ensureString = (value, path, { allowEmpty = false } = {}) => {
  if (typeof value !== "string") {
    fail(path, "must be a string");
  }
  if (!allowEmpty && value.trim() === "") {
    fail(path, "must be a non-empty string");
  }
  return value;
};

const ensureOptionalString = (value, path) => {
  if (value == null) {
    return;
  }
  ensureString(value, path, { allowEmpty: true });
};

const ensureStringArray = (value, path) => {
  const list = ensureArray(value, path);
  list.forEach((item, index) => {
    ensureString(item, `${path}[${index}]`, { allowEmpty: false });
  });
};

const ensureChart = (chart, path) => {
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
};

const ensureKpi = (kpi, path) => {
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
};

export const validateModuleMetricModulesPayload = (payload) => {
  const root = ensureObject(payload, "payload");
  const items = ensureArray(root.items, "payload.items");
  items.forEach((item, index) => {
    const node = ensureObject(item, `payload.items[${index}]`);
    ensureString(node.module_id, `payload.items[${index}].module_id`, {
      allowEmpty: false,
    });
    ensureOptionalString(node.title, `payload.items[${index}].title`);
    ensureOptionalString(
      node.description,
      `payload.items[${index}].description`,
    );
    ensureOptionalString(
      node.plugin_name,
      `payload.items[${index}].plugin_name`,
    );
    ensureOptionalString(
      node.module_name,
      `payload.items[${index}].module_name`,
    );
  });
  return payload;
};

export const validateModuleMetricOverviewPayload = (payload) => {
  const root = ensureObject(payload, "payload");
  const items = ensureArray(root.items, "payload.items");
  items.forEach((item, index) => {
    const node = ensureObject(item, `payload.items[${index}]`);
    ensureString(node.module_id, `payload.items[${index}].module_id`, {
      allowEmpty: false,
    });
    ensureOptionalString(node.title, `payload.items[${index}].title`);
    ensureOptionalString(
      node.description,
      `payload.items[${index}].description`,
    );

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
  return payload;
};

export const validateModuleMetricDetailPayload = (payload) => {
  const root = ensureObject(payload, "payload");
  ensureString(root.module_id, "payload.module_id", { allowEmpty: false });
  ensureOptionalString(root.title, "payload.title");
  const charts = ensureArray(root.charts, "payload.charts");
  charts.forEach((chart, index) => {
    ensureChart(chart, `payload.charts[${index}]`);
  });
  return payload;
};

export const validateModuleMetricOptionsPayload = (payload) => {
  const root = ensureObject(payload, "payload");
  ensureStringArray(root.plugin_names, "payload.plugin_names");
  ensureStringArray(root.module_names, "payload.module_names");
  ensureStringArray(root.operations, "payload.operations");
  ensureStringArray(root.conv_ids, "payload.conv_ids");
  return payload;
};
