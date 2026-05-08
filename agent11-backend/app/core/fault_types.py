"""
标准故障类型定义模块

定义路灯控制系统所有支持的故障类型，包含：
- 故障编码（英文 snake_case，系统唯一标识）
- 故障名称（中文）
- 1.0 版本支持状态
- 是否需要预测
- 是否需要客户推送
- 判断逻辑说明
- 预测所需数据源
- 严重程度级别
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class FaultSeverity(str, Enum):
    """故障严重程度"""
    CRITICAL = "critical"      # 紧急：需立即处理（漏电、继电器粘连等）
    HIGH = "high"              # 高：需尽快处理（灯不亮、电压异常等）
    MEDIUM = "medium"          # 中：需安排处理（通信错误、传感器异常等）
    LOW = "low"                # 低：可延后处理（轻微阈值越界等）


class FaultCategory(str, Enum):
    """故障分类"""
    ELECTRICAL = "electrical"           # 电气参数类
    TEMPERATURE = "temperature"         # 温度类
    SENSOR = "sensor"                   # 传感器类
    COMMUNICATION = "communication"     # 通信类
    LAMP = "lamp"                       # 灯具类
    RELAY = "relay"                     # 继电器类
    CONTROL = "control"                 # 控制类
    POWER = "power"                     # 电源类
    SAFETY = "safety"                   # 安全类


@dataclass(frozen=True)
class FaultTypeDef:
    """故障类型定义"""
    code: str                           # 故障编码（系统唯一标识）
    name_cn: str                        # 中文名称
    name_en: str                        # 英文名称
    category: FaultCategory             # 故障分类
    severity: FaultSeverity             # 严重程度
    supported_v1: bool                  # 1.0 版本是否支持
    needs_prediction: bool              # 是否需要预测
    needs_push: bool                    # 是否需要客户推送
    logic_description: str              # 判断逻辑描述
    data_sources: list[str]             # 所需数据源
    prediction_method: str              # 预测方法说明
    threshold_params: list[str] = field(default_factory=list)  # 关联的阈值参数名


# =============================================================================
# 故障类型注册表
# =============================================================================

FAULT_TYPE_REGISTRY: dict[str, FaultTypeDef] = {}


def _register(ft: FaultTypeDef) -> FaultTypeDef:
    """注册故障类型到全局注册表"""
    FAULT_TYPE_REGISTRY[ft.code] = ft
    return ft


# ---------------------------------------------------------------------------
# 1. 电气参数类 (Electrical)
# ---------------------------------------------------------------------------

AC_HIGH_MAIN_VOLTAGE = _register(FaultTypeDef(
    code="ac_high_main_voltage",
    name_cn="AC主电压过高",
    name_en="AC High Main Voltage",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="主回路电压连续3个采样周期超过阈值上限(max_voltage)，或单日最大值超过阈值上限的110%",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于电压历史趋势：若近7天电压呈上升趋势且接近阈值上限的90%，则预测未来24h可能越界",
    threshold_params=["max_voltage"],
))

AC_LOW_MAIN_VOLTAGE = _register(FaultTypeDef(
    code="ac_low_main_voltage",
    name_cn="AC主电压过低",
    name_en="AC Low Main Voltage",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="主回路电压连续3个采样周期低于阈值下限(min_voltage)，或单日最小值低于阈值下限的90%",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于电压历史趋势：若近7天电压呈下降趋势且接近阈值下限的110%，则预测未来24h可能越界",
    threshold_params=["min_voltage"],
))

HIGH_LOAD_POWER = _register(FaultTypeDef(
    code="high_load_power",
    name_cn="负载功率过高",
    name_en="High Load Power",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="负载功率连续3个采样周期超过阈值上限(max_power)，或超过额定功率的120%",
    data_sources=["device_readings", "device_threshold", "device_info"],
    prediction_method="基于功率历史趋势：若近7天功率均值超过阈值上限的85%，则预测未来7d可能越界",
    threshold_params=["max_power"],
))

HIGH_LOAD_CURRENT = _register(FaultTypeDef(
    code="high_load_current",
    name_cn="负载电流过高",
    name_en="High Load Current",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="负载电流连续3个采样周期超过阈值上限(max_current)，或超过额定电流的120%",
    data_sources=["device_readings", "device_threshold", "device_info"],
    prediction_method="基于电流历史趋势：若近7天电流均值超过阈值上限的85%，则预测未来7d可能越界",
    threshold_params=["max_current"],
))

LOW_POWER_FACTOR = _register(FaultTypeDef(
    code="low_power_factor",
    name_cn="功率因素过低",
    name_en="Low Power Factor",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.LOW,
    supported_v1=False,
    needs_prediction=True,
    needs_push=False,
    logic_description="功率因素连续3个采样周期低于阈值下限(min_power_factor)，通常低于0.85",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于功率因素历史趋势：若近14天功率因素持续低于0.9且呈下降趋势，则预测可能越界",
    threshold_params=["min_power_factor"],
))

LOW_LOAD_POWER = _register(FaultTypeDef(
    code="low_load_power",
    name_cn="负载功率过低",
    name_en="Low Load Power",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="灯应亮时（schedule/手动开灯）功率连续低于阈值下限(min_power)或额定功率的30%",
    data_sources=["device_readings", "device_threshold", "device_info"],
    prediction_method="基于功率历史趋势：若近7天功率均值低于额定功率的50%，预测灯具衰减或驱动故障",
    threshold_params=["min_power"],
))

LOW_LOAD_CURRENT = _register(FaultTypeDef(
    code="low_load_current",
    name_cn="负载电流过低",
    name_en="Low Load Current",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="灯应亮时电流连续低于阈值下限(min_current)或额定电流的30%",
    data_sources=["device_readings", "device_threshold", "device_info"],
    prediction_method="基于电流历史趋势：若近7天电流均值低于额定电流的50%，预测灯具衰减或驱动故障",
    threshold_params=["min_current"],
))

ABNORMAL_AC_VOLTAGE_FLUCTUATION = _register(FaultTypeDef(
    code="abnormal_ac_voltage_fluctuation",
    name_cn="AC电压异常波动",
    name_en="Abnormal AC Voltage Fluctuation",
    category=FaultCategory.ELECTRICAL,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="单日电压标准差超过正常波动范围（如>阈值范围的15%），或短时间内电压变化率超过10%/min",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于电压方差趋势：若近3天电压方差逐日增大，预测电网不稳定即将引发故障",
    threshold_params=["max_voltage", "min_voltage"],
))

AC_ON_OFF_FLICKER = _register(FaultTypeDef(
    code="ac_on_off_flicker",
    name_cn="AC电通断闪烁",
    name_en="AC On-Off Flicker",
    category=FaultCategory.POWER,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="1小时内电源通断（电压从有到无）次数超过阈值（如>3次），或灯具频繁亮灭",
    data_sources=["device_readings", "comm_logs"],
    prediction_method="基于电源事件频率：若近24h电源中断事件>2次，预测接触不良或电网问题",
    threshold_params=[],
))


# ---------------------------------------------------------------------------
# 2. 温度类 (Temperature)
# ---------------------------------------------------------------------------

HIGH_TEMPERATURE = _register(FaultTypeDef(
    code="high_temperature",
    name_cn="温度过高",
    name_en="High Temperature",
    category=FaultCategory.TEMPERATURE,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="设备内部温度连续3个采样周期超过阈值上限(max_temperature)，通常>85°C",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于温度趋势：若近6h温度上升速率>5°C/h且接近阈值上限的90%，预测未来4h可能越界",
    threshold_params=["max_temperature"],
))

TEMPERATURE_AND_HUMIDITY_SENSOR_TEMPERATURE_TOO_HIGH = _register(FaultTypeDef(
    code="temperature_and_humidity_sensor_temperature_too_high",
    name_cn="温湿度传感器温度过高",
    name_en="Temperature Sensor Temperature Too High",
    category=FaultCategory.TEMPERATURE,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=False,
    logic_description="环境温湿度传感器读数连续超过阈值上限(max_env_temperature)",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于环境温度趋势：若近12h环境温度持续上升，预测可能触发高温保护",
    threshold_params=["max_env_temperature"],
))

TEMPERATURE_AND_HUMIDITY_SENSOR_TEMPERATURE_TOO_LOW = _register(FaultTypeDef(
    code="temperature_and_humidity_sensor_temperature_too_low",
    name_cn="温湿度传感器温度过低",
    name_en="Temperature Sensor Temperature Too Low",
    category=FaultCategory.TEMPERATURE,
    severity=FaultSeverity.LOW,
    supported_v1=False,
    needs_prediction=True,
    needs_push=False,
    logic_description="环境温湿度传感器读数连续低于阈值下限(min_env_temperature)",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于环境温度趋势：若近12h环境温度持续下降，预测可能影响设备启动",
    threshold_params=["min_env_temperature"],
))

TEMPERATURE_AND_HUMIDITY_SENSOR_HUMIDITY_TOO_HIGH = _register(FaultTypeDef(
    code="temperature_and_humidity_sensor_humidity_too_high",
    name_cn="温湿度传感器湿度过高",
    name_en="Temperature Sensor Humidity Too High",
    category=FaultCategory.TEMPERATURE,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=False,
    logic_description="环境湿度连续超过阈值上限(max_humidity)，通常>85%RH",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于湿度趋势：若近24h湿度持续>80%RH，预测可能引发凝露或短路",
    threshold_params=["max_humidity"],
))

TEMPERATURE_AND_HUMIDITY_SENSOR_HUMIDITY_TOO_LOW = _register(FaultTypeDef(
    code="temperature_and_humidity_sensor_humidity_too_low",
    name_cn="温湿度传感器湿度过低",
    name_en="Temperature Sensor Humidity Too Low",
    category=FaultCategory.TEMPERATURE,
    severity=FaultSeverity.LOW,
    supported_v1=False,
    needs_prediction=True,
    needs_push=False,
    logic_description="环境湿度连续低于阈值下限(min_humidity)",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于湿度趋势：干燥环境一般无需预测，仅记录",
    threshold_params=["min_humidity"],
))


# ---------------------------------------------------------------------------
# 3. 传感器类 (Sensor)
# ---------------------------------------------------------------------------

METER_ERROR = _register(FaultTypeDef(
    code="meter_error",
    name_cn="电表错误",
    name_en="Meter Error",
    category=FaultCategory.SENSOR,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="电表数据异常：灯亮时能耗为0、能耗读数跳变>50%/周期、电表通信返回错误码",
    data_sources=["device_readings", "energy_readings", "comm_logs"],
    prediction_method="基于电表数据一致性：若近3天出现>2次能耗异常跳变，预测电表即将故障",
    threshold_params=[],
))

LIGHT_PERCEPTION_ERROR = _register(FaultTypeDef(
    code="light_perception_error",
    name_cn="光感错误",
    name_en="Light Perception Error",
    category=FaultCategory.SENSOR,
    severity=FaultSeverity.MEDIUM,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="光照度传感器数据异常：白天读数<阈值（如被遮挡）、夜间读数异常高、读数长时间不变",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于光感数据一致性：若近3天光感读数与预期日照模式偏差>30%，预测传感器故障",
    threshold_params=["daylight_threshold"],
))

EXT_ILLSENSOR_COMMUNICATION_FAILURE = _register(FaultTypeDef(
    code="ext_illsensor_communication_failure",
    name_cn="外接光照度传感器通信故障",
    name_en="External Illuminance Sensor Communication Failure",
    category=FaultCategory.SENSOR,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="外接光照度传感器连续3次通信超时或无响应",
    data_sources=["comm_logs", "device_readings"],
    prediction_method="基于通信成功率：若近24h通信成功率<90%，预测传感器即将离线",
    threshold_params=[],
))


# ---------------------------------------------------------------------------
# 4. 通信类 (Communication)
# ---------------------------------------------------------------------------

DRIVE_COMMUNICATION_ERROR = _register(FaultTypeDef(
    code="drive_communication_error",
    name_cn="驱动通信错误",
    name_en="Drive Communication Error",
    category=FaultCategory.COMMUNICATION,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="与LED驱动器通信连续3次超时、返回错误帧、CRC校验失败",
    data_sources=["comm_logs"],
    prediction_method="基于驱动通信成功率：若近24h通信成功率<95%，预测驱动通信模块故障",
    threshold_params=[],
))

TEMPERATURE_AND_HUMIDITY_SENSOR_COMMUNICATION_ERROR = _register(FaultTypeDef(
    code="temperature_and_humidity_sensor_communication_error",
    name_cn="温湿度传感器通信错误",
    name_en="Temperature And Humidity Sensor Communication Error",
    category=FaultCategory.COMMUNICATION,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="温湿度传感器连续3次通信超时或无响应",
    data_sources=["comm_logs", "device_readings"],
    prediction_method="基于传感器通信成功率：若近24h通信成功率<90%，预测传感器即将离线",
    threshold_params=[],
))

CTRL_MULTICAST_FAILED = _register(FaultTypeDef(
    code="ctrl_multicast_failed",
    name_cn="设备自控组播失败",
    name_en="Control Multicast Failed",
    category=FaultCategory.COMMUNICATION,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="自控组播命令发出后，目标设备未在预期时间内响应或状态未改变",
    data_sources=["comm_logs", "device_readings"],
    prediction_method="基于组播响应率：若近7天组播响应率<95%，预测通信网络不稳定",
    threshold_params=[],
))

JCMODE_SYN_SIGNAL_FAILURE = _register(FaultTypeDef(
    code="jcmode_syn_signal_failure",
    name_cn="联控模式同步信号故障",
    name_en="JCMode Sync Signal Failure",
    category=FaultCategory.COMMUNICATION,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="联控模式下主控设备与从控设备状态不同步，或同步信号丢失",
    data_sources=["comm_logs", "device_readings"],
    prediction_method="基于同步延迟：若近3天同步延迟>5s的频率增加，预测同步信号故障",
    threshold_params=[],
))


# ---------------------------------------------------------------------------
# 5. 灯具类 (Lamp)
# ---------------------------------------------------------------------------

DRIVE_ERROR = _register(FaultTypeDef(
    code="drive_error",
    name_cn="驱动器错误",
    name_en="Drive Error",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="LED驱动器返回错误状态码（过温/过压/开路/短路等）或驱动器无响应",
    data_sources=["comm_logs", "device_readings"],
    prediction_method="基于驱动器状态历史：若近7天驱动错误次数>0，预测驱动器即将失效",
    threshold_params=[],
))

LAMP_FAILED = _register(FaultTypeDef(
    code="lamp_failed",
    name_cn="灯失败",
    name_en="Lamp Failed",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="灯应亮时（schedule/手动）但实际不亮：power≈0 且 brightness≈0 持续>5分钟",
    data_sources=["device_readings", "device_info"],
    prediction_method="基于能耗趋势：若近14天功率逐日下降>20%，预测灯即将完全失效",
    threshold_params=[],
))

FLASH_LIGHTS = _register(FaultTypeDef(
    code="flash_lights",
    name_cn="闪灯",
    name_en="Flash Lights",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="灯在正常亮灯状态下亮度/功率在短时间内频繁波动（1小时内波动次数>阈值）",
    data_sources=["device_readings"],
    prediction_method="基于功率波动频率：若近3天功率标准差增大且波动次数增加，预测驱动不稳定",
    threshold_params=[],
))

LIGHTS_UP_DURING_DAY = _register(FaultTypeDef(
    code="lights_up_during_day",
    name_cn="白天亮灯",
    name_en="Lights Up During Day",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.MEDIUM,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="光照度>daylight_threshold（如>50lux）且灯处于亮灯状态（非测试模式）",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于光感+schedule：若光感读数持续异常且与schedule冲突，预测光感故障导致误亮",
    threshold_params=["daylight_threshold"],
))

LIGHTS_OFF_DURING_ON_TIME = _register(FaultTypeDef(
    code="lights_off_during_on_time",
    name_cn="亮灯时间关灯",
    name_en="Lights Off During On-Time",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="在schedule亮灯时段内，灯处于关灯状态且非手动控制关闭",
    data_sources=["device_readings", "device_info"],
    prediction_method="基于schedule执行率：若近7天schedule亮灯执行率<98%，预测控制逻辑或继电器故障",
    threshold_params=[],
))

ABNORMAL_LIGHTS_OFF = _register(FaultTypeDef(
    code="abnormal_lights_off",
    name_cn="异常关灯",
    name_en="Abnormal Lights Off",
    category=FaultCategory.LAMP,
    severity=FaultSeverity.HIGH,
    supported_v1=False,
    needs_prediction=True,
    needs_push=True,
    logic_description="非schedule时段、非手动控制、非故障保护情况下灯突然熄灭",
    data_sources=["device_readings", "comm_logs"],
    prediction_method="基于关灯事件异常性：若近7天出现异常关灯事件>1次，预测电源或继电器问题",
    threshold_params=[],
))


# ---------------------------------------------------------------------------
# 6. 继电器类 (Relay)
# ---------------------------------------------------------------------------

RELAY_ADHESION = _register(FaultTypeDef(
    code="relay_adhesion",
    name_cn="继电器粘连",
    name_en="Relay Adhesion",
    category=FaultCategory.RELAY,
    severity=FaultSeverity.CRITICAL,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="发送关灯指令后功率>额定功率的10%且持续>1分钟，说明继电器触点粘连无法断开",
    data_sources=["device_readings", "device_info"],
    prediction_method="基于继电器动作历史：若近30天继电器动作次数超过额定寿命的80%，预测粘连风险",
    threshold_params=[],
))

RELAY_OPEN = _register(FaultTypeDef(
    code="relay_open",
    name_cn="继电器断开",
    name_en="Relay Open",
    category=FaultCategory.RELAY,
    severity=FaultSeverity.HIGH,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="发送开灯指令后功率<额定功率的10%且持续>1分钟，说明继电器触点断开无法闭合",
    data_sources=["device_readings", "device_info"],
    prediction_method="基于继电器动作历史：若近30天继电器动作次数超过额定寿命的80%，预测开路风险",
    threshold_params=[],
))


# ---------------------------------------------------------------------------
# 7. 安全类 (Safety)
# ---------------------------------------------------------------------------

LEAKAGE_ALARM = _register(FaultTypeDef(
    code="leakage_alarm",
    name_cn="漏电报警",
    name_en="Leakage Alarm",
    category=FaultCategory.SAFETY,
    severity=FaultSeverity.CRITICAL,
    supported_v1=True,
    needs_prediction=True,
    needs_push=True,
    logic_description="漏电流超过安全阈值（如>30mA），或漏电流逐日增大",
    data_sources=["device_readings", "device_threshold"],
    prediction_method="基于漏电流趋势：若近7天漏电流呈上升趋势且超过阈值50%，预测即将触发漏电保护",
    threshold_params=["max_leakage_current"],
))


# =============================================================================
# 辅助函数
# =============================================================================

def get_fault_type(code: str) -> FaultTypeDef | None:
    """根据编码获取故障类型定义"""
    return FAULT_TYPE_REGISTRY.get(code)


def list_all_fault_types() -> list[FaultTypeDef]:
    """获取所有故障类型定义"""
    return list(FAULT_TYPE_REGISTRY.values())


def list_predictable_faults() -> list[FaultTypeDef]:
    """获取所有需要预测的故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if ft.needs_prediction]


