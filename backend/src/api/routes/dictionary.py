"""数据字典 API — 参数定义、基准值配置、对标指标。"""

from fastapi import APIRouter

router = APIRouter()

# Mock 数据字典 — 与 SCADA 监测参数完全同步
PARAMETERS = [
    # === 压气机 ===
    {"id": "P001", "name": "压气机进口温度 T1", "unit": "°C", "location": "压气机进口", "normal_range": [10, 40], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P002", "name": "压气机进口压力 P1", "unit": "MPa", "location": "压气机进口", "normal_range": [0.09, 0.11], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P003", "name": "压气机出口温度 T2", "unit": "°C", "location": "压气机出口", "normal_range": [380, 460], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P004", "name": "压气机出口压力 P2", "unit": "MPa", "location": "压气机出口", "normal_range": [1.2, 1.9], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P005", "name": "空气流量", "unit": "kg/s", "location": "压气机出口", "normal_range": [480, 720], "source": "时序数据库", "update_freq": "1s"},
    # === 燃烧室 ===
    {"id": "P006", "name": "透平进口温度 T3", "unit": "°C", "location": "燃烧室出口", "normal_range": [1050, 1350], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P007", "name": "燃烧室出口压力 P3", "unit": "MPa", "location": "燃烧室出口", "normal_range": [1.1, 1.8], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P008", "name": "天然气瞬时流量", "unit": "万Nm³/h", "location": "燃料入口", "normal_range": [4.0, 7.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P009", "name": "天然气累计流量", "unit": "万Nm³", "location": "燃料入口", "normal_range": [0, 99999], "source": "时序数据库", "update_freq": "1h"},
    {"id": "P010", "name": "燃气温度", "unit": "°C", "location": "燃料入口", "normal_range": [0, 40], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P011", "name": "燃气压力", "unit": "MPa", "location": "燃料入口", "normal_range": [1.5, 4.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P012", "name": "天然气低位热值", "unit": "MJ/Nm³", "location": "化验室", "normal_range": [31, 38], "source": "定期化验", "update_freq": "1天"},
    {"id": "P013", "name": "排烟含氧量", "unit": "%", "location": "烟囱", "normal_range": [10, 18], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P014", "name": "CO排放", "unit": "ppm", "location": "烟囱", "normal_range": [0, 20], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P015", "name": "未燃碳氢", "unit": "ppm", "location": "烟囱", "normal_range": [0, 10], "source": "时序数据库", "update_freq": "1s"},
    # === 透平 ===
    {"id": "P016", "name": "透平出口温度 T4", "unit": "°C", "location": "透平出口", "normal_range": [500, 600], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P017", "name": "透平出口压力 P4", "unit": "MPa", "location": "透平出口", "normal_range": [0.09, 0.11], "source": "时序数据库", "update_freq": "1s"},
    # === 发电机 ===
    {"id": "P018", "name": "发电机有功功率", "unit": "MW", "location": "发电机出口", "normal_range": [160, 230], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P019", "name": "累计发电量", "unit": "MWh", "location": "发电机出口", "normal_range": [0, 999999], "source": "时序数据库", "update_freq": "1h"},
    # === 汽机侧 ===
    {"id": "P020", "name": "主蒸汽流量", "unit": "t/h", "location": "余热锅炉出口", "normal_range": [50, 100], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P021", "name": "主蒸汽温度", "unit": "°C", "location": "余热锅炉出口", "normal_range": [470, 550], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P022", "name": "主蒸汽压力", "unit": "MPa", "location": "余热锅炉出口", "normal_range": [3.0, 5.5], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P023", "name": "汽机发电功率", "unit": "MW", "location": "汽轮发电机", "normal_range": [70, 130], "source": "时序数据库", "update_freq": "1s"},
    # === 余热锅炉 ===
    {"id": "P024", "name": "HRB进口烟温", "unit": "°C", "location": "余热锅炉进口", "normal_range": [500, 600], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P025", "name": "HRB出口烟温", "unit": "°C", "location": "余热锅炉出口", "normal_range": [70, 130], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P026", "name": "HRB蒸汽温度", "unit": "°C", "location": "余热锅炉", "normal_range": [470, 540], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P027", "name": "HRB蒸汽压力", "unit": "MPa", "location": "余热锅炉", "normal_range": [2.5, 5.0], "source": "时序数据库", "update_freq": "1s"},
    # === 其他 ===
    {"id": "P028", "name": "振动_轴向", "unit": "mm/s", "location": "轴承座", "normal_range": [0, 7.0], "source": "时序数据库", "update_freq": "1s"},
    {"id": "P029", "name": "振动_垂向", "unit": "mm/s", "location": "轴承座", "normal_range": [0, 7.0], "source": "时序数据库", "update_freq": "1s"},
]

BASELINE_CONFIGS = [
    {"parameter_id": "P003", "parameter_name": "压气机出口温度 T2", "model_type": "多元回归", "features": ["负荷率", "进口温度 T1", "进口压力 P1"], "accuracy": 0.98},
    {"parameter_id": "P016", "parameter_name": "透平出口温度 T4", "model_type": "多元回归", "features": ["负荷率", "环境温度", "透平进口温度 T3"], "accuracy": 0.97},
    {"parameter_id": "P008", "parameter_name": "天然气瞬时流量", "model_type": "设计值插值", "features": ["负荷指令", "发电功率"], "accuracy": 0.99},
    {"parameter_id": "P018", "parameter_name": "发电机有功功率", "model_type": "热力模型", "features": ["天然气流量", "热值", "压气机效率"], "accuracy": 0.96},
]

BENCHMARK_INDICATORS = [
    {"id": "B001", "name": "厂用电率", "unit": "%", "source": "对标分析模型", "peer_avg": 4.8},
    {"id": "B002", "name": "利用小时", "unit": "h", "source": "对标分析模型", "peer_avg": 4200},
    {"id": "B003", "name": "平均发电负荷", "unit": "MW", "source": "对标分析模型", "peer_avg": 200},
    {"id": "B004", "name": "负荷率", "unit": "%", "source": "对标分析模型", "peer_avg": 90},
    {"id": "B005", "name": "发电计划完成率", "unit": "%", "source": "对标分析模型", "peer_avg": 95},
    {"id": "B006", "name": "热电比", "unit": "", "source": "对标分析模型", "peer_avg": 0.85},
    {"id": "B007", "name": "售电收入", "unit": "万元", "source": "对标分析模型", "peer_avg": 12000},
]


@router.get("/parameters")
async def get_parameters():
    """获取监测参数定义列表。"""
    return {"parameters": PARAMETERS, "total": len(PARAMETERS)}


@router.get("/baselines")
async def get_baselines():
    """获取动态基准值模型配置。"""
    return {"baselines": BASELINE_CONFIGS, "total": len(BASELINE_CONFIGS)}


@router.get("/benchmark-indicators")
async def get_benchmark_indicators():
    """获取对标指标配置。"""
    return {"indicators": BENCHMARK_INDICATORS, "total": len(BENCHMARK_INDICATORS)}
