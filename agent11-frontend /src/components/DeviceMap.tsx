import { useEffect, useRef } from 'react'
import type { MapData } from '../api/chat'

const STATUS_COLORS: Record<string, string> = {
  normal: '#22c55e',
  warning: '#facc15',
  fault: '#ef4444',
  offline: '#6b7280',
  '1': '#22c55e',
  '0': '#ef4444',
}

/** 简单的 Canvas 地图组件（无需外部依赖） */
export default function DeviceMap({ mapData }: { mapData: MapData }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const { center, zoom = 14, markers = [], legend } = mapData

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || markers.length === 0) return

    const container = containerRef.current
    if (!container) return

    const dpr = window.devicePixelRatio || 1
    const rect = container.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    canvas.style.width = rect.width + 'px'
    canvas.style.height = rect.height + 'px'
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.scale(dpr, dpr)
    const w = rect.width
    const h = rect.height

    // Background
    ctx.fillStyle = '#f0f4f8'
    ctx.fillRect(0, 0, w, h)

    // Grid lines
    ctx.strokeStyle = '#e2e8f0'
    ctx.lineWidth = 1
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
    }

    if (markers.length === 0) return

    // Calculate bounds
    const lats = markers.map(m => m.lat)
    const lngs = markers.map(m => m.lng)
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLng = Math.min(...lngs)
    const maxLng = Math.max(...lngs)

    const padding = 40
    const mapW = w - padding * 2
    const mapH = h - padding * 2
    const latRange = maxLat - minLat || 1
    const lngRange = maxLng - minLng || 1

    const scale = Math.min(mapW / lngRange, mapH / latRange) * 0.8

    const centerX = w / 2
    const centerY = h / 2

    function toScreen(lat: number, lng: number): [number, number] {
      const x = centerX + (lng - (minLng + maxLng) / 2) * scale
      const y = centerY - (lat - (minLat + maxLat) / 2) * scale
      return [x, y]
    }

    // Draw markers
    markers.forEach((marker) => {
      const [x, y] = toScreen(marker.lat, marker.lng)
      const color = STATUS_COLORS[marker.status] || '#3b82f6'
      const radius = 8

      // Glow
      ctx.beginPath()
      ctx.arc(x, y, radius + 3, 0, Math.PI * 2)
      ctx.fillStyle = color + '30'
      ctx.fill()

      // Circle
      ctx.beginPath()
      ctx.arc(x, y, radius, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()

      // Label
      ctx.fillStyle = '#1e293b'
      ctx.font = '10px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(marker.device_id.slice(-4), x, y + radius + 14)
    })

    // Legend
    if (legend) {
      let ly = 10
      ctx.font = '11px sans-serif'
      for (const [label, color] of Object.entries(legend)) {
        ctx.fillStyle = color
        ctx.fillRect(10, ly, 10, 10)
        ctx.fillStyle = '#475569'
        ctx.textAlign = 'left'
        ctx.fillText(label, 24, ly + 9)
        ly += 18
      }
    }
  }, [markers, center, zoom])

  if (markers.length === 0) {
    return (
      <div className="mt-3 p-4 bg-slate-50 rounded-lg border border-slate-200 text-center text-sm text-slate-400">
        No location data available
      </div>
    )
  }

  return (
    <div className="mt-3">
      <div ref={containerRef} className="w-full h-64 rounded-lg overflow-hidden border border-slate-200 relative">
        <canvas ref={canvasRef} className="w-full h-full" />
        <div className="absolute top-2 right-2 bg-white/90 rounded px-2 py-1 text-[10px] text-slate-500 shadow-sm">
          {markers.length} device{markers.length > 1 ? 's' : ''}
        </div>
      </div>
    </div>
  )
}
