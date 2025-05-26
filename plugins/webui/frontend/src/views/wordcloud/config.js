export default {
  // 词云基本配置
  cloudOptions: {
    // 颜色配置
    colors: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'],
    
    // 字体配置
    fontFamily: 'Arial, "Microsoft YaHei", "微软雅黑", STXihei, "华文细黑", sans-serif',
    
    // 布局配置
    rotationRange: [-90, 90],
    rotationStep: 45,
    fontSizeRatio: 5, // 字体大小比例系数
    
    // 响应式配置
    minFontSize: 40,
    maxFontSize: 120,
    
    // 动画配置
    animation: true,
    animationDuration: 1000,
    
    // 交互配置
    interactive: true,
    
    // 背景颜色
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
  },
  
  // 控制面板配置
  controlPanel: {
    show: true,
    position: 'right', // right, left, top, bottom
    showRefreshButton: true,
    showHistorySelector: true,
    showLimitSlider: true,
    maxLimit: 100,
    defaultLimit: 50,
  },
  
  // 空数据提示
  emptyText: '暂无词云数据',
  
  // 加载提示
  loadingText: '正在加载词云数据...',
  
  // 错误提示
  errorText: '加载词云数据失败',
  
  // 定时刷新时间（毫秒），0 表示不自动刷新
  autoRefreshInterval: 0,
} 