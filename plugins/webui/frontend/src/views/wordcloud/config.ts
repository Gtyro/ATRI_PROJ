const wordcloudConfig = {
  cloudOptions: {
    colors: [
      "#1f77b4",
      "#ff7f0e",
      "#2ca02c",
      "#d62728",
      "#9467bd",
      "#8c564b",
      "#e377c2",
      "#7f7f7f",
      "#bcbd22",
      "#17becf",
    ],
    fontFamily:
      'Arial, "Microsoft YaHei", "微软雅黑", STXihei, "华文细黑", sans-serif',
    rotationRange: [-90, 90],
    rotationStep: 45,
    fontSizeRatio: 5,
    minFontSize: 40,
    maxFontSize: 120,
    animation: true,
    animationDuration: 1000,
    interactive: true,
    backgroundColor: "rgba(255, 255, 255, 0.8)",
  },
  controlPanel: {
    show: true,
    position: "right",
    showRefreshButton: true,
    showHistorySelector: true,
    showLimitSlider: true,
    showConversationSelector: false,
    maxLimit: 100,
    defaultLimit: 50,
  },
  emptyText: "暂无词云数据",
  loadingText: "正在加载词云数据...",
  errorText: "加载词云数据失败",
  autoRefreshInterval: 0,
};

export default wordcloudConfig;
