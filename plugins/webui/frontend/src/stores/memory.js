// store/modules/memory.js
import { defineStore } from 'pinia'
import { getMemoryTimeline, getMemoryDetail, getMemoryStats, getConversations } from '@/api/memory'

export const useMemoryStore = defineStore('memory', {
  state: () => ({
    // 记忆时间线数据
    timelineData: [],
    
    // 会话列表
    conversations: [],
    currentConvId: '',
    
    // 记忆统计
    memoryStats: {},
    
    // 当前选中的记忆
    selectedMemory: null,
    
    // 时间范围过滤
    timeRange: {
      start: null,
      end: null
    },
    
    // 加载状态
    isLoading: false,
    
    // 错误信息
    error: null
  }),

  getters: {
    // 获取当前过滤后的记忆数据
    filteredMemories: (state) => {
      if (!state.timeRange.start && !state.timeRange.end) {
        return state.timelineData;
      }
      
      return state.timelineData.filter(memory => {
        const createdAt = new Date(memory.created_at * 1000);
        
        if (state.timeRange.start && state.timeRange.end) {
          return createdAt >= state.timeRange.start && createdAt <= state.timeRange.end;
        } else if (state.timeRange.start) {
          return createdAt >= state.timeRange.start;
        } else if (state.timeRange.end) {
          return createdAt <= state.timeRange.end;
        }
        
        return true;
      });
    },
    
    // 按时间分组的记忆数据
    memoriesByDay: (state) => {
      const grouped = {};
      
      state.filteredMemories.forEach(memory => {
        const date = new Date(memory.created_at * 1000).toLocaleDateString();
        if (!grouped[date]) {
          grouped[date] = [];
        }
        grouped[date].push(memory);
      });
      
      return grouped;
    }
  },

  actions: {
    // 设置时间范围
    setTimeRange(start, end) {
      this.timeRange = { start, end };
    },
    
    // 设置当前会话ID
    setCurrentConvId(convId) {
      this.currentConvId = convId;
    },
    
    // 获取会话列表
    async fetchConversations() {
      this.isLoading = true;
      this.error = null;
      
      try {
        const response = await getConversations();
        this.conversations = response.data.rows || [];
        return this.conversations;
      } catch (error) {
        this.error = `获取会话列表失败: ${error.message}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // 获取记忆时间线数据
    async fetchMemoryTimeline() {
      this.isLoading = true;
      this.error = null;
      
      try {
        const response = await getMemoryTimeline(
          this.currentConvId,
          this.timeRange.start ? Math.floor(this.timeRange.start.getTime() / 1000) : null,
          this.timeRange.end ? Math.floor(this.timeRange.end.getTime() / 1000) : null
        );
        
        this.timelineData = response.data.memories || [];
        return this.timelineData;
      } catch (error) {
        this.error = `获取记忆时间线失败: ${error.message}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // 获取记忆详情
    async fetchMemoryDetail(memoryId) {
      this.isLoading = true;
      this.error = null;
      
      try {
        const response = await getMemoryDetail(memoryId);
        this.selectedMemory = response.data;
        return this.selectedMemory;
      } catch (error) {
        this.error = `获取记忆详情失败: ${error.message}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // 获取记忆统计数据
    async fetchMemoryStats() {
      this.isLoading = true;
      this.error = null;
      
      try {
        const response = await getMemoryStats(this.currentConvId);
        this.memoryStats = response.data;
        return this.memoryStats;
      } catch (error) {
        this.error = `获取记忆统计失败: ${error.message}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // 重置状态
    resetState() {
      this.timelineData = [];
      this.selectedMemory = null;
      this.error = null;
    }
  }
}); 