"""Mock 数据生成 — 模拟燃气轮机运行数据和各小模型分析结果。"""

import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np


def generate_realtime_data() -> dict:
    """生成燃气轮机实时 SCADA 监测参数 — 包含四大部件全部测点。"""
    now = datetime.now()

    # --- 压气机 ---
    T1 = round(random.uniform(15, 35), 1)       # 压气机进口温度 °C
    P1 = round(random.uniform(0.095, 0.105), 3)  # 压气机进口压力 MPa
    T2 = round(random.uniform(380, 450), 1)      # 压气机出口温度 °C
    P2 = round(random.uniform(1.4, 1.8), 3)      # 压气机出口压力 MPa

    # --- 燃烧室 ---
    T3 = round(random.uniform(1100, 1300), 0)    # 透平进口/燃烧室出口温度 °C
    P3 = round(P2 - random.uniform(0.03, 0.08), 3)  # 燃烧室出口压力 MPa
    gas_flow_inst = round(random.uniform(4.5, 6.0), 2)   # 天然气瞬时流量 万Nm³/h
    gas_flow_acc = round(random.uniform(8000, 12000), 0)  # 天然气累计流量 万Nm³
    gas_temp = round(random.uniform(10, 30), 1)           # 燃气温度 °C
    gas_pressure = round(random.uniform(2.0, 3.5), 2)     # 燃气压力 MPa
    lhv = round(random.uniform(33, 36), 1)                # 天然气低位热值 MJ/Nm³
    air_flow = round(random.uniform(500, 700), 1)         # 压气机出口空气流量 kg/s
    o2_exhaust = round(random.uniform(12, 16), 1)         # 排烟含氧量 %
    co_exhaust = round(random.uniform(1, 15), 1)          # CO ppm
    uhc_exhaust = round(random.uniform(0.5, 5), 1)        # 未燃碳氢 ppm

    # --- 透平 ---
    T4 = round(random.uniform(520, 580), 1)      # 透平出口/排气温度 °C
    P4 = round(random.uniform(0.100, 0.105), 3)  # 透平出口压力 MPa

    # --- 发电机 ---
    power_inst = round(random.uniform(180, 220), 1)  # 发电机有功功率 MW
    power_acc = round(random.uniform(50000, 80000), 0)  # 累计发电量 MWh

    # --- 汽机侧 (联合循环) ---
    steam_flow = round(random.uniform(60, 90), 1)       # 主蒸汽流量 t/h
    steam_temp = round(random.uniform(480, 540), 1)     # 主蒸汽温度 °C
    steam_pressure = round(random.uniform(3.5, 5.0), 2) # 主蒸汽压力 MPa
    st_power = round(random.uniform(80, 120), 1)        # 汽机发电功率 MW

    # --- 余热锅炉 ---
    hrh_gas_in = round(T4 + random.uniform(-5, 5), 1)   # HRB 进口烟温 °C
    hrh_gas_out = round(random.uniform(80, 110), 1)      # HRB 出口烟温 °C
    hrh_steam_temp = round(random.uniform(480, 530), 1)  # HRB 蒸汽温度 °C
    hrh_steam_press = round(random.uniform(3.0, 4.5), 2) # HRB 蒸汽压力 MPa

    return {
        "timestamp": now.isoformat(),
        "unit_id": "GT-01",
        "parameters": {
            # 压气机
            "压气机进口温度_T1": T1,
            "压气机进口压力_P1": P1,
            "压气机出口温度_T2": T2,
            "压气机出口压力_P2": P2,
            "空气流量": air_flow,
            # 燃烧室
            "透平进口温度_T3": T3,
            "燃烧室出口压力_P3": P3,
            "天然气瞬时流量": gas_flow_inst,
            "天然气累计流量": gas_flow_acc,
            "燃气温度": gas_temp,
            "燃气压力": gas_pressure,
            "天然气低位热值": lhv,
            "排烟含氧量": o2_exhaust,
            "CO排放": co_exhaust,
            "未燃碳氢": uhc_exhaust,
            # 透平
            "透平出口温度_T4": T4,
            "透平出口压力_P4": P4,
            # 发电机
            "发电机有功功率": power_inst,
            "累计发电量": power_acc,
            # 汽机
            "主蒸汽流量": steam_flow,
            "主蒸汽温度": steam_temp,
            "主蒸汽压力": steam_pressure,
            "汽机发电功率": st_power,
            # 余热锅炉
            "HRB进口烟温": hrh_gas_in,
            "HRB出口烟温": hrh_gas_out,
            "HRB蒸汽温度": hrh_steam_temp,
            "HRB蒸汽压力": hrh_steam_press,
            # 其他
            "振动_轴向": round(random.uniform(2.0, 6.0), 2),
            "振动_垂向": round(random.uniform(2.0, 5.5), 2),
        },
        "status": "正常运行" if random.random() > 0.15 else "注意",
        "warnings": random.sample(
            ["排气温度偏高", "振动值上升趋势", "压气机效率下降", "热耗率偏高"],
            k=random.randint(0, 2),
        ),
    }


