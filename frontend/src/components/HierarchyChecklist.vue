<script setup lang="ts">
import { computed, defineComponent, h, ref } from "vue";
import type { HierarchyNode } from "../services/api";

interface TreeNode extends HierarchyNode {
  children: TreeNode[];
}

const props = defineProps<{
  title: string;
  nodes: HierarchyNode[];
  modelValue: string[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string[]];
}>();

const selectedSet = computed(() => new Set(props.modelValue));
const searchQuery = ref("");
const hideZeroRows = ref(true);

function buildTree(nodes: HierarchyNode[]): TreeNode[] {
  const byCode = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  for (const node of nodes) {
    byCode.set(node.code, { ...node, children: [] });
  }
  for (const node of byCode.values()) {
    if (node.parent_code && byCode.has(node.parent_code)) {
      byCode.get(node.parent_code)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function toggleNode(node: TreeNode, checked: boolean): void {
  const next = new Set(props.modelValue);
  if (checked) next.add(node.code);
  else next.delete(node.code);
  emit("update:modelValue", Array.from(next));
}

function resetFilter(): void {
  searchQuery.value = "";
  emit("update:modelValue", []);
}

const treeRoots = computed(() => buildTree(props.nodes));

function filterZeroRows(nodes: TreeNode[], selected: Set<string>): TreeNode[] {
  const filtered: TreeNode[] = [];
  for (const node of nodes) {
    const filteredChildren = filterZeroRows(node.children, selected);
    const hasRows = (node.row_count ?? 0) > 0;
    const selectedByUser = selected.has(node.code);
    if (hasRows || selectedByUser || filteredChildren.length > 0) {
      filtered.push({
        ...node,
        children: filteredChildren
      });
    }
  }
  return filtered;
}

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  if (!query) {
    return nodes;
  }

  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return nodes;
  }

  const filtered: TreeNode[] = [];

  for (const node of nodes) {
    const ownMatch =
      node.code.toLowerCase().includes(normalizedQuery) ||
      node.name.toLowerCase().includes(normalizedQuery);

    const filteredChildren = filterTree(node.children, normalizedQuery);
    if (ownMatch || filteredChildren.length > 0) {
      filtered.push({
        ...node,
        children: filteredChildren
      });
    }
  }

  return filtered;
}

const visibleRoots = computed(() => {
  const roots = hideZeroRows.value
    ? filterZeroRows(treeRoots.value, selectedSet.value)
    : treeRoots.value;
  return filterTree(roots, searchQuery.value);
});

const TreeNodeView = defineComponent({
  name: "TreeNodeView",
  props: {
    node: { type: Object as () => TreeNode, required: true },
    selected: { type: Object as () => Set<string>, required: true },
    onToggle: {
      type: Function as () => (node: TreeNode, checked: boolean) => void,
      required: true
    }
  },
  setup(nodeProps) {
    return () =>
      h("li", [
        h("div", { class: "tree-item" }, [
          h("label", [
            h("input", {
              type: "checkbox",
              checked: nodeProps.selected.has(nodeProps.node.code),
              onChange: (event: Event) =>
                nodeProps.onToggle(
                  nodeProps.node,
                  (event.target as HTMLInputElement).checked
                )
            }),
            h("span", { class: "tree-code" }, nodeProps.node.code),
            h("span", { class: "tree-name" }, nodeProps.node.name),
            h("span", { class: "tree-count" }, `(${nodeProps.node.row_count ?? 0})`)
          ])
        ]),
        nodeProps.node.children.length
          ? h(
              "ul",
              { class: "tree-list tree-child" },
              nodeProps.node.children.map((child) =>
                h(TreeNodeView, {
                  key: child.code,
                  node: child,
                  selected: nodeProps.selected,
                  onToggle: nodeProps.onToggle
                })
              )
            )
          : null
      ]);
  }
});
</script>

<template>
  <section class="hierarchy-card">
    <h4>{{ title }}</h4>
    <input
      v-model="searchQuery"
      class="hierarchy-search"
      type="text"
      placeholder="Поиск по коду или названию..."
    />
    <div class="filter-actions">
      <label class="filter-toggle">
        <input v-model="hideZeroRows" type="checkbox" />
        <span>Скрыть строки с нулями</span>
      </label>
      <button class="btn btn-secondary filter-reset-btn" type="button" @click="resetFilter">
        Сбросить фильтр
      </button>
    </div>
    <div class="hierarchy-scroll">
      <ul v-if="visibleRoots.length" class="tree-list">
        <TreeNodeView
          v-for="node in visibleRoots"
          :key="node.code"
          :node="node"
          :selected="selectedSet"
          :on-toggle="toggleNode"
        />
      </ul>
      <p v-else class="empty-state">Ничего не найдено</p>
    </div>
  </section>
</template>
