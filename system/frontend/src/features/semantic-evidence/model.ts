export type SemanticLayer = 'all' | 'posts' | 'comments'

export type SemanticEntity = {
  key: string
  text: string
  label: string
}

export type SemanticRecord = {
  id: string
  layer: Exclude<SemanticLayer, 'all'>
  platform: string
  date: string
  timestamp: string
  keywords: string[]
  topics: string[]
  sentiment: string
  stance: string
  entities: SemanticEntity[]
}

export type SemanticFilters = {
  layer: SemanticLayer
  platforms: string[]
  date: string | null
  keyword: string | null
  topic: string | null
  sentiment: string | null
  stance: string | null
  entity: string | null
}

export type SemanticCount = {
  key: string
  label: string
  count: number
}

export type KeywordCloudItem = {
  term: string
  count: number
  fontSize: number
}

export type KeywordCloudPlacement = KeywordCloudItem & {
  x: number
  y: number
  rotation: number
  left: number
  top: number
  right: number
  bottom: number
}

export type SemanticDisplayField = 'sentiment' | 'stance'

export type SemanticPage = {
  items: SemanticRecord[]
  page: number
  pageSize: number
  total: number
}

export type SemanticCommunitySummary = {
  communityId: string
  memberCount: number
  itemCount: number
  sentiment: Record<string, number>
  stance: Record<string, number>
  keywords: SemanticCount[]
  topics: SemanticCount[]
  entities: SemanticCount[]
}

const CLOUD_MIN_FONT_SIZE = 12
const CLOUD_MAX_FONT_SIZE = 40
const CLOUD_LIMIT = 50

export function createSemanticFilters(): SemanticFilters {
  return {
    layer: 'all',
    platforms: [],
    date: null,
    keyword: null,
    topic: null,
    sentiment: null,
    stance: null,
    entity: null,
  }
}

export function toSemanticRecords(artifact: Record<string, unknown>): SemanticRecord[] {
  const layers = recordValue(artifact.layers)
  return (['posts', 'comments'] as const).flatMap((layer) => arrayValue(layers[layer])
    .map((item) => recordValue(item))
    .map((item, index) => ({
      id: textValue(item.id) || `${layer}-${index}`,
      layer,
      platform: textValue(item.platform) || 'unknown',
      date: textValue(item.timestamp).slice(0, 10) || 'unknown',
      timestamp: textValue(item.timestamp) || 'unknown',
      keywords: arrayValue(item.keywords)
        .map((keyword) => textValue(recordValue(keyword).term))
        .filter(Boolean),
      topics: arrayValue(item.topics)
        .map((topic) => textValue(recordValue(topic).label))
        .filter(Boolean),
      sentiment: textValue(recordValue(item.sentiment).label) || 'unknown',
      stance: textValue(recordValue(item.stance).label) || 'unknown',
      entities: arrayValue(item.entities)
        .map((entity) => recordValue(entity))
        .map((entity) => {
          const text = textValue(entity.text)
          const label = textValue(entity.label) || 'OTHER'
          return { key: `${label}:${text}`, text, label }
        })
        .filter((entity) => Boolean(entity.text)),
    })))
}

export function filterSemanticRecords(
  records: SemanticRecord[],
  filters: SemanticFilters,
): SemanticRecord[] {
  return records.filter((record) => {
    if (filters.layer !== 'all' && record.layer !== filters.layer) return false
    if (filters.platforms.length > 0 && !filters.platforms.includes(record.platform)) return false
    if (filters.date && record.date !== filters.date) return false
    if (filters.keyword && !record.keywords.includes(filters.keyword)) return false
    if (filters.topic && !record.topics.includes(filters.topic)) return false
    if (filters.sentiment && record.sentiment !== filters.sentiment) return false
    if (filters.stance && record.stance !== filters.stance) return false
    if (filters.entity && !record.entities.some((entity) => entity.key === filters.entity)) return false
    return true
  })
}

export function buildKeywordCloud(records: SemanticRecord[]): KeywordCloudItem[] {
  const counts = countNamedValues(records.flatMap((record) => record.keywords))
    .slice(0, CLOUD_LIMIT)
  const minimum = counts[counts.length - 1]?.count || 0
  const maximum = counts[0]?.count || 0
  return counts.map((item) => ({
    term: item.label,
    count: item.count,
    fontSize: logarithmicFontSize(item.count, minimum, maximum),
  }))
}

export function layoutKeywordCloud(
  items: KeywordCloudItem[],
  width: number,
  height: number,
): KeywordCloudPlacement[] {
  const canvasWidth = Math.max(1, Math.floor(width))
  const canvasHeight = Math.max(1, Math.floor(height))

  // Keep every selected top keyword visible on narrow viewports. Retrying with
  // a uniform scale preserves the frequency-derived size ordering.
  let best: KeywordCloudPlacement[] = []
  for (const scale of [1, 0.92, 0.84, 0.76, 0.68, 0.6]) {
    const placements = placeKeywordCloud(
      items.map((item) => ({
        ...item,
        fontSize: Math.max(9, Math.round(item.fontSize * scale)),
      })),
      canvasWidth,
      canvasHeight,
    )
    if (placements.length === items.length) return placements
    if (placements.length > best.length) best = placements
  }

  return best
}

