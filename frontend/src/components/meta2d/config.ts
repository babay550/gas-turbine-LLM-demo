// ============================================================
// Gas Turbine Schematic — Layout, SCADA mapping, Status colors
// ============================================================

export interface ScadaParamDef {
  key: string
  label: string
  unit: string
  normalRange: [number, number]
}

export interface ComponentDef {
  id: string
  label: string
  subtitle: string
  x: number
  y: number
  width: number
  height: number
  defaultFill: string
  defaultStroke: string
  textColor: string
  scadaParams: ScadaParamDef[]
}

export interface ConnectionDef {
  id: string
  fromId: string
  toId: string
  label: string
  animateType: number
  animateColor: string
}

// ---- Component layout ----

export const COMPONENTS: ComponentDef[] = [
  {
    id: 'compressor',
    label: '压气机',
    subtitle: 'Compressor',
    x: 40, y: 50, width: 160, height: 110,
    defaultFill: '#e6f7ff',
    defaultStroke: '#409eff',
    textColor: '#409eff',
    scadaParams: [
      { key: '压气机进口温度_T1', label: '进口温度 T1', unit: '°C', normalRange: [10, 40] },
      { key: '压气机进口压力_P1', label: '进口压力 P1', unit: 'MPa', normalRange: [0.09, 0.11] },
      { key: '压气机出口温度_T2', label: '出口温度 T2', unit: '°C', normalRange: [350, 480] },
      { key: '压气机出口压力_P2', label: '出口压力 P2', unit: 'MPa', normalRange: [1.2, 2.0] },
      { key: '空气流量', label: '空气流量', unit: 'kg/s', normalRange: [450, 750] },
    ],
  },
  {
    id: 'combustion',
    label: '燃烧室',
    subtitle: 'Combustor',
    x: 280, y: 40, width: 180, height: 130,
    defaultFill: '#fff7e6',
    defaultStroke: '#e6a23c',
    textColor: '#e6a23c',
    scadaParams: [
      { key: '透平进口温度_T3', label: '透平进口温度 T3', unit: '°C', normalRange: [1000, 1400] },
      { key: '燃烧室出口压力_P3', label: '出口压力 P3', unit: 'MPa', normalRange: [1.2, 1.9] },
      { key: '天然气瞬时流量', label: '天然气流量', unit: '万Nm³/h', normalRange: [4.0, 6.5] },
      { key: '排烟含氧量', label: '排烟含氧量', unit: '%', normalRange: [10, 18] },
      { key: 'CO排放', label: 'CO 排放', unit: 'ppm', normalRange: [0, 50] },
    ],
  },
  {
    id: 'turbine',
    label: '透平',
    subtitle: 'Turbine',
    x: 540, y: 50, width: 160, height: 110,
    defaultFill: '#fef0f0',
    defaultStroke: '#f56c6c',
    textColor: '#f56c6c',
    scadaParams: [
      { key: '透平出口温度_T4', label: '出口温度 T4', unit: '°C', normalRange: [480, 600] },
      { key: '透平出口压力_P4', label: '出口压力 P4', unit: 'MPa', normalRange: [0.08, 0.12] },
    ],
  },
  {
    id: 'generator',
    label: '发电机',
    subtitle: 'Generator',
    x: 780, y: 50, width: 140, height: 110,
    defaultFill: '#f0f9eb',
    defaultStroke: '#67c23a',
    textColor: '#67c23a',
    scadaParams: [
      { key: '发电机有功功率', label: '有功功率', unit: 'MW', normalRange: [150, 230] },
    ],
  },
]

// ---- Connection lines ----

export const CONNECTIONS: ConnectionDef[] = [
  { id: 'line-air', fromId: 'compressor', toId: 'combustion', label: '压缩空气', animateType: 0, animateColor: '#409eff' },
  { id: 'line-gas', fromId: 'combustion', toId: 'turbine', label: '高温燃气', animateType: 0, animateColor: '#f56c6c' },
  { id: 'line-work', fromId: 'turbine', toId: 'generator', label: '机械功', animateType: 3, animateColor: '#67c23a' },
]

// ---- Status colors ----

export const STATUS_COLORS: Record<string, { fill: string; stroke: string }> = {
  warning: { fill: '#fdf6ec', stroke: '#e6a23c' },
  alarm: { fill: '#fef0f0', stroke: '#f56c6c' },
}

// ---- Polling ----

export const POLL_INTERVAL = 10_000