def generate_efficiency_trend(days: int = 7) -> pd.DataFrame:
    """生成能效指标趋势数据。"""
    now = datetime.now()
    dates = [now - timedelta(days=i) for i in range(days)]
    dates.reverse()

    return pd.DataFrame({
        "日期": dates,
        "热耗率_kJ/kWh": np.random.normal(8200, 150, days).round(0),
        "发电效率_%": np.random.normal(38.5, 1.2, days).round(2),
        "厂用电率_%": np.random.normal(4.8, 0.3, days).round(2),
        "综合厂用电率_%": np.random.normal(5.2, 0.3, days).round(2),
    })


def generate_efficiency_analysis() -> dict:
    """生成能效分析结果 — 包含七大指标及其 SCADA 原始监测值。"""
    now = datetime.now()

    # --- SCADA 原始值 (模拟实时采样) ---
    scada = {
        # 发电气耗
        "天然气瞬时流量": round(random.uniform(4.5, 6.0), 2),  # 万Nm³/h
        "天然气累计流量": round(random.uniform(8000, 12000), 0),  # 万Nm³
        "发电机有功功率": round(random.uniform(180, 220), 1),  # MW
        "累计发电量": round(random.uniform(50000, 80000), 0),  # MWh
        "燃气温度": round(random.uniform(10, 30), 1),  # °C
        "燃气压力": round(random.uniform(2.0, 3.5), 2),  # MPa
        # 压气机
        "压气机进口温度_T1": round(random.uniform(15, 35), 1),
        "压气机进口压力_P1": round(random.uniform(0.095, 0.105), 3),
        "压气机出口温度_T2": round(random.uniform(380, 450), 1),
        "压气机出口压力_P2": round(random.uniform(1.4, 1.8), 3),
        "空气流量": round(random.uniform(500, 700), 1),
        # 燃烧室
        "透平进口温度_T3": round(random.uniform(1100, 1300), 0),
        "燃烧室出口压力_P3": round(random.uniform(1.35, 1.75), 3),
        "天然气低位热值": round(random.uniform(33, 36), 1),  # MJ/Nm³
        "排烟含氧量": round(random.uniform(12, 16), 1),
        "CO排放": round(random.uniform(1, 15), 1),
        "未燃碳氢": round(random.uniform(0.5, 5), 1),
        # 透平
        "透平出口温度_T4": round(random.uniform(520, 580), 1),
        "透平出口压力_P4": round(random.uniform(0.100, 0.105), 3),
        # 汽机 / 余热锅炉
        "主蒸汽流量": round(random.uniform(60, 90), 1),
        "主蒸汽温度": round(random.uniform(480, 540), 1),
        "主蒸汽压力": round(random.uniform(3.5, 5.0), 2),
        "汽机发电功率": round(random.uniform(80, 120), 1),
        "HRB进口烟温": round(random.uniform(520, 580), 1),
        "HRB出口烟温": round(random.uniform(80, 110), 1),
        "HRB蒸汽温度": round(random.uniform(480, 530), 1),
        "HRB蒸汽压力": round(random.uniform(3.0, 4.5), 2),
    }

    # --- 计算七大效率指标 ---
    gas_flow = scada["天然气瞬时流量"]  # 万Nm³/h
    power = scada["发电机有功功率"]  # MW
    lhv = scada["天然气低位热值"]  # MJ/Nm³
    T1 = scada["压气机进口温度_T1"]
    P1 = scada["压气机进口压力_P1"]
    T2 = scada["压气机出口温度_T2"]
    P2 = scada["压气机出口压力_P2"]
    T3 = scada["透平进口温度_T3"]
    T4 = scada["透平出口温度_T4"]
    steam_power = scada["汽机发电功率"]

    # 发电气耗 = 天然气流量 / 发电功率 (Nm³/kWh)
    gas_consumption = round(gas_flow * 10000 / (power * 1000), 4) if power > 0 else 0
    design_gas_consumption = 0.225

    # 压气机等熵效率
    pr = P2 / P1 if P1 > 0 else 1
    import math
    gamma = 1.4
    T2s = (T1 + 273.15) * (pr ** ((gamma - 1) / gamma)) - 273.15
    compressor_eff = round((T2s - T1) / (T2 - T1) * 100, 2) if T2 > T1 else 0
    design_compressor_eff = 88.0

    # 燃烧效率 (简化模型)
    combustion_eff = round(random.uniform(97.5, 99.5), 2)
    design_combustion_eff = 99.0

    # 透平等熵效率
    pr_t = P2 / scada["透平出口压力_P4"] if scada["透平出口压力_P4"] > 0 else 1
    T4s = (T3 + 273.15) / (pr_t ** ((gamma - 1) / gamma)) - 273.15
    turbine_eff = round((T3 - T4) / (T3 - T4s) * 100, 2) if T3 > T4 else 0
    design_turbine_eff = 90.0

    # 热耗率 = 燃料热量(kJ/h) / 发电功率(kW)
    # gas_flow(万Nm³/h) * 10000 = Nm³/h; * LHV(MJ/Nm³) = MJ/h; * 1000 = kJ/h
    # power(MW) * 1000 = kW; heat_rate = kJ/kWh
    heat_rate = round(gas_flow * 10000 * lhv * 1000 / (power * 1000), 0) if power > 0 else 8000
    design_heat_rate = 8000

    # 发电效率 = 3600 / 热耗率 * 100%
    gen_eff = round(3600 / heat_rate * 100, 2) if heat_rate > 0 else 0
    design_gen_eff = round(3600 / design_heat_rate * 100, 2)

    # 联合循环效率 (燃机 + 汽机)
    total_power = power + steam_power
    fuel_heat_mw = gas_flow * 10000 * lhv / 3600  # MJ/h ÷ 3600 = MW_th
    cc_eff = round(total_power / fuel_heat_mw * 100, 2) if fuel_heat_mw > 0 else 0
    design_cc_eff = 58.0

    indicators = {
        "发电气耗": {"value": gas_consumption, "design": design_gas_consumption, "unit": "Nm³/kWh", "best": 0.218},
        "压气机效率": {"value": compressor_eff, "design": design_compressor_eff, "unit": "%", "best": 89.5},
        "燃烧效率": {"value": combustion_eff, "design": design_combustion_eff, "unit": "%", "best": 99.2},
        "透平效率": {"value": turbine_eff, "design": design_turbine_eff, "unit": "%", "best": 91.0},
        "热耗率": {"value": heat_rate, "design": design_heat_rate, "unit": "kJ/kWh", "best": 7950},
        "发电效率": {"value": gen_eff, "design": design_gen_eff, "unit": "%", "best": round(3600 / 7950 * 100, 2)},
        "联合循环效率": {"value": cc_eff, "design": design_cc_eff, "unit": "%", "best": 59.5},
    }

    return {
        "analysis_time": now.isoformat(),
        "unit_id": "GT-01",
        "indicators": indicators,
        "scada": scada,
        "suggestions": random.sample(
            [
                "当前负荷率偏低，建议提升至 90% 以上以改善热耗率",
                "压气机效率下降约 1.5%，建议检查压气机叶片积垢情况",
                "厂用电率偏高，检查辅助系统运行工况",
                "排气温度偏高，关注燃烧器状态和燃气品质",
                "热电比优化空间约 3%，建议调整抽汽量",
            ],
            k=random.randint(2, 4),
        ),
    }


