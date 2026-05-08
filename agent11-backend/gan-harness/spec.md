# Product Specification: AGENT 11 Backend

> Generated from brief: "Build a LangChain-based backend agent for agent11 frontend, implementing all features from AGENT 11 PRD v2.0"

## Vision

AGENT 11 Backend is a **LangChain-powered reasoning agent** that transforms raw infrastructure data (streetlights, water pipes, bridges) into actionable intelligence. It thinks step-by-step, consults domain knowledge bases, and returns structured answers — not just LLM text. The backend exposes a skill-based API where each skill is a dedicated agent subgraph. It handles both pre-parsed metrics AND raw binary protocol data that it decodes on-the-fly using hardware protocol definition files.

## Design Direction

- **API Style**: REST + JSON, OpenAI-compatible chat completions endpoint
- **Response Format**: Structured JSON with `answer`, `reasoning_chain`, `confidence`, `sources`, `actions`, `data`
- **Error Handling**: Consistent error envelope `{ error: string, code: string, details?: object }`
- **Documentation**: OpenAPI 3.1 spec auto-generated from FastAPI
- **Logging**: Structured JSON logs with correlation IDs for tracing
- **Protocol Parsing**: Raw binary data decoded via user-uploaded protocol definition files (JSON/YAML)

## Features (Prioritized)

### Must-Have (Sprint 1-2)

#### 1. Skill Router (`POST /api/chats/{chat_id}/messages`)
- Route incoming messages to correct skill agent based on `skill` field
- Skills: `query`, `failure_troubleshoot`, `maintenance_report`, `prediction`, `flexible_report`
- Frontend sends `{ message, skill }`, backend returns structured `{ answer, reasoning_chain, data }`

#### 2. Query Skill — Two-Mode Data Query

**Mode A: Parsed Data Query**
- Natural language → SQL → execute → return results
- Domain vocabulary mapping: "路灯" → `streetlights`, "故障" → `status = 'fault'`
- Fields: power, current, voltage, energy consumption, status, geozone, device type
- Filters: by geozone, time range, device type, status
- Output: Tabular data + natural language summary

**Mode B: Raw Protocol Data Parsing**
- When query references unparsed binary data (data strings)
- System has access to hardware **Protocol Definition Files** (uploaded by users)
- AI parses binary data strings according to protocol spec → outputs human-readable values
- Protocol formats supported: Modbus RTU/TCP register maps, custom JSON/YAML definitions
- Example: Raw `0x01 0x03 0x02 0x00 0xC8 ...` → `{ register: 40001, value: 200, unit: "kWh" }`
- Protocol definitions stored in knowledge base, retrieved at query time

#### 3. Failure Troubleshoot Skill — Temporal Diagnostic Reasoning

**Core capability**: Correlate multiple data streams over time to diagnose root causes.

**Reasoning patterns the AI must handle**:

| Symptom | Diagnostic Logic |
|---------|-----------------|
| Controller comm lost + lights still ON + energy consumption continues | Controller hardware failure (not comm network issue) |
| Controller comm intermittent + lights ON + energy steady | Communication network instability |
| Single light flickering | Check: driver fault, bulb age, voltage fluctuation |
| Multiple lights flickering in same area | Grid voltage fluctuation or power supply issue |
| No comm + no energy + lights off | Power supply outage to that controller |

**Input**: Symptom description (e.g., "100 devices across different streets report 'communication lost'")
**Output**:
```
root_causes: [
  {
    rank: 1,
    cause: "Controller hardware failure",
    devices: ["CTRL-A", "CTRL-B"],
    evidence: [
      "CTRL-A: No comm for 7 days, but lights ON and energy consumption continues (indicates controller dead, not power issue)",
      "CTRL-B: Similar pattern confirmed across 3 other controllers in same grid segment"
    ],
    confidence: 0.87,
    recommendation: "Replace controller A and B; check grid segment for underlying power quality issues"
  },
  {
    rank: 2,
    cause: "Communication network instability",
    devices: ["CTRL-C", "CTRL-D"],
    evidence: [
      "CTRL-C: Intermittent online/offline pattern over 2 weeks",
      "CTRL-D: Same pattern; both connected to same switch"
    ],
    confidence: 0.72,
    recommendation: "Check network switch and fiber connection to this segment"
  }
]
reasoning_chain: [
  { step: 1, action: "Queried all devices with 'communication lost' status", observation: "Found 100 devices across geozones 12, 34, 55" },
  { step: 2, action: "Cross-referenced each device's energy consumption data for past 30 days", observation: "23 devices still consuming energy despite no comm" },
  { step: 3, action: "Checked comm log timestamps for devices with energy but no comm", observation: "CTRL-A last comm 7 days ago, energy pattern unchanged → controller dead" },
  { step: 4, action: "Grouped remaining 77 devices by network topology", observation: "12 devices share same network switch with intermittent issues → network issue" }
]
```