function placeKeywordCloud(
  items: KeywordCloudItem[],
  canvasWidth: number,
  canvasHeight: number,
): KeywordCloudPlacement[] {
  const placements: KeywordCloudPlacement[] = []

  for (const [index, item] of items.entries()) {
    const rotation = cloudRotation(index)
    const bounds = keywordBounds(item, rotation)
    const placement = findKeywordPlacement(
      bounds,
      index,
      canvasWidth,
      canvasHeight,
      placements,
    )
    if (placement) placements.push({ ...item, rotation, ...placement })
  }

  return placements
}

export function buildTopicCounts(records: SemanticRecord[]): SemanticCount[] {
  return countNamedValues(records.flatMap((record) => record.topics))
}

export function buildDistribution(records: SemanticRecord[], field: 'sentiment' | 'stance'): SemanticCount[] {
  return countNamedValues(records.map((record) => record[field]))
}

export function formatDistributionPercent(count: number, total: number): string {
  if (!Number.isFinite(count) || !Number.isFinite(total) || count <= 0 || total <= 0) return '0'
  const percentage = (count / total) * 100
  if (percentage < 0.01) return '<0.01'
  if (percentage < 1) return Number(percentage.toFixed(2)).toString()
  return Math.round(percentage).toString()
}

export function displaySemanticLabel(field: SemanticDisplayField, value: string): string {
  const normalized = value.trim().toLowerCase()
  if (field === 'sentiment') {
    return ({ positive: '正向', negative: '负向', neutral: '中性', unknown: '未判定' } as Record<string, string>)[normalized] || value || '未判定'
  }
  return ({ entailment: '支持', contradiction: '反对', neutral: '中立', unknown: '未判定' } as Record<string, string>)[normalized] || value || '未判定'
}

export function buildEntityCounts(records: SemanticRecord[]): SemanticCount[] {
  const counts = new Map<string, { text: string; label: string; count: number }>()
  for (const entity of records.flatMap((record) => record.entities)) {
    const current = counts.get(entity.key)
    counts.set(entity.key, {
      text: entity.text,
      label: entity.label,
      count: (current?.count || 0) + 1,
    })
  }
  return [...counts.entries()]
    .map(([key, value]) => ({ key, label: value.text, count: value.count, entityType: value.label }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, 'zh-CN'))
    .map(({ key, label, count }) => ({ key, label, count }))
}

export function entityTypeFromKey(value: string): string {
  return value.split(':', 1)[0] || 'OTHER'
}

export function buildTimeCounts(records: SemanticRecord[]): SemanticCount[] {
  return countNamedValues(records.map((record) => record.date)).sort((left, right) => left.label.localeCompare(right.label))
}

export function buildPlatformCounts(records: SemanticRecord[]): SemanticCount[] {
  return countNamedValues(records.map((record) => record.platform))
}

export function paginateSemanticRecords(
  records: SemanticRecord[],
  requestedPage: number,
  pageSize: number,
): SemanticPage {
  const total = records.length
  const maxPage = Math.max(1, Math.ceil(total / pageSize))
  const page = requestedPage > maxPage || requestedPage < 1 ? 1 : requestedPage
  const offset = (page - 1) * pageSize
  return { items: records.slice(offset, offset + pageSize), page, pageSize, total }
}

export function toCommunitySummaries(artifact: Record<string, unknown>): SemanticCommunitySummary[] {
  const crossAnalysis = recordValue(artifact.cross_analysis)
  return arrayValue(crossAnalysis.community_slices)
    .map((item) => recordValue(item))
    .map((item) => ({
      communityId: textValue(item.community_id),
      memberCount: numberValue(item.member_count),
      itemCount: numberValue(item.item_count),
      sentiment: distributionValue(item.sentiment_distribution),
      stance: distributionValue(item.stance_distribution),
      keywords: namedCounts(item.top_keywords, 'term'),
      topics: namedCounts(item.top_topics, 'label'),
      entities: namedCounts(item.top_entities, 'text'),
    }))
    .filter((item) => Boolean(item.communityId))
    .sort((left, right) => right.itemCount - left.itemCount || left.communityId.localeCompare(right.communityId))
}

