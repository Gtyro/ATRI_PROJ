// @ts-nocheck
import { defineComponent, nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TableManager from "@/components/TableManager.vue";
import {
  addRecord,
  createCognitiveNode,
  deleteCognitiveNode,
  deleteRecord,
  executeCypherQuery,
  executeQuery,
  getNodeLabels,
  getTables,
  updateCognitiveNode,
  updateRecord,
} from "@/api/db";

vi.mock("@/stores/db", () => ({
  useDbStore: () => ({
    setDataSource: vi.fn(),
  }),
}));

vi.mock("@/api", () => ({
  request: {
    get: vi.fn(),
  },
}));

vi.mock("@/api/db", () => ({
  addRecord: vi.fn(),
  updateRecord: vi.fn(),
  deleteRecord: vi.fn(),
  executeQuery: vi.fn(),
  executeCypherQuery: vi.fn(),
  getTables: vi.fn(),
  getNodeLabels: vi.fn(),
  createCognitiveNode: vi.fn(),
  updateCognitiveNode: vi.fn(),
  deleteCognitiveNode: vi.fn(),
}));

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

const settle = async (times = 4) => {
  for (let i = 0; i < times; i += 1) {
    await flushPromises();
  }
};

const ElButtonStub = defineComponent({
  name: "ElButtonStub",
  emits: ["click"],
  template:
    '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
});

const mountTableManager = () =>
  mount(TableManager, {
    props: {
      tables: [],
      onResult: vi.fn(),
      initialTable: "",
    },
    global: {
      stubs: {
        "el-form": true,
        "el-form-item": true,
        "el-radio-group": true,
        "el-radio": true,
        "el-select": true,
        "el-option": true,
        "el-checkbox-group": true,
        "el-checkbox": true,
        "el-input": true,
        "el-input-number": true,
        "el-button": ElButtonStub,
        "el-icon": true,
        "el-table": true,
        "el-table-column": true,
        "el-pagination": true,
        "el-dialog": true,
        "el-tag": true,
        "el-popconfirm": true,
        "el-auto-resizer": true,
        "el-table-v2": true,
      },
      directives: {
        loading() {},
      },
    },
  });

const setMaybeRef = (holder, key, value) => {
  const current = holder[key];
  if (current && typeof current === "object" && "value" in current) {
    current.value = value;
    return;
  }
  holder[key] = value;
};

const getMaybeRef = (holder, key) => {
  const current = holder[key];
  if (current && typeof current === "object" && "value" in current) {
    return current.value;
  }
  return current;
};

describe("TableManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getTables.mockResolvedValue({
      data: { tables: ["users", "logs"] },
    });
    getNodeLabels.mockResolvedValue({
      data: {
        results: [],
      },
    });

    executeQuery.mockResolvedValue({
      data: { columns: ["id"], rows: [] },
    });
    executeCypherQuery.mockResolvedValue({
      data: { results: [], metadata: [] },
    });
    addRecord.mockResolvedValue({ data: {} });
    updateRecord.mockResolvedValue({ data: {} });
    deleteRecord.mockResolvedValue({ data: {} });
    createCognitiveNode.mockResolvedValue({ data: {} });
    updateCognitiveNode.mockResolvedValue({ data: {} });
    deleteCognitiveNode.mockResolvedValue({ data: {} });
  });

  it("switches to virtual result table when rows exceed threshold", async () => {
    const wrapper = mountTableManager();
    await settle();

    const setupState = wrapper.vm.$.setupState;
    setMaybeRef(setupState, "resultData", {
      columns: ["id", "name"],
      rows: Array.from({ length: 220 }, (_, index) => ({
        id: index + 1,
        name: `row_${index + 1}`,
      })),
    });
    await nextTick();

    const useVirtual = getMaybeRef(setupState, "useVirtualResultTable");
    expect(useVirtual).toBe(true);
    expect(wrapper.find(".virtual-result-shell").exists()).toBe(true);
  });

  it("removes virtual row key from editable form payload", async () => {
    const wrapper = mountTableManager();
    await settle();

    const setupState = wrapper.vm.$.setupState;
    setupState.handleEdit({
      id: 1001,
      name: "alice",
      __row_key: 7,
    });
    await nextTick();

    const formData = getMaybeRef(setupState, "formData");
    const showEditForm = getMaybeRef(setupState, "showEditForm");

    expect(formData).toMatchObject({
      id: 1001,
      name: "alice",
    });
    expect(formData.__row_key).toBeUndefined();
    expect(showEditForm).toBe(true);
  });
});
