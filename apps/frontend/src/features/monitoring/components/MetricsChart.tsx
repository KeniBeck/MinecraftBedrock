import { useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { cn } from '@/lib/utils'
import type { MetricSample } from '@/stores/monitoring'

type SeriesKey = 'cpu' | 'ram' | 'players' | 'disk'

interface SeriesDef {
  key: SeriesKey
  label: string
  color: string
  /** Formatea el valor mostrado en tooltip/eje (aquí ya es % o nº). */
  format: (value: number) => string
  /** Devuelve el valor en % (0..100) o null si no hay dato. */
  value: (sample: MetricSample) => number | null
}

interface MetricsChartProps {
  data: MetricSample[]
  /** Límites del servidor (resources del detalle) para normalizar a % . */
  ramLimitMb?: number | undefined
  diskLimitGb?: number | undefined
  height?: number | undefined
}

const DEFAULT_VISIBLE: SeriesKey[] = ['cpu', 'ram', 'players']

/** Ticks del eje X cada ~6 muestras (evita saturar la etiqueta). */
function tickEvery(dataLength: number): number {
  if (dataLength <= 20) return 1
  return Math.ceil(dataLength / 8)
}

/**
 * Gráfico de área con Recharts (tema oscuro, gradiente) de las métricas del WS
 * de monitoreo. Las series se normalizan a % respecto a un máximo conocido
 * para que el eje Y sea coherente y no se dispare:
 * - CPU: ya viene en % (0..100).
 * - RAM: `ram_mb / ramLimitMb * 100` (límite del servidor, o 100 % de lo
 *   mayor visto si no hay límite configurado).
 * - Disco: `disk_mb / (diskLimitGb * 1024) * 100`.
 * - Jugadores: `players / players_max * 100`.
 * Curvas `natural` (spline) con `baseValue="dataMin"` para un look fluido y
 * sin "picos rotos" (el área arranca en el mínimo de los datos, no en 0).
 */
export function MetricsChart({
  data,
  ramLimitMb,
  diskLimitGb,
  height = 320,
}: MetricsChartProps) {
  const [visible, setVisible] = useState<SeriesKey[]>(DEFAULT_VISIBLE)

  // Máximo de RAM visto (fallback cuando no hay límite configurado): evita que
  // el % se dispare si `ram_mb` es 0/desconocido.
  const maxRamSeen = useMemo(() => {
    const values = data.map((s) => s.ram_mb).filter((v): v is number => v != null && v > 0)
    return values.length > 0 ? Math.max(...values) : 1
  }, [data])

  const ramCeiling = ramLimitMb && ramLimitMb > 0 ? ramLimitMb : maxRamSeen
  const diskCeiling = diskLimitGb && diskLimitGb > 0 ? diskLimitGb * 1024 : null

  const series: SeriesDef[] = useMemo(
    () => [
      {
        key: 'cpu',
        label: 'CPU',
        color: '#22d3ee',
        format: (v) => `${v.toFixed(1)} %`,
        value: (s) => s.cpu,
      },
      {
        key: 'ram',
        label: 'RAM',
        color: '#a78bfa',
        format: (v) => `${v.toFixed(1)} %`,
        value: (s) => (s.ram_mb != null && ramCeiling > 0 ? (s.ram_mb / ramCeiling) * 100 : null),
      },
      {
        key: 'players',
        label: 'Jugadores',
        color: '#34d399',
        format: (v) => `${v.toFixed(0)} jugadores`,
        value: (s) =>
          s.players_max > 0 && s.players > 0 ? (s.players / s.players_max) * 100 : s.players > 0 ? 100 : 0,
      },
      {
        key: 'disk',
        label: 'Disco',
        color: '#fb923c',
        format: (v) => `${v.toFixed(1)} %`,
        value: (s) =>
          diskCeiling != null && diskCeiling > 0 && s.disk_mb != null
            ? (s.disk_mb / diskCeiling) * 100
            : null,
      },
    ],
    [ramCeiling, diskCeiling],
  )

  const chartData = useMemo(() => {
    type Point = { ts: string; cpu: number | null; ram: number | null; players: number | null; disk: number | null }
    return data.map((sample) => {
      const point: Point = { ts: sample.ts, cpu: null, ram: null, players: null, disk: null }
      for (const s of series) point[s.key] = s.value(sample)
      return point
    })
  }, [data, series])

  const toggle = (key: SeriesKey) => {
    setVisible((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  if (chartData.length === 0) {
    return (
      <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">
        Esperando datos del servidor…
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-2">
        {series.map((s) => {
          const on = visible.includes(s.key)
          return (
            <button
              key={s.key}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(s.key)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-none border px-2.5 py-1 text-xs font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                on
                  ? 'border-white/20 bg-white/10 text-slate-100'
                  : 'border-white/10 bg-transparent text-slate-500',
              )}
            >
              <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </button>
          )
        })}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.4} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="#ffffff14" strokeDasharray="3 3" />
          <XAxis
            dataKey="ts"
            tickFormatter={(ts: string) => new Date(ts).toLocaleTimeString()}
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
            interval={tickEvery(chartData.length)}
          />
          <YAxis
            tickFormatter={(v: number) => `${Math.round(v)} %`}
            domain={[0, 100]}
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip
            labelFormatter={(ts) => (typeof ts === 'string' ? new Date(ts).toLocaleString() : String(ts))}
            formatter={(value, name) => {
              const key = String(name) as SeriesKey
              const def = series.find((s) => s.key === key)
              const num = typeof value === 'number' ? value : Number(value)
              return [def ? def.format(num) : String(value), def ? def.label : String(name)]
            }}
            contentStyle={{
              backgroundColor: '#0f172a',
              border: '1px solid #ffffff22',
              borderRadius: 0,
              fontSize: 12,
            }}
            labelStyle={{ color: '#cbd5e1' }}
          />
          {visible.map((key) => {
            const s = series.find((def) => def.key === key)
            if (!s) return null
            return (
              <Area
                key={s.key}
                type="natural"
                dataKey={s.key}
                name={s.key}
                stroke={s.color}
                strokeWidth={2}
                fill={`url(#grad-${s.key})`}
                baseValue="dataMin"
                connectNulls={false}
              />
            )
          })}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