function countNamedValues(values: string[]): SemanticCount[] {
  const counts = new Map<string, number>()
  for (const value of values) {
    if (!value) continue
    counts.set(value, (counts.get(value) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ key: label, label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, 'zh-CN'))
}

function logarithmicFontSize(value: number, minimum: number, maximum: number): number {
  if (minimum <= 0 || maximum <= 0) return CLOUD_MIN_FONT_SIZE
  if (minimum === maximum) return Math.round((CLOUD_MIN_FONT_SIZE + CLOUD_MAX_FONT_SIZE) / 2)
  const position = (Math.log(value) - Math.log(minimum)) / (Math.log(maximum) - Math.log(minimum))
  return Math.round(CLOUD_MIN_FONT_SIZE + position * (CLOUD_MAX_FONT_SIZE - CLOUD_MIN_FONT_SIZE))
}

const CLOUD_LAYOUT_PADDING = 2
const CLOUD_LAYOUT_GAP = 1
const CLOUD_LAYOUT_MAX_STEPS = 8000
const CLOUD_GOLDEN_ANGLE = 2.399963229728653
const CLOUD_ROTATIONS = [0, 0, -30, 30, 0, 90, 0, -90] as const

function cloudRotation(index: number): number {
  return CLOUD_ROTATIONS[index % CLOUD_ROTATIONS.length]
}

function keywordBounds(item: KeywordCloudItem, rotation: number): { width: number; height: number } {
  const textWidth = estimatedTextWidth(item.term, item.fontSize)
  const textHeight = Math.max(14, item.fontSize * 1.16)
  const radians = Math.abs(rotation) * Math.PI / 180
  return {
    width: Math.ceil(Math.abs(Math.cos(radians)) * textWidth + Math.abs(Math.sin(radians)) * textHeight),
    height: Math.ceil(Math.abs(Math.sin(radians)) * textWidth + Math.abs(Math.cos(radians)) * textHeight),
  }
}

function estimatedTextWidth(text: string, fontSize: number): number {
  const characterWidth = [...text].reduce((sum, character) => (
    sum + (/[\u2e80-\u9fff\uff00-\uffef]/u.test(character) ? 1 : 0.58)
  ), 0)
  return Math.max(fontSize, characterWidth * fontSize)
}

function findKeywordPlacement(
  bounds: { width: number; height: number },
  index: number,
  canvasWidth: number,
  canvasHeight: number,
  placements: KeywordCloudPlacement[],
): Omit<KeywordCloudPlacement, keyof KeywordCloudItem | 'rotation'> | null {
  const centerX = canvasWidth / 2
  const centerY = canvasHeight / 2
  const initialAngle = index * CLOUD_GOLDEN_ANGLE

  for (let step = 0; step < CLOUD_LAYOUT_MAX_STEPS; step += 1) {
    // Pack high-frequency terms at the center, then expand on an elliptical
    // phyllotaxis spiral. The small angular increment avoids the visible rings
    // produced by placing each rank on a precomputed radius.
    const radius = step === 0 ? 0 : 2 + 4.2 * Math.sqrt(step)
    const angle = initialAngle + Math.PI / 2 + step * CLOUD_GOLDEN_ANGLE * 0.38
    const x = Math.round(centerX + radius * 1.14 * Math.cos(angle))
    const y = Math.round(centerY + radius * 0.88 * Math.sin(angle))
    const left = Math.round(x - bounds.width / 2)
    const top = Math.round(y - bounds.height / 2)
    const right = left + bounds.width
    const bottom = top + bounds.height
    const candidate = { x, y, left, top, right, bottom }

    if (
      left < CLOUD_LAYOUT_PADDING
      || top < CLOUD_LAYOUT_PADDING
      || right > canvasWidth - CLOUD_LAYOUT_PADDING
      || bottom > canvasHeight - CLOUD_LAYOUT_PADDING
    ) continue
    if (placements.some((item) => cloudBoundsOverlap(candidate, item))) continue
    return candidate
  }

  return null
}

function cloudBoundsOverlap(
  candidate: { left: number; top: number; right: number; bottom: number },
  placement: KeywordCloudPlacement,
): boolean {
  return !(
    candidate.right + CLOUD_LAYOUT_GAP <= placement.left
    || placement.right + CLOUD_LAYOUT_GAP <= candidate.left
    || candidate.bottom + CLOUD_LAYOUT_GAP <= placement.top
    || placement.bottom + CLOUD_LAYOUT_GAP <= candidate.top
  )
}

function namedCounts(value: unknown, labelKey: string): SemanticCount[] {
  return arrayValue(value)
    .map((item) => recordValue(item))
    .map((item) => ({ key: textValue(item[labelKey]), label: textValue(item[labelKey]), count: numberValue(item.count) }))
    .filter((item) => Boolean(item.label))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, 'zh-CN'))
}

function distributionValue(value: unknown): Record<string, number> {
  const result: Record<string, number> = {}
  for (const [label, count] of Object.entries(recordValue(value))) {
    const normalized = numberValue(count)
    if (normalized > 0) result[label] = normalized
  }
  return result
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function textValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : value === null || value === undefined ? '' : String(value).trim()
}

function numberValue(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}
