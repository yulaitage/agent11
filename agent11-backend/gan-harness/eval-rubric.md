# Evaluation Rubric: AGENT 11 Backend

> How the Evaluator scores the Generator's implementation

## Scoring Matrix

| Criterion | Weight | Score (0-10) | Notes |
|-----------|--------|--------------|-------|
| Design Quality | 0.30 | | |
| Originality | 0.20 | | |
| Craft | 0.30 | | |
| Functionality | 0.20 | | |
| **Total** | 1.00 | | |

---

## Design Quality (0.30)

| Checkpoint | Max Score | Pass Criteria |
|------------|-----------|---------------|
| API REST conventions | /3 | All endpoints follow REST patterns; GET/POST/DELETE correctly used |
| Consistent error envelope | /3 | Every error returns `{ error: string, code: string, details?: object }` |
| Structured response with reasoning_chain | /3 | Response always has `answer`, `reasoning_chain`, `confidence`, `data` |
| OpenAPI auto-generated | /3 | `GET /docs` returns interactive Swagger UI with accurate schemas |
| Protocol parsing layer decoupled | /3 | Protocol definitions are data (YAML/JSON), not hardcoded Python |

**Total Design Quality = sum / 5**

---

## Originality (0.20)

| Checkpoint | Max Score | Pass Criteria |
|------------|-----------|---------------|
| Temporal correlation in Troubleshoot | /5 | Skill cross-references comm status + energy consumption + time to distinguish hardware failure vs network issue |
| Dual-mode Query (parsed + raw) | /5 | Query Skill handles both SQL data AND raw binary protocol parsing via uploaded definitions |
| Extensible skill plugin system | /5 | New protocol skills can be added via entry points without modifying core code |

**Total Originality = sum / 5**

---

## Craft (0.30)

| Checkpoint | Max Score | Pass Criteria |
|------------|-----------|---------------|
| Streaming responses | /3 | Prediction and report generation stream progress updates |
| Correlation IDs | /3 | Each request tagged with UUID, logged across all skill executions |
| Graceful LLM degradation | /3 | When Ollama unavailable, returns partial results with `confidence: null` and error in envelope |
| Confidence intervals on predictions | /3 | Every prediction returns `confidence: [lower, upper]` range, not just point estimate |
| Reasoning chain human + machine readable | /3 | CoT is JSON array of `{step, action, observation, conclusion}`, readable as text AND parseable programmatically |
| Docker deployment | /3 | `docker-compose up` starts all services; all 5 skills respond correctly |

**Total Craft = sum / 6**

---

## Functionality (0.20)

### Query Skill — Dual Mode

| Test | Pass Criteria |
|------|---------------|
| Query Mode A: parsed data | "Total energy consumption for zone 55 in April" → SQL executed → table + NL summary |
| Query Mode B: raw protocol parsing | Upload protocol YAML → raw binary string parsed → human-readable output |
| Vocabulary mapping | "路灯故障" correctly maps to `streetlights.status = 'fault'`, not raw string match |

### Troubleshoot Skill

| Test | Pass Criteria |
|------|---------------|
| Temporal correlation | Input: 100 devices with comm lost, 23 still consuming energy → correctly identifies controller hardware failure vs network issue |
| Ranked root causes | Returns `root_causes` array sorted by confidence |
| Evidence in chain | Each root cause has `evidence` array citing specific data points |
| Reasoning chain complete | Every step shows: action taken, observation made, conclusion drawn |

### Prediction Skill

| Test | Pass Criteria |
|------|---------------|
| Failure prediction | Returns per-device risk scores with 24h/7d/30d horizons |
| Energy prediction | Returns time-series forecast with confidence bands |
| Contributing factors | Each prediction lists top 3 factors contributing to risk/score |
| Standard metrics summary | `prediction_summary` includes city-wide counts: total monitored, high_risk per horizon |

### Maintenance Report Skill

| Test | Pass Criteria |
|------|---------------|
| Weekly/Monthly/Annual | Generates all 3 report types |
| Standard metrics | Reports include: total energy, fault count by type, fault response time, availability % |
| PDF format | File is valid PDF, opens in standard reader, properly formatted |
| Excel format | File is valid XLSX, opens in Excel, with separate sheets for different data categories |

### Flexible Report Skill

| Test | Pass Criteria |
|------|---------------|
| Ad-hoc table query | "Zero consumption devices this week" → correct WHERE clause → table |
| Chart data output | "Energy trend by geozone" → returns plottable data series |
| Comparison report | "Fault rates Zone 12 vs Zone 34" → side-by-side comparison table |

### Knowledge Base

| Test | Pass Criteria |
|------|---------------|
| Upload fault knowledge | POST /api/knowledge with fault symptom → document indexed |
| Upload protocol definition | POST /api/protocols with YAML/JSON spec → stored and usable |
| Semantic search | Query for "driver failure" → returns relevant fault knowledge docs |
| Delete | DELETE /api/knowledge/{id} → document removed from vector store |

---

## Scoring Instructions for Evaluator

For each functional test, score:
- **2**: Fully correct (passes all pass criteria)
- **1**: Partially correct (works but missing detail, e.g., no confidence interval)
- **0**: Does not work or wrong approach

**Functionality Score = (sum of earned points) / (max possible points) * 10**

---

## Pass Thresholds

| Score | Severity | Action |
|-------|----------|--------|
| 0.0-3.4 | CRITICAL | Must fix before merge. Core skills non-functional. |
| 3.5-5.9 | HIGH | Should fix. At least one skill returns raw LLM text instead of structured output. |
| 6.0-6.9 | MEDIUM | Consider fixing. Protocol parsing missing OR Troubleshoot lacks temporal correlation. |
| 7.0-8.9 | LOW | Optional improvement. Minor craft issues (missing streaming, etc). |
| 9.0-10.0 | PASS | Ready for production. |

**Minimum to pass: 7.0 weighted average + Query and Troubleshoot skills must score ≥ 6/10 individually**

---

## Critical Failures (auto-fail regardless of total score)

- [ ] Query returns raw LLM text with no `reasoning_chain` or `data` field
- [ ] Troubleshoot does NOT perform temporal correlation (same output for comm lost with energy vs comm lost without energy)
- [ ] Prediction returns point estimate without confidence interval
- [ ] Knowledge base cannot store or retrieve protocol definition files
- [ ] Any SQL injection vulnerability in Query skill
