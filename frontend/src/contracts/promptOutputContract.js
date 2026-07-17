import promptOutputContract from '../../../contracts/prompt_output_contract.json'

export const PROMPT_OUTPUT_CONTRACT = Object.freeze(promptOutputContract)

export const RISK_LEVEL_OPTIONS = Object.freeze(
  promptOutputContract.risk_levels.map((item) =>
    Object.freeze({
      key: item.key,
      value: item.value,
      label: item.value,
      minScore: item.min_score,
      maxScore: item.max_score,
      range: `${item.min_score}-${item.max_score} 分`,
      description: item.description,
      aliases: item.aliases || []
    })
  )
)

export const HIGH_RISK_LEVEL_OPTIONS = Object.freeze(
  RISK_LEVEL_OPTIONS.filter((item) => item.key !== 'trusted').slice().reverse()
)

const RISK_LEVEL_BY_VALUE = new Map(RISK_LEVEL_OPTIONS.map((item) => [item.value, item]))

function normalizeToken(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
}

export function getRiskLevelMeta(level) {
  const raw = String(level || '').trim()
  if (!raw) {
    return null
  }

  const direct = RISK_LEVEL_BY_VALUE.get(raw)
  if (direct) {
    return direct
  }

  const lowered = raw.toLowerCase()
  const normalized = normalizeToken(raw)
  return (
    RISK_LEVEL_OPTIONS.find((item) =>
      item.aliases.some((alias) => {
        const aliasText = String(alias || '').trim().toLowerCase()
        const aliasToken = normalizeToken(alias)
        return (
          (aliasText && lowered.includes(aliasText)) ||
          (aliasToken && (normalized === aliasToken || normalized.startsWith(`${aliasToken}_`)))
        )
      })
    ) || null
  )
}
