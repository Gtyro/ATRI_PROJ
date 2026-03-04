export type ModuleMetricChartType =
  | "kpi"
  | "table"
  | "line"
  | "bar"
  | "pie"
  | string;

export type ModuleMetricPrimitive = string | number | boolean | null;

export type ModuleMetricDataRow = Record<
  string,
  ModuleMetricPrimitive | ModuleMetricPrimitive[] | Record<string, unknown> | undefined
>;

export interface ModuleMetricKpi {
  key?: string;
  label?: string;
  format?: string;
  value?: ModuleMetricPrimitive;
  [key: string]: unknown;
}

export interface ModuleMetricSeries {
  field?: string;
  name?: string;
  type?: string;
  y_axis?: string;
  name_field?: string;
  [key: string]: unknown;
}

export interface ModuleMetricXAxis {
  field?: string;
  type?: string;
  [key: string]: unknown;
}

export interface ModuleMetricTableColumn {
  prop: string;
  label?: string;
  minWidth?: number;
  [key: string]: unknown;
}

export interface ModuleMetricMeta {
  columns?: Array<string | ModuleMetricTableColumn>;
  total?: number;
  page?: number;
  size?: number;
  [key: string]: unknown;
}

export interface ModuleMetricChart {
  type: ModuleMetricChartType;
  chart_id?: string;
  title?: string;
  dataset?: ModuleMetricDataRow[];
  series?: ModuleMetricSeries[];
  x_axis?: ModuleMetricXAxis;
  meta?: ModuleMetricMeta;
  [key: string]: unknown;
}

export interface ModuleMetricDefinition {
  module_id: string;
  title?: string;
  description?: string;
  plugin_name?: string;
  module_name?: string;
  [key: string]: unknown;
}

export interface ModuleMetricOverviewItem extends ModuleMetricDefinition {
  kpis?: ModuleMetricKpi[];
  main_chart?: ModuleMetricChart | null;
}

export interface ModuleMetricModulesPayload {
  items: ModuleMetricDefinition[];
  [key: string]: unknown;
}

export interface ModuleMetricOverviewPayload {
  items: ModuleMetricOverviewItem[];
  [key: string]: unknown;
}

export interface ModuleMetricDetailPayload {
  module_id: string;
  title?: string;
  charts: ModuleMetricChart[];
  [key: string]: unknown;
}

export interface ModuleMetricOptionsPayload {
  plugin_names: string[];
  module_names: string[];
  operations: string[];
  conv_ids: string[];
  [key: string]: unknown;
}

export interface ModuleMetricQueryParams {
  from?: string;
  to?: string;
  plugin_name?: string;
  module_name?: string;
  operation?: string;
  conv_id?: string;
  [key: string]: string | number | boolean | undefined;
}
