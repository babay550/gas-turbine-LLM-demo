<script setup lang="ts">
import { computed } from 'vue'
import { realtimeStore, warningStore } from '../../stores'
import { COMPONENTS, CONNECTIONS, STATUS_COLORS } from './config'
import type { ComponentDef } from './config'
import type { Warning } from '../../types'

const emit = defineEmits<{ select: [id: string] }>()

// ---- Status computation ----

function getComponentStatus(
  comp: ComponentDef,
  params: Record<string, number>,
  warnings: Warning[],
): 'normal' | 'warning' | 'alarm' {
  const paramKeys = comp.scadaParams.map(p => p.key)
  const compWarnings = warnings.filter(w =>
    paramKeys.some(k => w.parameter === k || w.message?.includes(comp.label)),
  )
  if (compWarnings.some(w => w.level === 'high')) return 'alarm'
  if (compWarnings.some(w => w.level === 'medium')) return 'warning'

  for (const p of comp.scadaParams) {
    const val = params[p.key]
    if (val == null) continue
    const [lo, hi] = p.normalRange
    const margin = (hi - lo) * 0.15
    if (val < lo - margin || val > hi + margin) return 'alarm'
    if (val < lo || val > hi) return 'warning'
  }
  return 'normal'
}

// ---- Computed styles per component ----

interface CompStyle {
  fill: string
  stroke: string
  status: string
}

const compStyles = computed<Record<string, CompStyle>>(() => {
  const params = realtimeStore.data?.parameters ?? {}
  const result: Record<string, CompStyle> = {}

  for (const comp of COMPONENTS) {
    const status = getComponentStatus(comp, params, warningStore.list as Warning[])
    if (status === 'normal') {
      result[comp.id] = { fill: comp.defaultFill, stroke: comp.defaultStroke, status }
    } else {
      result[comp.id] = {
        fill: STATUS_COLORS[status].fill,
        stroke: STATUS_COLORS[status].stroke,
        status,
      }
    }
  }
  return result
})

// ---- Layout constants (SVG viewBox 960x220) ----

const viewBox = '0 0 960 220'

// Connection line segments (from right-center of source to left-center of target)
function lineX1(fromId: string) {
  const c = COMPONENTS.find(x => x.id === fromId)!
  return c.x + c.width
}
function lineY(fromId: string) {
  const c = COMPONENTS.find(x => x.id === fromId)!
  return c.y + c.height / 2
}
function lineX2(toId: string) {
  const c = COMPONENTS.find(x => x.id === toId)!
  return c.x
}
function labelX(fromId: string, toId: string) {
  const f = COMPONENTS.find(x => x.id === fromId)!
  const t = COMPONENTS.find(x => x.id === toId)!
  return f.x + f.width + (t.x - f.x - f.width) / 2
}
</script>

<template>
  <div class="schematic-wrapper">
    <svg :viewBox="viewBox" class="schematic-svg">
      <defs>
        <!-- Animated flow pattern -->
        <marker id="arrow-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#409eff" />
        </marker>
        <marker id="arrow-red" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#f56c6c" />
        </marker>
        <marker id="arrow-green" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#67c23a" />
        </marker>

        <!-- Glow filter for hover -->
        <filter id="hover-glow" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <!-- Warning pulse filter -->
        <filter id="warn-pulse" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <!-- Connection lines with flow animation -->
      <g v-for="conn in CONNECTIONS" :key="conn.id">
        <line
          :x1="lineX1(conn.fromId)"
          :y1="lineY(conn.fromId)"
          :x2="lineX2(conn.toId)"
          :y2="lineY(conn.toId)"
          :stroke="conn.animateColor"
          stroke-width="3"
          :marker-end="`url(#arrow-${conn.animateColor === '#409eff' ? 'blue' : conn.animateColor === '#f56c6c' ? 'red' : 'green'})`"
          class="flow-line"
          :style="{ '--flow-color': conn.animateColor }"
        />
        <!-- Flow label -->
        <text
          :x="labelX(conn.fromId, conn.toId)"
          y="28"
          text-anchor="middle"
          :fill="conn.animateColor"
          font-size="11"
          font-weight="500"
        >
          {{ conn.label }}
        </text>
      </g>

      <!-- Component groups (clickable) -->
      <g
        v-for="comp in COMPONENTS"
        :key="comp.id"
        class="component-group"
        @click="emit('select', comp.id)"
        :filter="compStyles[comp.id]?.status !== 'normal' ? 'url(#warn-pulse)' : undefined"
      >
        <rect
          :x="comp.x"
          :y="comp.y"
          :width="comp.width"
          :height="comp.height"
          rx="12"
          :fill="compStyles[comp.id]?.fill ?? comp.defaultFill"
          :stroke="compStyles[comp.id]?.stroke ?? comp.defaultStroke"
          stroke-width="2"
          class="comp-rect"
        />
        <!-- Status indicator dot -->
        <circle
          v-if="compStyles[comp.id]?.status !== 'normal'"
          :cx="comp.x + comp.width - 14"
          :cy="comp.y + 14"
          r="5"
          :fill="compStyles[comp.id]?.status === 'alarm' ? '#f56c6c' : '#e6a23c'"
          class="status-dot"
        />
        <text
          :x="comp.x + comp.width / 2"
          :y="comp.y + comp.height / 2 - 8"
          text-anchor="middle"
          :fill="compStyles[comp.id]?.stroke ?? comp.textColor"
          font-size="14"
          font-weight="600"
        >
          {{ comp.label }}
        </text>
        <text
          :x="comp.x + comp.width / 2"
          :y="comp.y + comp.height / 2 + 10"
          text-anchor="middle"
          fill="#909399"
          font-size="11"
        >
          {{ comp.subtitle }}
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.schematic-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 4px 0;
}

.schematic-svg {
  width: 100%;
  max-width: 960px;
  height: auto;
}

/* Flow animation - moving dashes */
.flow-line {
  stroke-dasharray: 10 6;
  animation: flow-anim 0.8s linear infinite;
}

@keyframes flow-anim {
  to {
    stroke-dashoffset: -16;
  }
}

/* Component hover & click */
.component-group {
  cursor: pointer;
  transition: opacity 0.15s;
}

.component-group:hover {
  opacity: 0.85;
}

.component-group:hover .comp-rect {
  stroke-width: 3;
  filter: url(#hover-glow);
}

.component-group:active {
  opacity: 0.7;
}

/* Warning pulse animation */
.status-dot {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; r: 5; }
  50% { opacity: 0.5; r: 7; }
}
</style>