**Required data access**:
- Device status (online/offline/comm_lost)
- Energy consumption time series (per device, per hour/day)
- Communication log (timestamped events)
- Grid topology / network segment mapping
- Historical maintenance records

#### 4. Prediction Skill — Failure & Energy Forecasting

**Failure Prediction**:
- Input: "Predict which streetlights may fail in next 24 hours / 7 days / 30 days"
- Analyze: power factor drift, flicker frequency, energy anomalies, aging curves
- Output:
```
predictions: [
  {
    device_id: "LIGHT-55-A001",
    geozone: "Zone 55",
    risk_score: 0.82,
    time_horizon: "24h",
    confidence: [0.75, 0.90],
    factors: [
      "Power factor dropped from 0.95 to 0.78 over past 3 days",
      "Flickering events detected 12 times yesterday (threshold: 5)",
      "Running at 82% of rated power — approaching failure threshold"
    ],
    recommendation: "Schedule preventive maintenance within 48 hours"
  }
]
prediction_summary: {
  total_devices_monitored: 5420,
  high_risk_24h: 23,
  high_risk_7d: 87,
  high_risk_30d: 234,
  top_failure_types: { "driver_failure": 45, "grid_overvoltage": 32, "cable_fault": 10 }
}
```

**Energy Prediction**:
- Input: "Predict energy consumption for zone 55 in next 3 months"
- Factors: historical consumption, weather, holidays, daylight hours, special events
- Output: consumption curve with confidence bands + anomaly detection

#### 5. Maintenance Report Skill — Templated Periodic Reports

**Report Types**:
- Weekly operation report
- Monthly management report
- Annual summary report

**Standard Metrics in Reports**:
- Total energy consumption (kWh) — city-wide and per geozone
- Fault statistics: count by type (comm loss, power failure, lamp failure, flicker)
- Fault distribution: by geozone, by device type, by time period
- Fault response time: avg time from fault detection to resolution
- Maintenance actions completed: count and types
- Availability: uptime percentage per device and per geozone
- 节能成效: energy savings vs previous period
- **Map visualization**: Report includes map showing device locations, fault locations, geozone boundaries

**Output Formats**: PDF (formatted report with embedded map), Excel (raw data tables), JSON (structured data)

#### 5b. Chat Map Component — Inline Device Location Map

**Reference UI**: GovCity Platform — map-centric infrastructure management with AI chat panel

