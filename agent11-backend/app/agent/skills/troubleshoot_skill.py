"""Troubleshoot 技能 - 故障诊断"""
from typing import Any
from datetime import datetime, timedelta
from app.agent.skills.base import BaseSkill
from app.agent.context import ConversationContext
from app.db.repositories.device import DeviceRepository
from app.db.repositories.comm import CommRepository
from app.db.repositories.reading import ReadingRepository
from app.db.repositories.device_fault import DeviceFaultRepository
from app.db.repositories.device_info import DeviceInfoRepository


class TroubleshootSkill(BaseSkill):
    """Troubleshoot 技能 - 故障诊断和根因分析"""

    name = "troubleshoot"

    # 故障状态列表
    FAULT_STATUSES = ("fault", "warning", "offline")

    REASONING_RULES = [
        {
            "condition": "comm_lost AND energy_continues AND lights_on",
            "diagnosis": "控制器硬件故障",
            "confidence_boost": 0.2,
            "description": "设备灯仍亮且有能耗，说明供电正常、灯具正常，但控制器完全失去通信，推断控制器本体的通信模块或主控硬件故障。"
        },
        {
            "condition": "comm_intermittent AND energy_steady AND lights_on",
            "diagnosis": "通信网络不稳定",
            "confidence_boost": 0.15,
            "description": "设备灯亮、能耗正常，但通信时断时续，说明控制器和灯具均正常，问题出在通信链路（网络信号弱、路由器/交换机不稳定、SIM卡流量不足等）。"
        },
        {
            "condition": "comm_lost AND no_energy AND lights_off",
            "diagnosis": "电源中断",
            "confidence_boost": 0.25,
            "description": "设备灯不亮且无能耗，同时通信也丢失，最可能是供电中断（配电箱跳闸、线路断开、区域停电）。"
        },
        {
            "condition": "comm_lost AND energy_continues AND lights_off",
            "diagnosis": "灯具故障或驱动损坏",
            "confidence_boost": 0.18,
            "description": "控制器仍有通信能力（或偶尔通信），但灯不亮且无对应能耗，可能是灯具本体损坏或LED驱动电源故障。"
        },
        {
            "condition": "single_light_flickering",
            "diagnosis": "驱动故障或灯泡老化",
            "confidence_boost": 0.1,
            "description": "单盏灯闪烁通常是单个灯具的驱动电源或LED模组老化导致。"
        },
        {
            "condition": "multiple_lights_flickering_same_area",
            "diagnosis": "电网电压波动",
            "confidence_boost": 0.2,
            "description": "同一区域多盏灯同时闪烁，通常是电网电压不稳定或配电变压器问题。"
        },
    ]

    async def execute(
        self,
        llm: Any,
        query: str,
        context: ConversationContext
    ) -> dict[str, Any]:
        """执行故障诊断"""
        reasoning_chain = []

        # 1. 查询通信中断的设备
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("查询通信中断设备", "查找所有通信中断的设备", "获取设备列表"),
            ("交叉引用能耗数据", "检查这些设备的能耗状态", "分析能耗模式")
        ]))

        comm_lost_devices = await self._get_comm_lost_devices()
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("分析结果", f"发现 {len(comm_lost_devices)} 个通信中断设备", "开始根因分析")
        ]))

        # 2. 查询数据库中直接标记为故障的设备
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("查询故障设备", "查找数据库中状态异常的设备", "获取故障设备列表")
        ]))

        faulty_devices = await self._get_faulty_devices()
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("分析结果", f"发现 {len(faulty_devices)} 个故障/告警设备", "合并分析")
        ]))

        # 3. 查询故障事件表中近期有故障的设备
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("查询故障事件", "从 devices_fault 查找近期故障事件", "获取故障设备列表")
        ]))

        fault_event_devices = await self._get_fault_event_devices()
        reasoning_chain.extend(await self._build_reasoning_chain([
            ("分析结果", f"发现 {len(fault_event_devices)} 个有故障事件的设备", "合并分析")
        ]))

        # 4. 合并设备列表（去重）
        seen = set()
        all_devices = []
        for d in comm_lost_devices + faulty_devices + fault_event_devices:
            did = d.get("device_id") or d.get("deviceId")
            if did and did not in seen:
                seen.add(did)
                all_devices.append(d)

        # 5. 关联分析
        root_causes = await self._analyze_root_causes(all_devices)

        # 6. 生成地图数据
        map_data = await self._generate_map_data(root_causes)

        # 计算总体置信度
        avg_confidence = sum(r["confidence"] for r in root_causes) / len(root_causes) if root_causes else 0.5

        # 7. 用 LLM 基于真实数据生成回答
        answer = await self._generate_llm_answer(llm, query, root_causes, all_devices)

        return {
            "answer": answer,
            "reasoning_chain": reasoning_chain,
            "confidence": avg_confidence,
            "map_data": map_data,
            "data": {
                "root_causes": root_causes
            },
            "sources": []
        }

    async def _generate_llm_answer(
        self,
        llm: Any,
        query: str,
        root_causes: list[dict],
        all_devices: list[dict]
    ) -> str:
        """基于真实数据库数据，用 LLM 生成针对性的回答"""
        # 构建数据摘要
        summary_lines = ["以下是系统数据库中查询到的真实数据：\n"]

        # 设备概览
        summary_lines.append(f"共有 {len(all_devices)} 个异常设备：")
        for d in all_devices[:30]:
            did = d.get("device_id") or d.get("deviceId", "unknown")
            zone = d.get("geozone", "unknown")
            status = d.get("status", "unknown")
            dt = d.get("device_type", d.get("deviceType", "unknown"))
            summary_lines.append(f"  - {did} | 区域: {zone} | 类型: {dt} | 状态: {status}")
        if len(all_devices) > 30:
            summary_lines.append(f"  ... 还有 {len(all_devices) - 30} 个设备")

        # 根因分析
        summary_lines.append(f"\n根因分析结果（共 {len(root_causes)} 项）：")
        for rc in root_causes:
            summary_lines.append(
                f"  - 原因: {rc['cause']} | 区域: {rc['zone']} | "
                f"涉及设备: {rc['device_count']} 个 | 置信度: {rc['confidence']:.0%}"
            )

        data_summary = "\n".join(summary_lines)

        system_prompt = """你是 AGENT 11，一个智能基础设施管理 AI 助手。

你的回答必须严格基于以下数据库查询到的真实数据。请根据用户的问题，从数据中提取最相关的信息来回答。

回答原则：
1. 仔细阅读用户的问题，理解他们具体想知道什么
2. 从提供的数据库数据中找到对应的信息
3. 用清晰、自然的中文回答，不要输出固定模板
4. 如果用户问的是具体某类异常（如温度、通信），请重点分析该类问题
5. 如果数据不包含用户询问的内容，诚实说明数据库中暂无相关记录
6. 数据中涉及的具体设备ID、区域、数量等信息必须准确引用
7. 不要编造不存在的数据细节"""

        try:
            response = await llm.invoke(
                f"## 用户问题\n{query}\n\n"
                f"## {data_summary}\n\n"
                f"请根据以上数据库真实数据，针对用户的问题给出准确的回答。"
                f"如果用户询问的具体问题在数据中没有对应记录，请如实告知。",
                system=system_prompt,
                temperature=0.3
            )
            return response
        except Exception:
            # LLM 失败时回退到模板回答
            return self._generate_diagnosis_answer(root_causes)

    async def _get_comm_lost_devices(self, max_devices: int = 500) -> list[dict]:
        """
        获取通信中断的设备（包含最近一次丢失时间）。
        默认最多分析 500 台设备，支持大规模故障场景。
        """
        now = datetime.utcnow()
        lookback_start = now - timedelta(days=14)
        comm_logs = await CommRepository.find_by_event_type(
            event_type="comm_loss",
            start_time=lookback_start,
            end_time=now,
            limit=5000,
        )

        # latest comm_loss per device_id
        latest_loss: dict[str, datetime] = {}
        for log in comm_logs:
            did = log.get("device_id")
            ts = log.get("timestamp")
            if not did or not ts:
                continue
            if did not in latest_loss or ts > latest_loss[did]:
                latest_loss[did] = ts

        devices: list[dict] = []
        # 按通信丢失时间排序，优先分析最近的
        sorted_items = sorted(latest_loss.items(), key=lambda x: x[1], reverse=True)
        for device_id, loss_ts in sorted_items[:max_devices]:
            device = await DeviceRepository.find_by_id(device_id)
            if device:
                device["last_comm_loss_at"] = loss_ts
                devices.append(device)

        return devices

    async def _get_faulty_devices(self, max_devices: int = 500) -> list[dict]:
        """
        获取数据库中直接标记为故障/告警的的设备。
        同时追踪这些设备近期通信状态。
        """
        now = datetime.utcnow()
        lookback_start = now - timedelta(days=7)

        # 查询各种异常状态的设备
        all_faulty = []
        for status in self.FAULT_STATUSES:
            devices = await DeviceRepository.find_all(status=status, limit=max_devices)
            for d in devices:
                d["_fault_source"] = f"status={status}"
                all_faulty.append(d)

        # 查询这些设备中哪些有近期通信丢失记录
        if all_faulty:
            faulty_ids = {d.get("device_id") for d in all_faulty if d.get("device_id")}
            comm_logs = await CommRepository.find_by_event_type(
                event_type="comm_loss",
                start_time=lookback_start,
                end_time=now,
                limit=5000,
            )
            # 只保留属于故障设备的日志，记录最近通信丢失时间
            latest_loss: dict[str, datetime] = {}
            for log in comm_logs:
                did = log.get("device_id")
                ts = log.get("timestamp")
                if did in faulty_ids and ts:
                    if did not in latest_loss or ts > latest_loss[did]:
                        latest_loss[did] = ts

            for d in all_faulty:
                did = d.get("device_id")
                if did and did in latest_loss:
                    d["last_comm_loss_at"] = latest_loss[did]
                else:
                    # 无通信丢失记录的故障设备，使用 updated_at 作为参考时间
                    d["last_comm_loss_at"] = d.get("updated_at") or now

        return all_faulty

    async def _get_fault_event_devices(self, days: int = 30) -> list[dict]:
        """
        从 devices_fault 表查询近期有故障事件的设备。
        故障事件表的 device_id 对应 devices_info.id。
        """
        now = datetime.utcnow()
        start_time = now - timedelta(days=days)

        recent_faults = await DeviceFaultRepository.find_recent(
            limit=200,
            start_time=start_time,
        )

        # 去重，每个 device_id 记录最近故障类型
        device_faults: dict[int, str] = {}
        for f in recent_faults:
            did = f.get("device_id")
            if did:
                if did not in device_faults:
                    device_faults[did] = f.get("fault", "unknown")

        if not device_faults:
            return []

        # 通过 devices_info 获取设备详细信息
        devices = []
        for did, fault_type in device_faults.items():
            info = await DeviceInfoRepository.find_by_id(did)
            if info:
                # 转换为与 _analyze_root_causes 兼容的格式
                devices.append({
                    "device_id": info.get("device_id") or str(did),
                    "device_type": info.get("device_type", "streetlight"),
                    "geozone": info.get("businessGroupName", "unknown"),
                    "street_name": info.get("street_name", ""),
                    "latitude": info.get("latitude"),
                    "longitude": info.get("longitude"),
                    "status": info.get("status", "fault"),
                    "fault_types": fault_type,
                    "last_comm_loss_at": now,
                    "_fault_source": f"device_fault:{fault_type}",
                })

        return devices

    async def _analyze_root_causes(self, devices: list[dict]) -> list[dict]:
        """分析根本原因"""
        root_causes = []

        # 按区域分组
        by_zone: dict[str, list] = {}
        for device in devices:
            zone = device.get("geozone", "unknown")
            if zone not in by_zone:
                by_zone[zone] = []
            by_zone[zone].append(device)

        # 对每个区域分析
        for zone, zone_devices in by_zone.items():
            # Device-level evidence
            device_evidence = []
            counters = {"controller_hw": 0, "network": 0, "power_outage": 0}

            for d in zone_devices:
                did = d.get("device_id") or d.get("deviceId")
                last_loss = d.get("last_comm_loss_at")
                if not did:
                    continue
                if not last_loss:
                    # 无通信丢失记录的故障设备，默认使用最近7天数据分析
                    last_loss = datetime.utcnow() - timedelta(days=7)

                # 确保 last_loss 是 datetime 对象
                if isinstance(last_loss, str):
                    try:
                        last_loss = datetime.fromisoformat(last_loss.replace("Z", "+00:00").split("+")[0])
                    except (ValueError, AttributeError):
                        last_loss = datetime.utcnow() - timedelta(days=7)

                # energy after comm loss (7 days window)
                start_time = last_loss
                end_time = datetime.utcnow()
                energy = await ReadingRepository.get_energy_readings(
                    device_id=did,
                    start_time=start_time,
                    end_time=end_time,
                    limit=200,
                )
                energy_sum = sum(float(r.get("energy_kwh") or 0) for r in energy)
                energy_continues = energy_sum > 0.0

                status = d.get("status")
                lights_on = status in (None, "normal", "warning")

                if energy_continues and lights_on:
                    diagnosis = "控制器硬件故障"
                    counters["controller_hw"] += 1
                    confidence = 0.85
                elif not energy_continues and not lights_on:
                    diagnosis = "电源中断"
                    counters["power_outage"] += 1
                    confidence = 0.82
                elif energy_continues and not lights_on:
                    diagnosis = "灯具故障或驱动损坏"
                    counters["controller_hw"] += 1
                    confidence = 0.78
                else:
                    # 不亮灯但有能耗的边界情况（可能是微功耗）
                    diagnosis = "通信网络不稳定"
                    counters["network"] += 1
                    confidence = 0.72

                device_evidence.append({
                    "device_id": did,
                    "last_comm_loss_at": last_loss.isoformat() if hasattr(last_loss, "isoformat") else str(last_loss),
                    "energy_since_loss_kwh": round(energy_sum, 3),
                    "status": status,
                    "diagnosis": diagnosis,
                    "confidence": confidence,
                })

            # Zone-level decision by majority
            cause, confidence = "通信网络问题", 0.7
            if counters["controller_hw"] >= max(counters["network"], counters["power_outage"]):
                cause, confidence = "控制器硬件故障", 0.8
            if counters["power_outage"] > max(counters["controller_hw"], counters["network"]):
                cause, confidence = "电源中断", 0.85

            root_causes.append({
                "rank": len(root_causes) + 1,
                "cause": cause,
                "zone": zone,
                "device_count": len(zone_devices),
                "evidence": [
                    f"区域 {zone} 有 {len(zone_devices)} 个设备通信中断",
                    f"推断: 控制器硬件故障 {counters['controller_hw']} 个, 网络问题 {counters['network']} 个, 电源问题 {counters['power_outage']} 个",
                ],
                "confidence": confidence,
                "recommendation": self._get_recommendation(cause),
                "devices": device_evidence[:50],
            })

        # 按置信度排序
        root_causes.sort(key=lambda x: x["confidence"], reverse=True)

        # 更新排名
        for i, cause in enumerate(root_causes):
            cause["rank"] = i + 1

        return root_causes

    def _get_recommendation(self, cause: str) -> str:
        """获取建议"""
        recommendations = {
            "电源中断": (
                "1. 检查区域电源配电箱总闸是否跳闸\n"
                "2. 用万用表测量配电箱输出端电压\n"
                "3. 检查电缆接头是否松动或进水\n"
                "4. 联系电力公司确认该区域是否有计划停电或线路故障"
            ),
            "控制器硬件故障": (
                "1. 检查控制器外观是否有烧毁、进水痕迹\n"
                "2. 尝试断电重启控制器（观察是否恢复通信）\n"
                "3. 检查控制器电源模块输出电压是否正常\n"
                "4. 如重启无效，准备更换控制器并记录故障控制器序列号"
            ),
            "通信网络问题": (
                "1. 检查网线/光纤连接是否松动、氧化\n"
                "2. 测试该区域网络信号强度（如为4G/5G通信，检查信号覆盖）\n"
                "3. 检查汇聚交换机/路由器端口状态灯\n"
                "4. 联系网络运营商确认是否有线路维护或基站故障"
            ),
            "灯具故障或驱动损坏": (
                "1. 检查灯具外观是否有明显损坏（灯珠发黑、驱动烧焦味）\n"
                "2. 测量灯具输入端电压是否正常\n"
                "3. 尝试更换同型号驱动电源测试\n"
                "4. 如驱动正常但灯不亮，更换LED模组"
            ),
        }
        return recommendations.get(cause, "建议现场检查确认问题，必要时联系技术支持")

    def _generate_diagnosis_answer(self, root_causes: list[dict]) -> str:
        """生成诊断回答"""
        if not root_causes:
            return "未发现明显故障模式，建议现场检查。"

        lines = [f"发现 {len(root_causes)} 个可能的根本原因：\n"]

        for cause in root_causes:
            lines.append(f"{cause['rank']}. {cause['cause']}")
            lines.append(f"   - 影响区域: {cause['zone']}")
            lines.append(f"   - 影响设备: {cause['device_count']} 个")
            lines.append(f"   - 置信度: {cause['confidence']:.0%}")
            lines.append(f"   - 建议: {cause['recommendation']}\n")

        return "\n".join(lines)

    async def _generate_map_data(self, root_causes: list[dict]) -> dict | None:
        """生成地图数据"""
        markers = []

        for cause in root_causes:
            zone = cause.get("zone")
            if not zone:
                continue

            # 获取该区域的设备
            devices = await DeviceRepository.find_all(geozone=zone, limit=50)

            for device in devices:
                if device.get("latitude") and device.get("longitude"):
                    markers.append({
                        "device_id": device.get("device_id", ""),
                        "lat": device.get("latitude"),
                        "lng": device.get("longitude"),
                        "status": "warning",
                        "popup": f"{device.get('device_id', '')} - {cause['cause']}"
                    })

        if not markers:
            return None

        # 计算中心点
        lats = [m["lat"] for m in markers]
        lngs = [m["lng"] for m in markers]
        center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]

        return {
            "center": center,
            "zoom": 14,
            "markers": markers,
            "legend": {
                "normal": "#3b82f6",
                "warning": "#f97316",
                "fault": "#ef4444"
            }
        }
