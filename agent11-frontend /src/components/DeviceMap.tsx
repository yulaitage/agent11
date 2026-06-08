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

/** 高德地图瓦片 URL（中国可用，无需 API Key） */
const AMAP_TILES = 'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}'
/** 离线/本地瓦片 URL（如用 TileServer 自建） */
const LOCAL_TILES = '/tiles/{z}/{x}/{y}.png'

function getTileUrl(): string {
  // 优先使用本地瓦片（离线部署），否则用高德在线瓦片
  return LOCAL_TILES
}

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

  const { center = [22.54, 114.06], zoom = 14, markers = [], legend } = mapData

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return

    const map = L.map(containerRef.current, {
      center: center as [number, number],
      zoom,
      zoomControl: true,
      attributionControl: false,
    })

    // Try local tiles first, fall back to Amap tiles
    const tileLayer = L.tileLayer(getTileUrl(), {
      maxZoom: 18,
      errorTileUrl: '',
    })
    tileLayer.addTo(map)

    // If local tiles fail (404), fall back to Amap tiles
    tileLayer.on('tileerror', () => {
      if (!mapRef.current) return
      L.tileLayer(AMAP_TILES, { maxZoom: 18 }).addTo(map)
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