**Visual Design** (per reference video):
```
┌─────────────────────────────────────────────────────────────┐
│  Top Nav: Dashboard | Streetlight | Fault | Energy | Report │
├────────────────────────────────────┬────────────────────────┤
│                                    │  Device Detail Panel   │
│         GIS Map                    │  - ID, Name, Status   │
│    (device markers + geozones)     │  - Voltage/Current/PF │
│                                    │  - Energy charts      │
│                                    │  - Controller ID     │
├────────────────────────────────────┴────────────────────────┤
│  AI Agent Chat Panel (bottom-right)                        │
│  ┌──────────────────────────────────────────────┐          │
│  │ "What can I help you"                       │          │
│  │ ─────────────────────────────────────────── │          │
│  │ Agent response with analysis...             │          │
│  │ Map markers updated to highlight devices     │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

**Marker Status Colors**:
- Blue: Normal
- Orange/Warning: Warning state
- Red: Fault
- Markers clickable → show device details

**Backend returns** `map_data` in response:
```json
{
  "answer": "Found 23 faulted streetlights in Zone 55",
  "map_data": {
    "center": [latitude, longitude],
    "zoom": 14,
    "markers": [
      {
        "device_id": "LIGHT-55-A001",
        "lat": 30.123,
        "lng": -119.456,
        "status": "fault",
        "popup": "Fault: Power Outage",
        "info": { "voltage": 240, "current": 0.0, "power": 0.0 }
      }
    ],
    "highlight_geozones": ["55"],
    "legend": { "fault": "#ef4444", "warning": "#f97316", "normal": "#3b82f6" }
  }
}
```

**Frontend Integration**:
- Agent response includes `map_data` → map auto-pans/zooms to relevant area
- Markers update to reflect queried devices
- Clicking marker shows device detail card (side panel or modal)
- When >50 markers, use marker clustering
- Geozone boundaries rendered as polygons

**Map Provider**:
- Default: OpenStreetMap via Leaflet (no API key required)
- Air-gapped: self-hosted tile server
- Optional: Mapbox/Google Maps with token

#### 6. Flexible Report Skill — Ad-hoc Data Query & Visualization

**Core capability**: User describes any data they want → system queries + formats

**Examples**:
- "List all streetlights with zero consumption this week" → table
- "Show me energy consumption trends by geozone for the past month" → chart data
- "Compare fault rates between Zone 12 and Zone 34" → comparison table + chart
- "Which devices have had more than 5 faults in 30 days?" → prioritized list

**Output Formats**: Table (HTML/Excel), Chart (PNG/base64), Dashboard summary

#### 7. Knowledge Base — ChromaDB Vector Store

**Knowledge Types**:
- Fault diagnosis knowledge: symptoms → root causes → fix procedures
- Equipment manuals and protocol definition files (for raw data parsing)
- Maintenance logs and historical resolution patterns
- Grid topology and network segment data
- Device specifications and datasheets

**Operations**: Add document, semantic search, delete document, update metadata

#### 8. Skill Management Module — Plugin Architecture

- Each protocol/system = one skill plugin
- Dynamic loading via Python entry points
- Skills: `modbus_skill`, `mqtt_skill`, `bacnet_skill`, `opc_skill`, `http_api_skill`

### Should-Have (Sprint 3-4)

#### 9. Dual Confirmation Mechanism
- Any control action requires user confirmation in two steps
- Write operations isolated from read operations
- Audit log for all operations

#### 10. Protocol Adapter Framework
- Read data from Modbus/BACnet/MQTT/OPC DA/OPC UA
- Convert raw bytes to human-readable values using uploaded protocol definitions
- Simulation mode for testing

### Nice-to-Have (Sprint 5+)

#### 11. Digital Twin Simulation
- Pre-execute control actions in simulated environment
- Observe predicted outcomes before real deployment

## Technical Stack

| Layer | Technology |
|-------|------------|
| API Framework | FastAPI (Python 3.11+) |
| Agent Framework | LangChain / LangGraph |
| Vector Store | ChromaDB |
| SQL Engine | SQLAlchemy 2.0 + SQLite (dev) / PostgreSQL (prod) |
| Local LLM | Ollama (qwen2.5vl:7b, llama3.2) or LocalAI |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| ML Forecasting | scikit-learn, prophet |
| Protocol Parsing | custom struct/binary parser + user-uploaded YAML/JSON specs |
| PDF Export | reportlab, weasyprint |
| Excel Export | openpyxl |
| Charting | matplotlib, plotly |
| Container | Docker + Docker Compose |

## API Endpoints

```
POST /api/chats/{chat_id}/messages
  Body: { message: string, skill: SkillType }
  Response: { chat_id, message: { role, content, timestamp, reasoning_chain?, data?, confidence? } }

GET  /api/chats
POST /api/chats
GET  /api/chats/{chat_id}
DELETE /api/chats/{chat_id}

GET  /api/knowledge
POST /api/knowledge              # upload protocol file or fault knowledge
DELETE /api/knowledge/{doc_id}

GET  /api/skills               # list available skills
POST /api/skills/{skill_name}/run

GET  /api/protocols            # list uploaded protocol definitions
POST /api/protocols            # upload protocol definition file
GET  /api/protocols/{protocol_id}/parse  # test raw data parsing

POST /api/reports/maintenance  # generate templated maintenance report
  Body: { report_type: "weekly"|"monthly"|"annual", geozone?, start_date, end_date, format: "pdf"|"excel"|"json" }

POST /api/reports/flexible     # generate ad-hoc report
  Body: { query: string, format: "table"|"chart"|"json" }

GET  /api/health
GET  /api/models
```

## Data Model

```
Chat
  - id: UUID
  - title: string
  - messages: Message[]
  - created_at, updated_at

Message
  - id: UUID
  - role: user | assistant | system
  - content: string
  - skill: SkillType?
  - reasoning_chain: json?  (CoT trace: [{step, action, observation, conclusion}])
  - sources: json?         (retrieved knowledge base docs)
  - data: json?            (structured query results, tables, chart data)
  - confidence: float?     (0-1, for troubleshoot/predict skills)
  - created_at

KnowledgeDocument
  - id: UUID
  - content: text
  - doc_type: "fault_knowledge" | "protocol" | "manual" | "maintenance_log"
  - metadata: { source, device_type?, created_at }
  - embedding: vector (ChromaDB)

ProtocolDefinition
  - id: UUID
  - name: string
  - protocol_type: "modbus" | "custom" | "json"
  - spec: json  (register map or field definitions)
  - raw_data_field: string  (which DB field contains raw binary strings)

