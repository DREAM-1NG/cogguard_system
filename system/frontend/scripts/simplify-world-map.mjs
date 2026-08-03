import { readFile, stat, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const inputPath = resolve('src/assets/world-countries.geojson')
const tolerance = 0.03
const maxBytes = 2_000_000

function squaredSegmentDistance(point, start, end) {
  let x = start[0]
  let y = start[1]
  let dx = end[0] - x
  let dy = end[1] - y
  if (dx || dy) {
    const ratio = ((point[0] - x) * dx + (point[1] - y) * dy) / (dx * dx + dy * dy)
    if (ratio > 1) {
      x = end[0]
      y = end[1]
    } else if (ratio > 0) {
      x += dx * ratio
      y += dy * ratio
    }
  }
  dx = point[0] - x
  dy = point[1] - y
  return dx * dx + dy * dy
}

function simplifyLine(points, squaredTolerance) {
  if (points.length <= 2) return points
  let index = -1
  let maxDistance = squaredTolerance
  for (let cursor = 1; cursor < points.length - 1; cursor += 1) {
    const distance = squaredSegmentDistance(points[cursor], points[0], points.at(-1))
    if (distance > maxDistance) {
      index = cursor
      maxDistance = distance
    }
  }
  if (index === -1) return [points[0], points.at(-1)]
  return [
    ...simplifyLine(points.slice(0, index + 1), squaredTolerance).slice(0, -1),
    ...simplifyLine(points.slice(index), squaredTolerance),
  ]
}

function quantize(position) {
  return position.map((value) => Number(value.toFixed(4)))
}

function simplifyCoordinateSequence(sequence) {
  const closed = sequence.length > 3
    && sequence[0][0] === sequence.at(-1)[0]
    && sequence[0][1] === sequence.at(-1)[1]
  const openSequence = closed ? sequence.slice(0, -1) : sequence
  let simplified = simplifyLine(openSequence, tolerance * tolerance)
  if (closed && simplified.length < 3) simplified = openSequence
  const quantized = simplified.map(quantize)
  if (closed) quantized.push([...quantized[0]])
  return quantized
}

function simplifyCoordinates(value) {
  if (!Array.isArray(value) || value.length === 0) return value
  if (typeof value[0] === 'number') return quantize(value)
  if (Array.isArray(value[0]) && typeof value[0][0] === 'number') {
    return simplifyCoordinateSequence(value)
  }
  return value.map(simplifyCoordinates)
}

const source = JSON.parse(await readFile(inputPath, 'utf8'))
const simplified = {
  ...source,
  cogguard_simplification: {
    algorithm: 'Ramer-Douglas-Peucker',
    tolerance_degrees: tolerance,
    coordinate_precision: 4,
    source: source.name || 'Natural Earth',
  },
  features: source.features.map((feature) => ({
    ...feature,
    geometry: feature.geometry
      ? { ...feature.geometry, coordinates: simplifyCoordinates(feature.geometry.coordinates) }
      : null,
  })),
}

await writeFile(inputPath, `${JSON.stringify(simplified)}\n`, 'utf8')
const outputBytes = (await stat(inputPath)).size
if (outputBytes > maxBytes) {
  throw new Error(`Simplified map is ${outputBytes} bytes; budget is ${maxBytes}`)
}
console.log(`Simplified world map: ${outputBytes} bytes`)
