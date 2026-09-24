<template>
  <section v-if="graph.nodes.length" class="agent-graph" aria-labelledby="agent-graph-title">
    <header class="agent-graph__header">
      <div>
        <p class="agent-graph__eyebrow">实际执行路径</p>
        <h3 id="agent-graph-title">{{ graphTitle }}</h3>
      </div>
      <span class="agent-graph__count">{{ graph.nodes.length }} 个节点</span>
    </header>

    <ol class="agent-graph__path" aria-label="Agent 状态图实际执行节点">
      <li
        v-for="(node, index) in graph.nodes"
        :key="`${node.id}-${index}`"
        class="agent-graph__node"
        :class="`agent-graph__node--${node.status}`"
      >
        <span class="agent-graph__marker" aria-hidden="true">{{ index + 1 }}</span>
        <span class="agent-graph__body">
          <span class="agent-graph__heading">
            <strong>{{ node.label }}</strong>
            <code>{{ node.id }}</code>
          </span>
          <span class="agent-graph__meta">
            <span>{{ statusLabel(node.status) }}</span>
            <span v-if="node.latencyMs != null">{{ formatLatency(node.latencyMs) }}</span>
          </span>
          <span v-if="node.routeLabel" class="agent-graph__route">
            条件路由 · {{ node.routeLabel }}
          </span>
        </span>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  graph: {
    type: Object,
    default: () => ({ name: '', version: '', nodes: [] })
  }
})

const graphTitle = computed(() => {
  const name = props.graph?.name || 'Agent 状态图'
  const version = props.graph?.version ? ` · v${props.graph.version}` : ''
  return `${name}${version}`
})

function statusLabel(status) {
  return status === 'failed' ? '执行失败' : '执行完成'
}

function formatLatency(value) {
  const latency = Number(value)
  if (!Number.isFinite(latency)) return ''
  return latency >= 1000 ? `${(latency / 1000).toFixed(2)} s` : `${latency.toFixed(1)} ms`
}
</script>

<style scoped>
.agent-graph {
  display: grid;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  padding: var(--space-4);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-md);
  background: var(--color-bg-subtle);
}

.agent-graph__header,
.agent-graph__heading,
.agent-graph__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.agent-graph__header {
  justify-content: space-between;
  gap: var(--space-3);
}

.agent-graph__eyebrow {
  margin: 0 0 var(--space-1);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.agent-graph h3 {
  margin: 0;
  color: var(--color-text-strong);
  font-size: 15px;
}

.agent-graph__count,
.agent-graph__meta,
.agent-graph__route {
  color: var(--color-text-muted);
  font-size: 12px;
}

.agent-graph__count {
  padding: 3px 8px;
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-sm);
  background: var(--color-bg-panel);
  font-weight: 700;
}

.agent-graph__path {
  display: flex;
  gap: var(--space-2);
  margin: 0;
  padding: 0 0 var(--space-1);
  overflow-x: auto;
  list-style: none;
  scroll-snap-type: x proximity;
}

.agent-graph__node {
  display: grid;
  flex: 0 0 min(240px, 78vw);
  grid-template-columns: 28px minmax(0, 1fr);
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--color-border-soft);
  border-radius: var(--radius-sm);
  background: var(--color-bg-panel);
  scroll-snap-align: start;
}

.agent-graph__marker {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: var(--radius-sm);
  color: #ffffff;
  background: var(--color-primary);
  font-size: 12px;
  font-weight: 800;
}

.agent-graph__node--failed .agent-graph__marker {
  background: var(--color-danger);
}

.agent-graph__body {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}

.agent-graph__heading,
.agent-graph__meta {
  gap: var(--space-2);
}

.agent-graph__heading strong {
  color: var(--color-text-strong);
  font-size: 13px;
}

.agent-graph__heading code {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
}

.agent-graph__route {
  padding-top: var(--space-1);
  border-top: 1px dashed var(--color-border-soft);
  color: var(--color-primary);
  font-weight: 700;
}

@media (max-width: 640px) {
  .agent-graph {
    padding: var(--space-3);
  }

  .agent-graph__node {
    flex-basis: min(220px, 84vw);
  }
}
</style>