def list_pushable_faults() -> list[FaultTypeDef]:
    """获取所有需要客户推送的故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if ft.needs_push]


def list_v1_supported_faults() -> list[FaultTypeDef]:
    """获取1.0版本已支持的故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if ft.supported_v1]


def list_v1_pending_faults() -> list[FaultTypeDef]:
    """获取1.0版本待支持的故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if not ft.supported_v1]


def get_faults_by_category(category: FaultCategory) -> list[FaultTypeDef]:
    """按分类获取故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if ft.category == category]


def get_faults_by_severity(severity: FaultSeverity) -> list[FaultTypeDef]:
    """按严重程度获取故障类型"""
    return [ft for ft in FAULT_TYPE_REGISTRY.values() if ft.severity == severity]


def to_table_dict() -> list[dict]:
    """导出为表格字典（用于报表/API返回）"""
    return [
        {
            "故障名称": ft.name_cn,
            "故障编码": ft.code,
            "1.0版本是否支持": "Y" if ft.supported_v1 else "",
            "是否需要预测": "Y" if ft.needs_prediction else "",
            "是否需要客户推送": "Y" if ft.needs_push else "",
            "判断逻辑": ft.logic_description,
            "严重程度": ft.severity.value,
            "分类": ft.category.value,
        }
        for ft in sorted(FAULT_TYPE_REGISTRY.values(), key=lambda x: (x.category.value, x.severity.value))
    ]