SkillResult
  - skill: SkillType
  - query: string
  - answer: string
  - reasoning_chain: array of { step, action, observation, conclusion }
  - confidence: float 0-1
  - data: object  (tables, charts, predictions depending on skill)
  - sources: array of doc_ids
  - execution_time_ms: int
  - actions: array of { type, target, params }? (for control ops)
```

## Evaluation Criteria

### Design Quality (weight: 0.3)
- [ ] API follows REST conventions, consistent error envelope
- [ ] Structured JSON responses with reasoning_chain always exposed
- [ ] OpenAPI docs auto-generated and accurate
- [ ] Protocol parsing layer is decoupled from query logic

### Originality (weight: 0.2)
- [ ] Temporal correlation reasoning (comm status + energy + time) built into Troubleshoot skill
- [ ] Dual-mode query (parsed data + raw protocol parsing) is domain-specific
- [ ] Skill plugin system allows adding new protocols without code changes

### Craft (weight: 0.3)
- [ ] Streaming for long-running predictions and report generation
- [ ] Correlation IDs for request tracing across skill executions
- [ ] Graceful degradation when LLM unavailable (return partial results with confidence)
- [ ] Confidence scores + intervals on all predictions
- [ ] Reasoning chain is human-readable AND machine-parseable

### Functionality (weight: 0.2)
- [ ] Query skill handles both Mode A (SQL) and Mode B (protocol parsing)
- [ ] Troubleshoot skill returns ranked root causes with temporal evidence
- [ ] Prediction skill returns per-device risk scores with 24h/7d/30d horizons
- [ ] Maintenance report generates PDF with all standard metrics
- [ ] Flexible report handles ad-hoc NL queries and returns chart data
- [ ] Knowledge base supports upload/search/delete for both fault knowledge AND protocol specs

## Sprint Plan

### Sprint 1: Foundation & Query Skill (Week 1-2)
**Goal**: Backend skeleton + Query skill with dual-mode data access

- Setup FastAPI + LangChain project structure
- Define all data models (SQLAlchemy)
- Implement skill router at `/api/chats/{id}/messages`
- **Build Query Skill Mode A**: NL → SQL → execute → tabular + NL summary
- **Build Query Skill Mode B**: Protocol definition upload + binary data parsing
- Setup sample SQLite DB with mock streetlight data (parsed + raw binary fields)
- **Done when**: "What is zone 55's total energy consumption this month?" AND "Parse the raw data for device LIGHT-55-A001" both return structured results

### Sprint 2: Troubleshoot + Knowledge Base (Week 3-4)
**Goal**: Temporal diagnostic reasoning with knowledge retrieval

- Setup ChromaDB vector store
- Populate fault diagnosis knowledge base (symptoms → root causes → procedures)
- Upload grid topology and network segment data to knowledge base
- Implement Troubleshoot Skill with temporal correlation logic
- **Done when**: "100 devices report 'communication lost' across A Street and B Street — analyze root causes" returns ranked diagnoses with evidence from energy data, comm logs, and time correlations

### Sprint 3: Prediction + Report Skills (Week 5-6)
**Goal**: ML forecasting and multi-format report generation

- Build Prediction Skill: failure risk scoring with confidence intervals
- Build Energy Prediction: time-series forecasting with weather factors
- Build Maintenance Report Skill: PDF/Excel/JSON with standard metrics
- Build Flexible Report Skill: ad-hoc NL → chart data / table
- **Done when**: User can request "30-day failure prediction for zone 55" and download PDF report

### Sprint 4: Protocol Adapters + Safety + Docker (Week 7-8)
**Goal**: Physical system integration with safety guardrails

- Implement Modbus/MQTT/BACnet/OPC adapter skeletons
- Add dual-confirmation for any control actions
- Implement audit logging
- Docker Compose for full stack deployment
- **Done when**: `docker-compose up` starts backend + ChromaDB + PostgreSQL, and all 5 skills respond correctly

## Anti-AI-Slop Directives

- DO NOT return raw LLM text — always structure with `answer`, `reasoning_chain`, `confidence`, `data`
- DO NOT skip the temporal correlation step in Troubleshoot — always cross-reference comm status + energy + time
- DO NOT treat raw binary data as unparseable — protocol definition files enable automatic decoding
- DO NOT generate fixed-template-only reports — Flexible Report must handle ad-hoc queries
- DO NOT skip confidence scores on predictions — every prediction needs a confidence interval
- DO NOT hardcode domain vocabulary — use the vocabulary mapping layer for all NL → SQL translations
- DO NOT skip error handling on SQL execution and LLM calls
