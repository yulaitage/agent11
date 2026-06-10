import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { MapData } from '../api/chat'

const STATUS_COLORS: Record<string, string> = {
  normal: '#22c55e',
  warning: '#eab308',
  fault: '#ef4444',
  offline: '#6b7280',
  '1': '#22c55e',
  '0': '#ef4444',
}
const STATUS_NAMES: Record<string, string> = {
  normal: 'Normal', warning: 'Warning', fault: 'Fault', offline: 'Offline',
  '1': 'Normal', '0': 'Fault',
}

/** 瓦片源配置：切换此处即可更换地图 */
const TILE_SOURCES: Record<string, string> = {
  // 本地离线瓦片（当前为高德深圳，通过后端 /api/tiles/ 服务）
  local: '/api/tiles/{z}/{x}/{y}.png',
  // 高德地图在线（中国可用，无需 API Key，主要显示街道）
  amap: 'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
}

// 切换: 'local'（离线） | 'amap'（在线）
const TILE_SOURCE: string = 'local'
function getTileUrl(): string { return TILE_SOURCES[TILE_SOURCE] || TILE_SOURCES.local }

function createIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:16px;height:16px;border-radius:50%;
      background:${color};border:2px solid #fff;
      box-shadow:0 1px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })
}

export default function DeviceMap({ mapData }: { mapData: MapData }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const amapFallbackRef = useRef(false)

  const { center = [22.54, 114.06], zoom = 14, markers = [], legend } = mapData

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return

    const map = L.map(containerRef.current, {
      center: center as [number, number],
      zoom,
      zoomControl: true,
      attributionControl: false,
    })

    // 使用本地瓦片（后端服务 /api/tiles/）
    const localTiles = L.tileLayer(getTileUrl(), { maxZoom: 18 })
    localTiles.addTo(map)
    // 如果本地瓦片 404，回退到高德在线瓦片
    localTiles.on('tileerror', () => {
      if (!mapRef.current || amapFallbackRef.current) return
      amapFallbackRef.current = true
      L.tileLayer(TILE_SOURCES.amap, { maxZoom: 18 }).addTo(map)
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [center, zoom])

  // Update markers when data changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Clear existing markers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        map.removeLayer(layer)
      }
    })

    if (markers.length === 0) return

    const bounds = L.latLngBounds([])
    const markerGroup = L.featureGroup()

    markers.forEach((mk) => {
      const color = STATUS_COLORS[mk.status] || '#3b82f6'
      const statusName = STATUS_NAMES[mk.status] || mk.status
      const popupContent = `
        <div style="font-size:12px;line-height:1.5">
          <b>${mk.popup || mk.device_id}</b><br/>
          ID: ${mk.device_id}<br/>
          Status: <span style="color:${color}">${statusName}</span><br/>
          (${mk.lat.toFixed(4)}, ${mk.lng.toFixed(4)})
        </div>
      `
      const marker = L.marker([mk.lat, mk.lng], { icon: createIcon(color) })
        .bindPopup(popupContent)
      markerGroup.addLayer(marker)
      bounds.extend([mk.lat, mk.lng])
    })

    markerGroup.addTo(map)

    if (markers.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: zoom })
    }
  }, [markers, zoom])

  return (
    <div className="mt-3">
      <div className="flex items-center gap-3 mb-1.5 text-xs text-slate-500">
        <span>📍 Device Locations ({markers.length})</span>
        {legend && Object.entries(legend).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
      <div ref={containerRef} className="w-full h-80 rounded-lg border border-slate-200 z-0" />
    </div>
  )
}
