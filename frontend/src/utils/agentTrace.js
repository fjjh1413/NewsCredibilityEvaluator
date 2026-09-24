const SKIPPED_STATUSES = new Set(['skipped', 'not_needed', 'disabled'])
const DEGRADED_STATUSES = new Set(['degraded', 'fallback', 'partial', 'retry_exhausted'])
const FAILED_STATUSES = new Set(['error', 'failed', 'fail', 'provider_error'])

const GRAPH_NODE_LABELS = {
  prepare_input: '准备检测输入',
  extract_claims: '抽取关键词与声明',
  retrieve_local_evidence: '检索本地知识库',
  route_web_search: '判断是否联网补证',
  search_web_evidence: '检索网络证据',
  prepare_model_input: '构建模型证据上下文',
  analyze_with_model: '执行模型分析',
  arbitrate_evidence: '仲裁证据质量',
  retry_arbitration: '重试证据仲裁',
  score_risk: '计算可信度与风险',
  persist_result: '持久化检测结果'
}

const GRAPH_ROUTE_LABELS = {
  search: '执行联网搜索',
  skip: '跳过联网搜索',
  retry: '执行一次聚焦重试',
  continue: '继续风险评分'
}

function normalizeStatus(value) {
  const status = String(value || 'completed').toLowerCase()
  if (SKIPPED_STATUSES.has(status)) return 'skipped'
  if (DEGRADED_STATUSES.has(status)) return 'degraded'
  if (FAILED_STATUSES.has(status)) return 'failed'
  if (['pending', 'waiting'].includes(status)) return 'pending'
  if (['running', 'processing', 'active'].includes(status)) return 'running'
  return 'completed'
}

function normalizeLatency(value) {
  const latency = Number(value)
  return Number.isFinite(latency) && latency >= 0 ? latency : null
}

function normalizeStage(stage, index) {
  if (typeof stage === 'string') {
    return {
      id: `legacy-${index + 1}`,
      title: stage,
      description: '',
      decision: '',
      kind: 'step',
      tool: '',
      status: 'completed',
      latencyMs: null,
      metrics: {}
    }
  }

  return {
    id: String(stage?.id || `stage-${index + 1}`),
    title: stage?.title || stage?.name || stage?.step || stage?.label || '未命名步骤',
    description: stage?.summary || stage?.description || stage?.detail || stage?.message || '',
    decision: stage?.decision || '',
    kind: stage?.kind || 'step',
    tool: stage?.tool || '',
    status: normalizeStatus(stage?.status || stage?.state),
    latencyMs: normalizeLatency(stage?.latency_ms ?? stage?.latencyMs),
    metrics: stage?.metrics && typeof stage.metrics === 'object' ? stage.metrics : {}
  }
}

export function normalizeAgentTrace(result = {}) {
  const trace = result?.agent_trace || result?.agentTrace
  const structuredStages = Array.isArray(trace?.stages) ? trace.stages : []
  if (structuredStages.length) {
    return structuredStages.map(normalizeStage)
  }

  const legacySteps = result?.agent_steps || result?.agentSteps || result?.analysis_steps
  return Array.isArray(legacySteps) ? legacySteps.map(normalizeStage) : []
}

export function normalizeAgentGraph(result = {}) {
  const trace = result?.agent_trace || result?.agentTrace
  const execution = trace?.graph_execution || trace?.graphExecution
  const visitedNodes = Array.isArray(execution?.visited_nodes)
    ? execution.visited_nodes
    : Array.isArray(execution?.visitedNodes)
      ? execution.visitedNodes
      : []

  if (!execution || !visitedNodes.length) {
    return { name: '', version: '', nodes: [] }
  }

  const transitions = Array.isArray(execution.transitions) ? execution.transitions : []
  const nodeRuns = Array.isArray(execution.node_runs)
    ? execution.node_runs
    : Array.isArray(execution.nodeRuns)
      ? execution.nodeRuns
      : []
  const transitionBySource = new Map(
    transitions.map((transition) => [transition?.source, transition])
  )
  const runByNode = new Map(
    nodeRuns.map((run) => [run?.node_id || run?.nodeId, run])
  )

  return {
    name: String(execution.graph_name || execution.graphName || ''),
    version: String(execution.version || ''),
    nodes: visitedNodes.map((nodeId) => {
      const id = String(nodeId)
      const run = runByNode.get(id) || {}
      const transition = transitionBySource.get(id) || {}
      const route = String(transition.route || '')
      return {
        id,
        label: GRAPH_NODE_LABELS[id] || id,
        status: normalizeStatus(run.status),
        latencyMs: normalizeLatency(run.latency_ms ?? run.latencyMs),
        route,
        routeLabel: GRAPH_ROUTE_LABELS[route] || route,
        target: String(transition.target || '')
      }
    })
  }
}