def generate_loss_analysis() -> dict:
    """生成耗差分析结果。"""
    items = [
        {"name": "压气机效率损失", "value": round(random.uniform(0.8, 2.5), 2), "design": 0.5},
        {"name": "燃烧效率损失", "value": round(random.uniform(0.3, 1.2), 2), "design": 0.3},
        {"name": "透平效率损失", "value": round(random.uniform(0.5, 2.0), 2), "design": 0.4},
        {"name": "排气热损失", "value": round(random.uniform(3.0, 5.0), 2), "design": 3.5},
        {"name": "机械损失", "value": round(random.uniform(0.8, 1.5), 2), "design": 1.0},
        {"name": "发电机损失", "value": round(random.uniform(1.0, 2.0), 2), "design": 1.2},
        {"name": "厂用电消耗", "value": round(random.uniform(4.0, 6.0), 2), "design": 4.5},
    ]

    return {
        "analysis_time": datetime.now().isoformat(),
        "unit_id": "GT-01",
        "total_loss": round(sum(i["value"] for i in items), 2),
        "total_design_loss": round(sum(i["design"] for i in items), 2),
        "items": items,
        "major_losses": sorted(
            [i for i in items if i["value"] > i["design"] * 1.2],
            key=lambda x: x["value"] - x["design"],
            reverse=True,
        ),
    }


