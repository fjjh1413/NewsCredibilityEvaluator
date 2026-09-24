import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizeAgentGraph, normalizeAgentTrace } from './agentTrace.js'

test('normalizes structured agent trace stages and preserves audit metadata', () => {
  const stages = normalizeAgentTrace({
    agent_trace: {
      version: '1.0',
      status: 'degraded',
      total_latency_ms: 245.6,
      stages: [
        {
          id: 'route_web_search',
          title: '路由联网补证',
          kind: 'decision',
          tool: 'bocha_web_search',
          status: 'skipped',
          latency_ms: 0.4,
          decision: '本地证据已满足阈值。',
          summary: '未调用联网搜索。',
          metrics: { source_count: 0 }
        }
      ]
    },
    agent_steps: ['兼容步骤']
  })

  assert.deepEqual(stages, [
    {
      id: 'route_web_search',
      title: '路由联网补证',
      description: '未调用联网搜索。',
      decision: '本地证据已满足阈值。',
      kind: 'decision',
      tool: 'bocha_web_search',
      status: 'skipped',
      latencyMs: 0.4,
      metrics: { source_count: 0 }
    }
  ])
})

test('falls back to legacy agent step strings', () => {
  assert.deepEqual(
    normalizeAgentTrace({ agent_steps: ['关键词提取完成', '规则评分完成'] }),
    [
      {
        id: 'legacy-1',
        title: '关键词提取完成',
        description: '',
        decision: '',
        kind: 'step',
        tool: '',
        status: 'completed',
        latencyMs: null,
        metrics: {}
      },
      {
        id: 'legacy-2',
        title: '规则评分完成',
        description: '',
        decision: '',
        kind: 'step',
        tool: '',
        status: 'completed',
        latencyMs: null,
        metrics: {}
      }
    ]
  )
})

test('normalizes the actual graph path and conditional routes', () => {
  const graph = normalizeAgentGraph({
    agent_trace: {
      graph_execution: {
        version: '1.0',
        graph_name: 'evidence-investigation-agent',
        visited_nodes: ['prepare_input', 'route_web_search', 'search_web_evidence'],
        transitions: [
          { source: 'prepare_input', target: 'route_web_search', route: null },
          { source: 'route_web_search', target: 'search_web_evidence', route: 'search' }
        ],
        node_runs: [
          { node_id: 'prepare_input', status: 'completed', latency_ms: 0.2 },
          { node_id: 'route_web_search', status: 'completed', latency_ms: 0.4 },
          { node_id: 'search_web_evidence', status: 'completed', latency_ms: null }
        ]
      }
    }
  })

  assert.equal(graph.name, 'evidence-investigation-agent')
  assert.equal(graph.nodes.length, 3)
  assert.deepEqual(graph.nodes[1], {
    id: 'route_web_search',
    label: '判断是否联网补证',
    status: 'completed',
    latencyMs: 0.4,
    route: 'search',
    routeLabel: '执行联网搜索',
    target: 'search_web_evidence'
  })
})

test('returns an empty graph for legacy results', () => {
  assert.deepEqual(normalizeAgentGraph({ agent_steps: ['兼容步骤'] }), {
    name: '',
    version: '',
    nodes: []
  })
})
