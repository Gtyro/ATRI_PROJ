import { defineStore } from "pinia";

import {
  getConversations,
  getMemoryDetail,
  getMemoryStats,
  getMemoryTimeline,
  type MemoryTimelineItem,
} from "@/api/memory";

interface TimeRange {
  start: Date | null;
  end: Date | null;
}

interface MemoryState {
  timelineData: MemoryTimelineItem[];
  conversations: string[];
  currentConvId: string;
  memoryStats: Record<string, unknown>;
  selectedMemory: Record<string, unknown> | null;
  timeRange: TimeRange;
  isLoading: boolean;
  error: string | null;
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误";
};

export const useMemoryStore = defineStore("memory", {
  state: (): MemoryState => ({
    timelineData: [],
    conversations: [],
    currentConvId: "",
    memoryStats: {},
    selectedMemory: null,
    timeRange: {
      start: null,
      end: null,
    },
    isLoading: false,
    error: null,
  }),

  getters: {
    filteredMemories: (state): MemoryTimelineItem[] => {
      if (!state.timeRange.start && !state.timeRange.end) {
        return state.timelineData;
      }

      return state.timelineData.filter((memory) => {
        const createdAt = new Date(memory.created_at * 1000);

        if (state.timeRange.start && state.timeRange.end) {
          return (
            createdAt >= state.timeRange.start &&
            createdAt <= state.timeRange.end
          );
        }
        if (state.timeRange.start) {
          return createdAt >= state.timeRange.start;
        }
        if (state.timeRange.end) {
          return createdAt <= state.timeRange.end;
        }

        return true;
      });
    },

    memoriesByDay(): Record<string, MemoryTimelineItem[]> {
      const grouped: Record<string, MemoryTimelineItem[]> = {};

      this.filteredMemories.forEach((memory) => {
        const date = new Date(memory.created_at * 1000).toLocaleDateString();
        if (!grouped[date]) {
          grouped[date] = [];
        }
        grouped[date].push(memory);
      });

      return grouped;
    },
  },

  actions: {
    setTimeRange(start: Date | null, end: Date | null): void {
      this.timeRange = { start, end };
    },

    setCurrentConvId(convId: string): void {
      this.currentConvId = convId;
    },

    async fetchConversations(): Promise<string[]> {
      this.isLoading = true;
      this.error = null;

      try {
        const response = await getConversations();
        this.conversations = Array.isArray(response.data?.rows)
          ? response.data.rows
          : [];
        return this.conversations;
      } catch (error: unknown) {
        this.error = `获取会话列表失败: ${getErrorMessage(error)}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchMemoryTimeline(): Promise<MemoryTimelineItem[]> {
      this.isLoading = true;
      this.error = null;

      try {
        const response = await getMemoryTimeline(
          this.currentConvId,
          this.timeRange.start
            ? Math.floor(this.timeRange.start.getTime() / 1000)
            : null,
          this.timeRange.end
            ? Math.floor(this.timeRange.end.getTime() / 1000)
            : null,
        );

        this.timelineData = Array.isArray(response.data?.memories)
          ? response.data.memories
          : [];
        return this.timelineData;
      } catch (error: unknown) {
        this.error = `获取记忆时间线失败: ${getErrorMessage(error)}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchMemoryDetail(
      memoryId: string,
    ): Promise<Record<string, unknown> | null> {
      this.isLoading = true;
      this.error = null;

      try {
        const response = await getMemoryDetail(memoryId);
        this.selectedMemory =
          response.data && typeof response.data === "object"
            ? response.data
            : null;
        return this.selectedMemory;
      } catch (error: unknown) {
        this.error = `获取记忆详情失败: ${getErrorMessage(error)}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchMemoryStats(): Promise<Record<string, unknown>> {
      this.isLoading = true;
      this.error = null;

      try {
        const response = await getMemoryStats(this.currentConvId);
        this.memoryStats =
          response.data && typeof response.data === "object"
            ? response.data
            : {};
        return this.memoryStats;
      } catch (error: unknown) {
        this.error = `获取记忆统计失败: ${getErrorMessage(error)}`;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },

    resetState(): void {
      this.timelineData = [];
      this.selectedMemory = null;
      this.error = null;
    },
  },
});
