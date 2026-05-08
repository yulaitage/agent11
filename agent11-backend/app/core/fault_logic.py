"""
故障判断逻辑引擎

基于设备实时读数、阈值配置和历史数据，判断具体故障类型的触发条件，
并计算各故障类型的预测风险评分。
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from app.core.fault_types import (
    FaultTypeDef,
    FaultSeverity,
    FaultCategory,
    FAULT_TYPE_REGISTRY,
    get_fault_type,
    list_predictable_faults,
)


class FaultCheckResult:
    """故障检查结果"""

    def __init__(
        self,
        fault_code: str,
        triggered: bool,
        risk_score: float = 0.0,
        risk_level: str = "low",
        evidence: list[str] | None = None,
        recommendation: str = "",
        raw_data: dict | None = None,
    ):
        self.fault_code = fault_code
        self.triggered = triggered
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.evidence = evidence or []
        self.recommendation = recommendation
        self.raw_data = raw_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "fault_code": self.fault_code,
            "fault_name": get_fault_type(self.fault_code).name_cn if get_fault_type(self.fault_code) else self.fault_code,
            "triggered": self.triggered,
            "risk_score": round(self.risk_score, 3),
            "risk_level": self.risk_level,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "raw_data": self.raw_data,
        }


class FaultLogicEngine:
    """
    故障判断逻辑引擎

    输入：设备读数、阈值配置、历史数据
    输出：各故障类型的检查结果和预测风险
    """

    # 风险等级阈值
    RISK_THRESHOLDS = {
        "极高": 0.85,
        "高": 0.70,
        "中": 0.40,
        "低": 0.0,
    }

    @classmethod
    def _risk_level(cls, score: float) -> str:
        if score >= cls.RISK_THRESHOLDS["极高"]:
            return "极高"
        if score >= cls.RISK_THRESHOLDS["高"]:
            return "高"
        if score >= cls.RISK_THRESHOLDS["中"]:
            return "中"
        return "低"

    # ------------------------------------------------------------------
    # 电气参数类判断
    # ------------------------------------------------------------------

    @classmethod
    def check_ac_high_main_voltage(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """AC主电压过高判断"""
        code = "ac_high_main_voltage"
        ft = get_fault_type(code)
        max_v = threshold.get("max_voltage") if threshold else None

        if not readings or max_v is None:
            return FaultCheckResult(code, False, 0.0, "低", ["缺少电压数据或阈值配置"])

        voltages = [r.get("voltage", 0) for r in readings if r.get("voltage") is not None]
        if not voltages:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效电压读数"])

        # 连续超限检测
        consecutive_over = 0
        max_consecutive = 0
        for v in voltages:
            if v > max_v:
                consecutive_over += 1
                max_consecutive = max(max_consecutive, consecutive_over)
            else:
                consecutive_over = 0

        triggered = max_consecutive >= 3
        max_voltage = max(voltages)
        risk_score = min((max_voltage / max_v - 1) * 2 + max_consecutive * 0.1, 0.98) if max_voltage > max_v * 0.85 else 0.0

        evidence = [
            f"最大电压: {max_voltage:.1f}V (阈值: {max_v}V)",
            f"连续超限次数: {max_consecutive}",
        ]
        if triggered:
            evidence.append(f"电压超过阈值上限 {((max_voltage/max_v - 1)*100):.1f}%")

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            evidence,
            recommendation="检查电网电压，确认是否为区域电网问题或配电变压器故障" if triggered else "持续监控电压趋势",
            raw_data={"max_voltage": max_voltage, "threshold": max_v, "consecutive_over": max_consecutive},
        )

    @classmethod
    def check_ac_low_main_voltage(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """AC主电压过低判断"""
        code = "ac_low_main_voltage"
        ft = get_fault_type(code)
        min_v = threshold.get("min_voltage") if threshold else None

        if not readings or min_v is None:
            return FaultCheckResult(code, False, 0.0, "低", ["缺少电压数据或阈值配置"])

        voltages = [r.get("voltage", 0) for r in readings if r.get("voltage") is not None]
        if not voltages:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效电压读数"])

        consecutive_under = 0
        max_consecutive = 0
        for v in voltages:
            if v < min_v:
                consecutive_under += 1
                max_consecutive = max(max_consecutive, consecutive_under)
            else:
                consecutive_under = 0

        triggered = max_consecutive >= 3
        min_voltage = min(voltages)
        risk_score = min((1 - min_voltage / min_v) * 2 + max_consecutive * 0.1, 0.98) if min_voltage < min_v * 1.15 else 0.0

        evidence = [
            f"最小电压: {min_voltage:.1f}V (阈值: {min_v}V)",
            f"连续低电压次数: {max_consecutive}",
        ]

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            evidence,
            recommendation="检查配电线路压降，确认电缆接头是否松动" if triggered else "持续监控电压趋势",
            raw_data={"min_voltage": min_voltage, "threshold": min_v, "consecutive_under": max_consecutive},
        )

    @classmethod
    def check_high_load_power(
        cls,
        readings: list[dict],
        threshold: dict | None,
        rated_power: float | None = None,
    ) -> FaultCheckResult:
        """负载功率过高判断"""
        code = "high_load_power"
        max_p = threshold.get("max_power") if threshold else None

        if not readings or max_p is None:
            return FaultCheckResult(code, False, 0.0, "低", ["缺少功率数据或阈值配置"])

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        if not powers:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率读数"])

        max_power = max(powers)
        avg_power = sum(powers) / len(powers)
        triggered = max_power > max_p or (rated_power and max_power > rated_power * 1.2)

        risk_score = 0.0
        if max_power > max_p * 0.85:
            risk_score = min((max_power / max_p - 0.85) * 3, 0.98)

        evidence = [f"最大功率: {max_power:.1f}W (阈值: {max_p}W)", f"平均功率: {avg_power:.1f}W"]
        if rated_power:
            evidence.append(f"额定功率: {rated_power}W")

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            evidence,
            recommendation="检查灯具是否过载，确认驱动器选型是否匹配" if triggered else "监控功率趋势",
            raw_data={"max_power": max_power, "avg_power": avg_power, "threshold": max_p},
        )

    @classmethod
    def check_high_load_current(
        cls,
        readings: list[dict],
        threshold: dict | None,
        rated_current: float | None = None,
    ) -> FaultCheckResult:
        """负载电流过高判断"""
        code = "high_load_current"
        max_c = threshold.get("max_current") if threshold else None

        if not readings or max_c is None:
            return FaultCheckResult(code, False, 0.0, "低", ["缺少电流数据或阈值配置"])

        currents = [r.get("current", 0) for r in readings if r.get("current") is not None]
        if not currents:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效电流读数"])

        max_current = max(currents)
        triggered = max_current > max_c or (rated_current and max_current > rated_current * 1.2)
        risk_score = min((max_current / max_c - 0.85) * 3, 0.98) if max_current > max_c * 0.85 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最大电流: {max_current:.2f}A (阈值: {max_c}A)"],
            recommendation="检查线路是否短路或灯具内部故障" if triggered else "监控电流趋势",
            raw_data={"max_current": max_current, "threshold": max_c},
        )

    @classmethod
    def check_low_power_factor(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """功率因素过低判断"""
        code = "low_power_factor"
        min_pf = threshold.get("min_power_factor") if threshold else 0.85

        pfs = [r.get("power_factor", 0) for r in readings if r.get("power_factor") is not None]
        if not pfs:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率因素读数"])

        min_pf_val = min(pfs)
        avg_pf = sum(pfs) / len(pfs)
        triggered = min_pf_val < min_pf
        risk_score = min((min_pf - min_pf_val) * 2 + (min_pf - avg_pf), 0.98) if min_pf_val < min_pf * 1.15 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最小功率因素: {min_pf_val:.2f} (阈值: {min_pf})", f"平均功率因素: {avg_pf:.2f}"],
            recommendation="检查补偿电容是否失效或灯具驱动是否老化" if triggered else "监控功率因素",
            raw_data={"min_pf": min_pf_val, "avg_pf": avg_pf, "threshold": min_pf},
        )

    @classmethod
    def check_low_load_power(
        cls,
        readings: list[dict],
        threshold: dict | None,
        rated_power: float | None = None,
        expected_on: bool = True,
    ) -> FaultCheckResult:
        """负载功率过低判断"""
        code = "low_load_power"
        min_p = threshold.get("min_power") if threshold else None

        if not expected_on:
            return FaultCheckResult(code, False, 0.0, "低", ["灯未处于应亮状态，无需检测"])

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        if not powers:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率读数"])

        min_power = min(powers)
        triggered = False
        if min_p is not None and min_power < min_p:
            triggered = True
        if rated_power and min_power < rated_power * 0.3:
            triggered = True

        risk_score = 0.0
        if rated_power and min_power > 0:
            risk_score = min(1.0 - min_power / (rated_power * 0.5), 0.98)

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最小功率: {min_power:.1f}W (额定: {rated_power or 'N/A'}W)"],
            recommendation="检查灯具是否老化或驱动器输出异常" if triggered else "监控功率趋势",
            raw_data={"min_power": min_power, "rated_power": rated_power},
        )

    @classmethod
    def check_low_load_current(
        cls,
        readings: list[dict],
        threshold: dict | None,
        rated_current: float | None = None,
        expected_on: bool = True,
    ) -> FaultCheckResult:
        """负载电流过低判断"""
        code = "low_load_current"
        min_c = threshold.get("min_current") if threshold else None

        if not expected_on:
            return FaultCheckResult(code, False, 0.0, "低", ["灯未处于应亮状态，无需检测"])

        currents = [r.get("current", 0) for r in readings if r.get("current") is not None]
        if not currents:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效电流读数"])

        min_current = min(currents)
        triggered = False
        if min_c is not None and min_current < min_c:
            triggered = True
        if rated_current and min_current < rated_current * 0.3:
            triggered = True

        risk_score = 0.0
        if rated_current and min_current > 0:
            risk_score = min(1.0 - min_current / (rated_current * 0.5), 0.98)

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最小电流: {min_current:.2f}A (额定: {rated_current or 'N/A'}A)"],
            recommendation="检查灯具或线路是否开路" if triggered else "监控电流趋势",
            raw_data={"min_current": min_current, "rated_current": rated_current},
        )

    @classmethod
    def check_abnormal_ac_voltage_fluctuation(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """AC电压异常波动判断"""
        code = "abnormal_ac_voltage_fluctuation"

        voltages = [r.get("voltage", 0) for r in readings if r.get("voltage") is not None]
        if len(voltages) < 3:
            return FaultCheckResult(code, False, 0.0, "低", ["电压样本不足"])

        mean_v = sum(voltages) / len(voltages)
        variance = sum((v - mean_v) ** 2 for v in voltages) / len(voltages)
        std_dev = math.sqrt(variance)

        # 波动率 = 标准差 / 均值
        fluctuation_rate = std_dev / mean_v if mean_v > 0 else 0
        triggered = fluctuation_rate > 0.15  # 15% 波动率阈值

        risk_score = min(fluctuation_rate * 3, 0.98) if fluctuation_rate > 0.08 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"电压均值: {mean_v:.1f}V", f"标准差: {std_dev:.2f}V", f"波动率: {fluctuation_rate*100:.1f}%"],
            recommendation="检查电网稳定性，确认配电变压器负载率" if triggered else "持续监控",
            raw_data={"mean": mean_v, "std_dev": std_dev, "fluctuation_rate": fluctuation_rate},
        )

    @classmethod
    def check_ac_on_off_flicker(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """AC电通断闪烁判断"""
        code = "ac_on_off_flicker"

        # 从电压读数检测通断
        voltages = [r.get("voltage", 0) for r in readings if r.get("voltage") is not None]
        if len(voltages) >= 4:
            # 检测电压从有到无再到有的循环次数
            transitions = 0
            was_on = voltages[0] > 50  # 50V作为通断阈值
            for v in voltages[1:]:
                is_on = v > 50
                if was_on != is_on:
                    transitions += 1
                    was_on = is_on
            on_off_cycles = transitions // 2  # 一次完整闪烁 = 通+断

            triggered = on_off_cycles >= 3
            risk_score = min(on_off_cycles * 0.15, 0.95) if on_off_cycles > 0 else 0.0

            if triggered:
                return FaultCheckResult(
                    code, triggered, risk_score, cls._risk_level(risk_score),
                    [f"检测到电源通断循环: {on_off_cycles}次 (阈值: 3次)"],
                    recommendation="检查供电线路接触是否良好，排查电源波动原因",
                    raw_data={"on_off_cycles": on_off_cycles, "voltage_samples": len(voltages)},
                )

        # 从通信日志检测电源事件
        if comm_logs:
            power_events = [
                log for log in comm_logs
                if log.get("type", "").lower() in ("power_loss", "power_restore", "brownout", "power_on", "power_off")
            ]
            if len(power_events) >= 3:
                return FaultCheckResult(
                    code, True, 0.85, cls._risk_level(0.85),
                    [f"电源事件次数: {len(power_events)} (1小时内)"],
                    recommendation="检查电网供电质量及线路接触情况",
                    raw_data={"power_events_count": len(power_events), "events": power_events},
                )

        return FaultCheckResult(code, False, 0.0, "低", ["电源供电正常"])

    # ------------------------------------------------------------------
    # 温度类判断
    # ------------------------------------------------------------------

    @classmethod
    def check_high_temperature(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """温度过高判断"""
        code = "high_temperature"
        max_t = threshold.get("max_temperature") if threshold else 85.0

        temps = [r.get("temperature", 0) for r in readings if r.get("temperature") is not None]
        if not temps:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效温度读数"])

        max_temp = max(temps)
        avg_temp = sum(temps) / len(temps)
        triggered = max_temp > max_t

        risk_score = 0.0
        if max_temp > max_t * 0.85:
            risk_score = min((max_temp / max_t - 0.85) * 4, 0.98)

        # 计算升温速率（如果有时间戳）
        if len(readings) >= 2 and readings[0].get("timestamp") and readings[-1].get("timestamp"):
            try:
                t1 = readings[0]["timestamp"]
                t2 = readings[-1]["timestamp"]
                if isinstance(t1, str):
                    t1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
                if isinstance(t2, str):
                    t2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
                hours = (t2 - t1).total_seconds() / 3600
                if hours > 0:
                    rise_rate = (temps[-1] - temps[0]) / hours
                    if rise_rate > 5 and risk_score < 0.7:
                        risk_score = min(risk_score + 0.15, 0.98)
            except Exception:
                pass

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最高温度: {max_temp:.1f}°C (阈值: {max_t}°C)", f"平均温度: {avg_temp:.1f}°C"],
            recommendation="检查散热条件，确认灯具通风是否良好" if triggered else "监控温度趋势",
            raw_data={"max_temp": max_temp, "avg_temp": avg_temp, "threshold": max_t},
        )

    @classmethod
    def check_temperature_and_humidity_sensor_temperature_too_high(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """温湿度传感器温度过高判断"""
        code = "temperature_and_humidity_sensor_temperature_too_high"
        max_env_t = threshold.get("max_env_temperature") if threshold else 60.0

        # 使用环境温度读数（env_temperature 或 ambient_temperature 字段）
        temps = [
            r.get("env_temperature") or r.get("ambient_temperature") or 0
            for r in readings
            if r.get("env_temperature") is not None or r.get("ambient_temperature") is not None
        ]
        if not temps:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效环境温度读数"])

        max_temp = max(temps)
        triggered = max_temp > max_env_t
        risk_score = min((max_temp / max_env_t - 0.9) * 5, 0.95) if max_temp > max_env_t * 0.9 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最高环境温度: {max_temp:.1f}°C (阈值: {max_env_t}°C)"],
            recommendation="检查设备安装环境通风散热情况" if triggered else "监控环境温度",
            raw_data={"max_env_temp": max_temp, "threshold": max_env_t},
        )

    @classmethod
    def check_temperature_and_humidity_sensor_temperature_too_low(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """温湿度传感器温度过低判断"""
        code = "temperature_and_humidity_sensor_temperature_too_low"
        min_env_t = threshold.get("min_env_temperature") if threshold else -20.0

        temps = [
            r.get("env_temperature") or r.get("ambient_temperature") or 0
            for r in readings
            if r.get("env_temperature") is not None or r.get("ambient_temperature") is not None
        ]
        if not temps:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效环境温度读数"])

        min_temp = min(temps)
        triggered = min_temp < min_env_t
        risk_score = min((min_env_t - min_temp) * 0.05, 0.90) if min_temp < min_env_t else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最低环境温度: {min_temp:.1f}°C (阈值: {min_env_t}°C)"],
            recommendation="注意低温可能影响设备启动和电池性能" if triggered else "监控环境温度",
            raw_data={"min_env_temp": min_temp, "threshold": min_env_t},
        )

    @classmethod
    def check_temperature_and_humidity_sensor_humidity_too_high(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """温湿度传感器湿度过高判断"""
        code = "temperature_and_humidity_sensor_humidity_too_high"
        max_h = threshold.get("max_humidity") if threshold else 85.0

        humidities = [r.get("humidity", 0) for r in readings if r.get("humidity") is not None]
        if not humidities:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效湿度读数"])

        max_hum = max(humidities)
        triggered = max_hum > max_h
        risk_score = min((max_hum / max_h - 0.9) * 3, 0.95) if max_hum > max_h * 0.9 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最高湿度: {max_hum:.1f}%RH (阈值: {max_h}%RH)"],
            recommendation="检查设备密封性，高湿度可能导致凝露和短路" if triggered else "监控湿度趋势",
            raw_data={"max_humidity": max_hum, "threshold": max_h},
        )

    @classmethod
    def check_temperature_and_humidity_sensor_humidity_too_low(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """温湿度传感器湿度过低判断"""
        code = "temperature_and_humidity_sensor_humidity_too_low"
        min_h = threshold.get("min_humidity") if threshold else 20.0

        humidities = [r.get("humidity", 0) for r in readings if r.get("humidity") is not None]
        if not humidities:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效湿度读数"])

        min_hum = min(humidities)
        triggered = min_hum < min_h
        risk_score = max(0.0, 0.3 - (min_hum - min_h) * 0.02) if min_hum < min_h else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最低湿度: {min_hum:.1f}%RH (阈值: {min_h}%RH)"],
            recommendation="干燥环境易产生静电，注意设备接地" if triggered else "监控湿度趋势",
            raw_data={"min_humidity": min_hum, "threshold": min_h},
        )

    # ------------------------------------------------------------------
    # 传感器类判断 (Sensor)
    # ------------------------------------------------------------------

    @classmethod
    def check_meter_error(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
        expected_on: bool = True,
    ) -> FaultCheckResult:
        """电表错误判断"""
        code = "meter_error"

        # 检查1: 亮灯时能耗为0
        if expected_on:
            energies = [r.get("energy", 0) for r in readings if r.get("energy") is not None]
            if energies and all(e == 0 for e in energies):
                return FaultCheckResult(
                    code, True, 0.85, cls._risk_level(0.85),
                    ["灯亮时能耗始终为0，电表可能故障"],
                    recommendation="检查电表接线和通信，确认电表是否正常工作",
                    raw_data={"energies": energies, "expected_on": True},
                )

        # 检查2: 能耗读数跳变 > 50%
        energies = [r.get("energy", 0) for r in readings if r.get("energy") is not None]
        if len(energies) >= 3:
            jumps = 0
            for i in range(1, len(energies)):
                if energies[i-1] > 0 and abs(energies[i] - energies[i-1]) / max(energies[i-1], 0.01) > 0.5:
                    jumps += 1
            if jumps >= 2:
                return FaultCheckResult(
                    code, True, 0.75, cls._risk_level(0.75),
                    [f"能耗读数跳变次数: {jumps} (超过2次)"],
                    recommendation="电表数据异常跳变，检查电表是否损坏",
                    raw_data={"energies": energies, "jumps": jumps},
                )

        # 检查3: 通信错误码
        if comm_logs:
            error_codes = [log.get("error_code") for log in comm_logs if log.get("error_code")]
            if error_codes:
                return FaultCheckResult(
                    code, True, 0.70, cls._risk_level(0.70),
                    [f"电表返回错误码: {error_codes}"],
                    recommendation="电表返回错误码，检查电表状态",
                    raw_data={"error_codes": error_codes},
                )

        return FaultCheckResult(code, False, 0.0, "低", ["电表数据正常"])

    @classmethod
    def check_light_perception_error(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """光感错误判断"""
        code = "light_perception_error"
        daylight_t = threshold.get("daylight_threshold") if threshold else 50.0

        illuminances = [
            r.get("illuminance") or r.get("light") or 0
            for r in readings
            if r.get("illuminance") is not None or r.get("light") is not None
        ]
        if not illuminances:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效光照度读数"])

        max_ill = max(illuminances)
        min_ill = min(illuminances)
        unique_vals = len(set(round(v, -1) for v in illuminances))  # 粗略去重

        # 判断1: 白天读数异常低（可能被遮挡）
        day_readings_low = sum(1 for v in illuminances if v < daylight_t * 0.3)
        day_low_ratio = day_readings_low / len(illuminances)

        # 判断2: 读数长时间不变（传感器冻结）
        stuck = unique_vals <= 2 and len(illuminances) >= 5

        triggered = day_low_ratio > 0.8 or stuck
        risk_score = 0.0
        if day_low_ratio > 0.8:
            risk_score = min(0.5 + day_low_ratio * 0.4, 0.95)
        if stuck:
            risk_score = max(risk_score, 0.7)

        evidence = [
            f"光照度范围: {min_ill:.0f}~{max_ill:.0f} lux",
            f"低光照度比例: {day_low_ratio*100:.0f}%",
        ]
        if stuck:
            evidence.append(f"读数长时间未变化(唯一值数:{unique_vals})")

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            evidence,
            recommendation="检查光感传感器是否被遮挡、污损或故障" if triggered else "监控光感数据",
            raw_data={"min_illuminance": min_ill, "max_illuminance": max_ill, "day_low_ratio": day_low_ratio},
        )

    @classmethod
    def check_ext_illsensor_communication_failure(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """外接光照度传感器通信故障判断"""
        code = "ext_illsensor_communication_failure"

        # 检查通信日志中的超时/无响应
        if comm_logs:
            timeouts = sum(
                1 for log in comm_logs
                if log.get("sensor_type", "").lower() in ("illuminance", "ext_ill", "light_sensor")
                and log.get("status") in ("timeout", "no_response", "failed")
            )
            total = sum(
                1 for log in comm_logs
                if log.get("sensor_type", "").lower() in ("illuminance", "ext_ill", "light_sensor")
            )
            if total > 0 and timeouts / total > 0.3:
                return FaultCheckResult(
                    code, True, 0.80, cls._risk_level(0.80),
                    [f"外接光照度传感器通信超时率: {timeouts}/{total}"],
                    recommendation="检查外接光照度传感器接线和通信模块",
                    raw_data={"timeouts": timeouts, "total": total},
                )

        # 备选: 检查读数持续为空
        ill_readings = [
            r.get("illuminance") for r in readings
            if r.get("illuminance") is not None
        ] if readings else []

        if not ill_readings and readings:
            # 设备有读数但无光照度数据，可能通信失败
            return FaultCheckResult(
                code, True, 0.60, cls._risk_level(0.60),
                ["设备有上报但无光照度数据，传感器通信可能中断"],
                recommendation="检查外接光照度传感器是否离线",
                raw_data={"reading_count": len(readings), "ill_readings": 0},
            )

        return FaultCheckResult(code, False, 0.0, "低", ["外接光照度传感器通信正常"])

    # ------------------------------------------------------------------
    # 通信类判断 (Communication)
    # ------------------------------------------------------------------

    @classmethod
    def check_drive_communication_error(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """驱动通信错误判断"""
        code = "drive_communication_error"

        if not comm_logs:
            return FaultCheckResult(code, False, 0.0, "低", ["无通信日志数据"])

        drive_logs = [
            log for log in comm_logs
            if log.get("target", "").lower() in ("drive", "driver", "led_driver")
        ]
        if not drive_logs:
            drive_logs = comm_logs  # 如果没有过滤到驱动日志，使用全部

        timeouts = sum(1 for log in drive_logs if log.get("status") in ("timeout", "failed", "crc_error"))
        total = len(drive_logs)

        if total == 0:
            return FaultCheckResult(code, False, 0.0, "低", ["无驱动通信记录"])

        fail_rate = timeouts / total
        triggered = fail_rate > 0.1 or timeouts >= 3
        risk_score = min(fail_rate * 3, 0.98) if fail_rate > 0.05 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"驱动通信失败: {timeouts}/{total} ({fail_rate*100:.1f}%)"],
            recommendation="检查驱动通信线路和DALI/0-10V接口" if triggered else "监控驱动通信状态",
            raw_data={"timeouts": timeouts, "total": total, "fail_rate": fail_rate},
        )

    @classmethod
    def check_temperature_and_humidity_sensor_communication_error(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """温湿度传感器通信错误判断"""
        code = "temperature_and_humidity_sensor_communication_error"

        # 从读数判断：如果完全没有温湿度数据但其他数据正常
        has_temp = any(
            r.get("temperature") is not None or r.get("env_temperature") is not None
            for r in readings
        ) if readings else False

        if not has_temp and readings and len(readings) >= 3:
            return FaultCheckResult(
                code, True, 0.75, cls._risk_level(0.75),
                ["设备持续上报但无温湿度数据，传感器通信可能中断"],
                recommendation="检查温湿度传感器接线和通信模块",
                raw_data={"reading_count": len(readings), "has_temperature": False},
            )

        # 从通信日志判断
        if comm_logs:
            th_logs = [
                log for log in comm_logs
                if log.get("target", "").lower() in ("th_sensor", "temp_humid", "sht20", "dht22")
            ]
            if th_logs:
                timeouts = sum(1 for log in th_logs if log.get("status") in ("timeout", "no_response"))
                if timeouts >= 3:
                    return FaultCheckResult(
                        code, True, 0.80, cls._risk_level(0.80),
                        [f"温湿度传感器通信超时: {timeouts}次"],
                        recommendation="检查温湿度传感器是否离线",
                        raw_data={"timeouts": timeouts},
                    )

        return FaultCheckResult(code, False, 0.0, "低", ["温湿度传感器通信正常"])

    @classmethod
    def check_ctrl_multicast_failed(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """设备自控组播失败判断"""
        code = "ctrl_multicast_failed"

        if not comm_logs:
            return FaultCheckResult(code, False, 0.0, "低", ["无通信日志数据"])

        multicast_logs = [
            log for log in comm_logs
            if log.get("type", "").lower() in ("multicast", "groupcast", "broadcast")
        ]
        if not multicast_logs:
            return FaultCheckResult(code, False, 0.0, "低", ["无组播通信记录"])

        failed = sum(1 for log in multicast_logs if log.get("status") in ("timeout", "no_ack", "failed"))
        total = len(multicast_logs)
        fail_rate = failed / total if total > 0 else 0

        triggered = fail_rate > 0.05 or failed >= 2
        risk_score = min(fail_rate * 5, 0.90) if fail_rate > 0.02 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"组播命令失败: {failed}/{total} ({fail_rate*100:.1f}%)"],
            recommendation="检查网络通信链路和路由器组播配置" if triggered else "监控组播通信状态",
            raw_data={"failed": failed, "total": total, "fail_rate": fail_rate},
        )

    @classmethod
    def check_jcmode_syn_signal_failure(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """联控模式同步信号故障判断"""
        code = "jcmode_syn_signal_failure"

        # 需要设备处于联控模式且同步信号异常
        is_jcmode = any(
            r.get("control_mode") == "jc" or r.get("control_mode") == "联控"
            for r in readings
        ) if readings else False

        if not is_jcmode:
            return FaultCheckResult(code, False, 0.0, "低", ["设备未处于联控模式"])

        # 检查通信日志中的同步信号
        if comm_logs:
            sync_logs = [
                log for log in comm_logs
                if log.get("type", "").lower() in ("sync", "synchronization", "heartbeat")
            ]
            if sync_logs:
                failed_sync = sum(1 for log in sync_logs if log.get("status") != "ok")
                total_sync = len(sync_logs)
                fail_rate = failed_sync / total_sync if total_sync > 0 else 0

                triggered = fail_rate > 0.2 or failed_sync >= 3
                risk_score = min(fail_rate * 3, 0.95) if fail_rate > 0.1 else 0.0

                return FaultCheckResult(
                    code, triggered, risk_score, cls._risk_level(risk_score),
                    [f"同步信号失败: {failed_sync}/{total_sync} ({fail_rate*100:.1f}%)"],
                    recommendation="检查主控与从控设备之间的同步信号链路" if triggered else "监控同步状态",
                    raw_data={"failed_sync": failed_sync, "total_sync": total_sync},
                )

        # 没有同步日志但处于联控模式 → 可能同步信号丢失
        return FaultCheckResult(
            code, True, 0.50, cls._risk_level(0.50),
            ["设备处于联控模式但无同步信号记录"],
            recommendation="检查联控同步信号配置",
            raw_data={"is_jcmode": True, "sync_logs_found": False},
        )

    # ------------------------------------------------------------------
    # 灯具类判断 (Lamp)
    # ------------------------------------------------------------------

    @classmethod
    def check_drive_error(
        cls,
        readings: list[dict],
        comm_logs: list[dict] | None = None,
    ) -> FaultCheckResult:
        """驱动器错误判断"""
        code = "drive_error"

        # 检查驱动器错误状态码
        error_statuses = [r.get("drive_status") or r.get("driver_status") for r in readings
                         if r.get("drive_status") is not None or r.get("driver_status") is not None]
        if error_statuses:
            error_codes = [s for s in error_statuses if s != "ok" and s != 0 and s != "normal"]
            if error_codes:
                return FaultCheckResult(
                    code, True, 0.90, cls._risk_level(0.90),
                    [f"驱动器返回错误状态: {error_codes}"],
                    recommendation="检查LED驱动器，确认是否过温/过压/开路/短路",
                    raw_data={"error_codes": error_codes},
                )

        # 检查通信日志中的驱动错误
        if comm_logs:
            drive_errors = [
                log for log in comm_logs
                if log.get("target", "").lower() in ("drive", "driver")
                and log.get("error_code") is not None
            ]
            if drive_errors:
                codes = [log["error_code"] for log in drive_errors]
                return FaultCheckResult(
                    code, True, 0.80, cls._risk_level(0.80),
                    [f"驱动器通信返回错误码: {codes}"],
                    recommendation="根据错误码检查驱动器具体故障",
                    raw_data={"comm_error_codes": codes},
                )

        return FaultCheckResult(code, False, 0.0, "低", ["驱动器状态正常"])

    @classmethod
    def check_lights_off_during_on_time(
        cls,
        readings: list[dict],
        expected_on: bool = True,
        manual_off: bool = False,
    ) -> FaultCheckResult:
        """亮灯时间关灯判断"""
        code = "lights_off_during_on_time"

        if not expected_on:
            return FaultCheckResult(code, False, 0.0, "低", ["非亮灯时段"])

        if manual_off:
            return FaultCheckResult(code, False, 0.0, "低", ["手动关闭，非异常"])

        # 在应有亮灯时段检查灯状态
        brightnesses = [r.get("brightness", 0) for r in readings if r.get("brightness") is not None]
        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]

        light_on = False
        if brightnesses:
            light_on = any(b > 10 for b in brightnesses)
        elif powers:
            light_on = any(p > 5 for p in powers)
        else:
            return FaultCheckResult(code, False, 0.0, "低", ["无亮度或功率数据"])

        # 在亮灯时段但灯不亮
        triggered = not light_on
        risk_score = 0.85 if triggered else 0.0

        avg_brightness = sum(brightnesses) / len(brightnesses) if brightnesses else 0
        avg_power = sum(powers) / len(powers) if powers else 0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"亮灯时段灯不亮: 平均亮度={avg_brightness:.1f}%, 平均功率={avg_power:.1f}W"],
            recommendation="检查schedule设置、继电器状态和控制指令" if triggered else "监控亮灯状态",
            raw_data={"avg_brightness": avg_brightness, "avg_power": avg_power},
        )

    @classmethod
    def check_abnormal_lights_off(
        cls,
        readings: list[dict],
        schedule_on: bool = False,
        manual_off: bool = False,
        protection_active: bool = False,
    ) -> FaultCheckResult:
        """异常关灯判断"""
        code = "abnormal_lights_off"

        if schedule_on:
            return FaultCheckResult(code, False, 0.0, "低", ["当前在schedule时段内，走亮灯时间关灯检测"])

        if manual_off:
            return FaultCheckResult(code, False, 0.0, "低", ["手动关闭，非异常"])

        if protection_active:
            return FaultCheckResult(code, False, 0.0, "低", ["故障保护触发，非异常"])

        # 非schedule时段检查灯是否意外熄灭（从有到无的跳变）
        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        brightnesses = [r.get("brightness", 0) for r in readings if r.get("brightness") is not None]

        if len(powers) < 2 and len(brightnesses) < 2:
            return FaultCheckResult(code, False, 0.0, "低", ["样本不足以检测异常关灯"])

        # 检测功率或亮度从有到无的跳变
        sudden_off = False
        if len(powers) >= 2:
            for i in range(1, len(powers)):
                if powers[i-1] > 10 and powers[i] < 5:
                    sudden_off = True
                    break
        if not sudden_off and len(brightnesses) >= 2:
            for i in range(1, len(brightnesses)):
                if brightnesses[i-1] > 20 and brightnesses[i] < 5:
                    sudden_off = True
                    break

        triggered = sudden_off
        risk_score = 0.80 if triggered else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            ["检测到灯从亮到灭的异常跳变"],
            recommendation="检查电源、继电器和控制器，排查异常关灯原因" if triggered else "监控设备状态",
            raw_data={"has_sudden_off": sudden_off, "power_count": len(powers)},
        )

    @classmethod
    def check_lamp_failed(
        cls,
        readings: list[dict],
        rated_power: float | None = None,
        expected_on: bool = True,
    ) -> FaultCheckResult:
        """灯失败判断"""
        code = "lamp_failed"

        if not expected_on:
            return FaultCheckResult(code, False, 0.0, "低", ["灯未处于应亮状态"])

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        brightnesses = [r.get("brightness", 0) for r in readings if r.get("brightness") is not None]

        if not powers:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率读数"])

        avg_power = sum(powers) / len(powers)
        avg_brightness = sum(brightnesses) / len(brightnesses) if brightnesses else 0

        triggered = avg_power < 5.0 and avg_brightness < 5.0
        risk_score = 0.0
        if rated_power and rated_power > 0:
            risk_score = min(1.0 - avg_power / (rated_power * 0.3), 0.98)
        elif avg_power < 5:
            risk_score = 0.9

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"平均功率: {avg_power:.1f}W", f"平均亮度: {avg_brightness:.1f}%"],
            recommendation="检查灯具和驱动器，确认LED模组是否损坏" if triggered else "监控灯具状态",
            raw_data={"avg_power": avg_power, "avg_brightness": avg_brightness},
        )

    @classmethod
    def check_flash_lights(
        cls,
        readings: list[dict],
    ) -> FaultCheckResult:
        """闪灯判断"""
        code = "flash_lights"

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        if len(powers) < 4:
            return FaultCheckResult(code, False, 0.0, "低", ["功率样本不足"])

        # 检测波动：相邻读数变化超过30%视为一次波动
        fluctuations = 0
        for i in range(1, len(powers)):
            if powers[i-1] > 0 and abs(powers[i] - powers[i-1]) / powers[i-1] > 0.3:
                fluctuations += 1

        triggered = fluctuations >= 3
        risk_score = min(fluctuations * 0.15, 0.98) if fluctuations > 0 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"功率波动次数: {fluctuations} (样本数: {len(powers)})"],
            recommendation="检查驱动器输出稳定性，确认电源滤波是否良好" if triggered else "监控功率稳定性",
            raw_data={"fluctuations": fluctuations, "sample_count": len(powers)},
        )

    @classmethod
    def check_lights_up_during_day(
        cls,
        readings: list[dict],
        threshold: dict | None,
        is_test_mode: bool = False,
    ) -> FaultCheckResult:
        """白天亮灯判断"""
        code = "lights_up_during_day"
        daylight_t = threshold.get("daylight_threshold") if threshold else 50.0

        if is_test_mode:
            return FaultCheckResult(code, False, 0.0, "低", ["设备处于测试模式，跳过检测"])

        # 需要光照度和亮度/功率数据
        light_readings = [(r.get("illuminance", 0), r.get("power", 0), r.get("brightness", 0))
                         for r in readings
                         if r.get("illuminance") is not None]

        if not light_readings:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效光照度读数"])

        # 检测白天亮灯的情况
        day_on_count = sum(1 for ill, p, b in light_readings if ill > daylight_t and (p > 10 or b > 10))
        triggered = day_on_count >= 2
        risk_score = min(day_on_count * 0.2, 0.98) if day_on_count > 0 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"白天亮灯次数: {day_on_count} (光照度阈值: {daylight_t}lux)"],
            recommendation="检查光感传感器是否被遮挡或故障" if triggered else "监控光感数据",
            raw_data={"day_on_count": day_on_count, "daylight_threshold": daylight_t},
        )

    @classmethod
    def check_relay_adhesion(
        cls,
        readings: list[dict],
        rated_power: float | None = None,
        commanded_off: bool = True,
    ) -> FaultCheckResult:
        """继电器粘连判断"""
        code = "relay_adhesion"

        if not commanded_off:
            return FaultCheckResult(code, False, 0.0, "低", ["未发送关灯指令"])

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        if not powers:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率读数"])

        avg_power = sum(powers) / len(powers)
        threshold = rated_power * 0.1 if rated_power else 10.0
        triggered = avg_power > threshold
        risk_score = min(avg_power / (threshold * 5), 0.98) if triggered else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"关灯后平均功率: {avg_power:.1f}W (阈值: {threshold:.1f}W)"],
            recommendation="【紧急】继电器触点粘连，需立即更换继电器或控制器" if triggered else "监控继电器状态",
            raw_data={"avg_power_after_off": avg_power, "threshold": threshold},
        )

    @classmethod
    def check_relay_open(
        cls,
        readings: list[dict],
        rated_power: float | None = None,
        commanded_on: bool = True,
    ) -> FaultCheckResult:
        """继电器断开判断"""
        code = "relay_open"

        if not commanded_on:
            return FaultCheckResult(code, False, 0.0, "低", ["未发送开灯指令"])

        powers = [r.get("power", 0) for r in readings if r.get("power") is not None]
        if not powers:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效功率读数"])

        avg_power = sum(powers) / len(powers)
        threshold = rated_power * 0.1 if rated_power else 10.0
        triggered = avg_power < threshold
        risk_score = min(1.0 - avg_power / threshold, 0.98) if triggered else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"开灯后平均功率: {avg_power:.1f}W (阈值: {threshold:.1f}W)"],
            recommendation="检查继电器触点是否氧化或损坏，需更换继电器" if triggered else "监控继电器状态",
            raw_data={"avg_power_after_on": avg_power, "threshold": threshold},
        )

    @classmethod
    def check_leakage_alarm(
        cls,
        readings: list[dict],
        threshold: dict | None,
    ) -> FaultCheckResult:
        """漏电报警判断"""
        code = "leakage_alarm"
        max_leakage = threshold.get("max_leakage_current") if threshold else 30.0  # mA

        leakages = [r.get("leakage_current", 0) for r in readings if r.get("leakage_current") is not None]
        if not leakages:
            return FaultCheckResult(code, False, 0.0, "低", ["无有效漏电流读数"])

        max_leak = max(leakages)
        triggered = max_leak > max_leakage
        risk_score = min(max_leak / max_leakage * 0.8, 0.98) if max_leak > max_leakage * 0.5 else 0.0

        return FaultCheckResult(
            code, triggered, risk_score, cls._risk_level(risk_score),
            [f"最大漏电流: {max_leak:.1f}mA (阈值: {max_leakage}mA)"],
            recommendation="【紧急】立即断电检查，确认绝缘是否损坏或线路是否进水" if triggered else "监控漏电流趋势",
            raw_data={"max_leakage": max_leak, "threshold": max_leakage},
        )

    # ------------------------------------------------------------------
    # 批量检查入口
    # ------------------------------------------------------------------

    @classmethod
    async def check_all(
        cls,
        device_id: str,
        readings: list[dict],
        threshold: dict | None,
        device_info: dict | None,
        expected_on: bool = True,
        comm_logs: list[dict] | None = None,
        manual_off: bool = False,
        schedule_on: bool = True,
        protection_active: bool = False,
    ) -> list[FaultCheckResult]:
        """
        对单个设备执行所有故障类型的检查

        Args:
            device_id: 设备ID
            readings: 最近读数列表
            threshold: 阈值配置
            device_info: 设备信息（含额定功率等）
            expected_on: 灯是否应处于亮灯状态
            comm_logs: 通信日志列表
            manual_off: 是否手动关灯
            schedule_on: 当前是否在schedule亮灯时段
            protection_active: 是否故障保护触发
        """
        rated_power = device_info.get("rated_power") if device_info else None
        rated_current = device_info.get("rated_current") if device_info else None

        results = []

        # 电气参数类 (Electrical)
        results.append(cls.check_ac_high_main_voltage(readings, threshold))
        results.append(cls.check_ac_low_main_voltage(readings, threshold))
        results.append(cls.check_high_load_power(readings, threshold, rated_power))
        results.append(cls.check_high_load_current(readings, threshold, rated_current))
        results.append(cls.check_low_power_factor(readings, threshold))
        results.append(cls.check_low_load_power(readings, threshold, rated_power, expected_on))
        results.append(cls.check_low_load_current(readings, threshold, rated_current, expected_on))
        results.append(cls.check_abnormal_ac_voltage_fluctuation(readings, threshold))

        # 电源类 (Power)
        results.append(cls.check_ac_on_off_flicker(readings, comm_logs))

        # 温度类 (Temperature)
        results.append(cls.check_high_temperature(readings, threshold))
        results.append(cls.check_temperature_and_humidity_sensor_temperature_too_high(readings, threshold))
        results.append(cls.check_temperature_and_humidity_sensor_temperature_too_low(readings, threshold))
        results.append(cls.check_temperature_and_humidity_sensor_humidity_too_high(readings, threshold))
        results.append(cls.check_temperature_and_humidity_sensor_humidity_too_low(readings, threshold))

        # 传感器类 (Sensor)
        results.append(cls.check_meter_error(readings, comm_logs, expected_on))
        results.append(cls.check_light_perception_error(readings, threshold))
        results.append(cls.check_ext_illsensor_communication_failure(readings, comm_logs))

        # 通信类 (Communication)
        results.append(cls.check_drive_communication_error(readings, comm_logs))
        results.append(cls.check_temperature_and_humidity_sensor_communication_error(readings, comm_logs))
        results.append(cls.check_ctrl_multicast_failed(readings, comm_logs))
        results.append(cls.check_jcmode_syn_signal_failure(readings, comm_logs))

        # 灯具类 (Lamp)
        results.append(cls.check_drive_error(readings, comm_logs))
        results.append(cls.check_lamp_failed(readings, rated_power, expected_on))
        results.append(cls.check_flash_lights(readings))
        results.append(cls.check_lights_up_during_day(readings, threshold))
        results.append(cls.check_lights_off_during_on_time(readings, expected_on, manual_off))
        results.append(cls.check_abnormal_lights_off(readings, schedule_on, manual_off, protection_active))

        # 继电器类 (Relay)
        # 注：继电器检测需要知道指令状态，由调用方传入
        # results.append(cls.check_relay_adhesion(readings, rated_power, commanded_off=False))
        # results.append(cls.check_relay_open(readings, rated_power, commanded_on=False))

        # 安全类 (Safety)
        results.append(cls.check_leakage_alarm(readings, threshold))

        # 按风险评分排序
        results.sort(key=lambda r: r.risk_score, reverse=True)
        return results