def generate_benchmark_analysis() -> dict:
    """生成对标分析结果。"""
    indicators = [
        "厂用电率",
        "利用小时",
        "平均发电负荷",
        "负荷率",
        "发电计划完成率",
        "热电比",
        "售电收入",
    ]

    this_unit = [round(random.uniform(3.5, 7.0), 2)]  # 厂用电率 %
    peer_avg = [round(random.uniform(4.0, 5.5), 2)]

    this_unit.append(round(random.uniform(3500, 5000), 0))  # 利用小时 h
    peer_avg.append(round(random.uniform(3800, 4800), 0))

    this_unit.append(round(random.uniform(170, 220), 1))  # 平均发电负荷 MW
    peer_avg.append(round(random.uniform(180, 215), 1))

    this_unit.append(round(random.uniform(75, 98), 1))  # 负荷率 %
    peer_avg.append(round(random.uniform(80, 95), 1))

    this_unit.append(round(random.uniform(88, 100), 1))  # 发电计划完成率 %
    peer_avg.append(round(random.uniform(90, 99), 1))

    this_unit.append(round(random.uniform(0.6, 1.2), 2))  # 热电比
    peer_avg.append(round(random.uniform(0.7, 1.1), 2))

    this_unit.append(round(random.uniform(8000, 15000), 0))  # 售电收入 万元
    peer_avg.append(round(random.uniform(9000, 14000), 0))

    gaps = [
        {
            "indicator": indicators[i],
            "this_unit": this_unit[i],
            "peer_avg": peer_avg[i],
            "gap": round(this_unit[i] - peer_avg[i], 2),
            "unit": ["%", "h", "MW", "%", "%", "", "万元"][i],
        }
        for i in range(len(indicators))
    ]

    return {
        "analysis_time": datetime.now().isoformat(),
        "unit_id": "GT-01",
        "peer_group": "F级燃气轮机机组（同类 6 台）",
        "period": "近 30 天",
        "gaps": gaps,
        "strengths": [g for g in gaps if g["indicator"] in ["厂用电率"] and g["gap"] < 0],
        "weaknesses": sorted(
            [g for g in gaps if abs(g["gap"]) > 0],
            key=lambda x: abs(x["gap"]),
            reverse=True,
        )[:3],
    }
