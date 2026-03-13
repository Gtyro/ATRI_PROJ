import type { EChartsType } from "echarts/core";

type CoreEchartsRuntime = typeof import("echarts/core");
type WordCloudEchartsRuntime = typeof import("echarts");

let coreRuntimePromise: Promise<CoreEchartsRuntime> | null = null;
let wordCloudRuntimePromise: Promise<WordCloudEchartsRuntime> | null = null;

export const loadCoreEchartsRuntime = async (): Promise<CoreEchartsRuntime> => {
  if (!coreRuntimePromise) {
    coreRuntimePromise = Promise.all([
      import("echarts/core"),
      import("echarts/charts"),
      import("echarts/components"),
      import("echarts/renderers"),
    ]).then(
      ([echartsCore, echartsCharts, echartsComponents, echartsRenderers]) => {
        echartsCore.use([
          echartsCharts.LineChart,
          echartsCharts.BarChart,
          echartsCharts.PieChart,
          echartsCharts.GraphChart,
          echartsCharts.HeatmapChart,
          echartsComponents.TooltipComponent,
          echartsComponents.LegendComponent,
          echartsComponents.GridComponent,
          echartsComponents.DatasetComponent,
          echartsComponents.TitleComponent,
          echartsComponents.DataZoomComponent,
          echartsComponents.CalendarComponent,
          echartsComponents.VisualMapComponent,
          echartsRenderers.CanvasRenderer,
        ]);
        return echartsCore;
      },
    );
  }

  return coreRuntimePromise;
};

export const loadWordCloudRuntime =
  async (): Promise<WordCloudEchartsRuntime> => {
    if (!wordCloudRuntimePromise) {
      wordCloudRuntimePromise = Promise.all([
        import("echarts"),
        import("echarts-wordcloud"),
      ]).then(([echartsRuntime]) => echartsRuntime);
    }

    return wordCloudRuntimePromise;
  };

export const createResizeObserver = (
  target: Element | null | undefined,
  callback: () => void,
): ResizeObserver | null => {
  if (!target || typeof ResizeObserver === "undefined") {
    return null;
  }

  const observer = new ResizeObserver(() => {
    callback();
  });
  observer.observe(target);
  return observer;
};

export const disconnectObserver = <
  T extends Pick<ResizeObserver, "disconnect"> | null,
>(
  observer: T,
): null => {
  observer?.disconnect();
  return null;
};

export const disposeChart = <T extends Pick<EChartsType, "dispose"> | null>(
  chart: T,
): null => {
  chart?.dispose();
  return null;
};
