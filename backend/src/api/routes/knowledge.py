"""模型与知识库 API — 小模型接口注册、知识库管理。"""

import httpx
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

router = APIRouter()

# Mock 小模型 API 注册数据
MODEL_APIS = [
    {"id": "M001", "name": "预警诊断模型", "url": "http://192.168.1.100:8001/api/warning", "method": "POST", "input_params": ["unit_id", "parameters"], "output_format": "warning_list", "status": "online", "last_check": "2026-05-10 09:00:00"},
    {"id": "M002", "name": "能效分析模型", "url": "http://192.168.1.100:8002/api/efficiency", "method": "POST", "input_params": ["unit_id", "time_range"], "output_format": "efficiency_report", "status": "online", "last_check": "2026-05-10 09:00:00"},
    {"id": "M003", "name": "耗差分析模型", "url": "http://192.168.1.100:8003/api/loss", "method": "POST", "input_params": ["unit_id", "time_range"], "output_format": "loss_report", "status": "online", "last_check": "2026-05-10 09:00:00"},
    {"id": "M004", "name": "对标分析模型", "url": "http://192.168.1.100:8004/api/benchmark", "method": "POST", "input_params": ["unit_id", "peer_group"], "output_format": "benchmark_report", "status": "offline", "last_check": "2026-05-10 08:55:00"},
]

# Mock 知识库数据 — 包含完整专业内容
KNOWLEDGE_BASE = {
    "maintenance": [
        {
            "id": "K001",
            "title": "压气机叶片积垢在线清洗规程",
            "category": "压气机",
            "type": "检修规程",
            "equipment": "压气机叶片（静叶/动叶）",
            "severity": "中",
            "keywords": ["压气机", "叶片", "积垢", "在线清洗", "离线清洗"],
            "symptoms": "压气机出口压力 P2 持续下降超过 0.05 MPa；压气机等熵效率低于设计值 2% 以上；空气流量下降明显；机组在同负荷下燃料消耗增加。运行中可观察到压气机出口温度 T2 偏高（相同压比下熵增导致）。",
            "analysis": "压气机进口空气中的灰尘、油污、盐分等杂质在叶片表面沉积，导致叶片型线改变、流道截面积减小、表面粗糙度增加。积垢使气流分离提前发生，降低压气机效率和压比。沿海或工业污染区域运行的机组尤为严重。空气过滤器效率不足或维护不及时会加速积垢。",
            "solution": "1. 在线清洗：保持机组在 50%~70% 负荷运行，通过压气机进口清洗喷嘴注入清洗液（去离子水 + 专用清洗剂，按 1:20 比例配制），每次清洗持续 15~20 分钟，观察出口压力恢复情况。\n2. 离线清洗：停机冷却至 80°C 以下，拆除压气机上半缸检查，用高压清洗枪逐级清洗叶片正反面，重点清理叶根和叶冠积垢区域。\n3. 清洗后需做动平衡校验，首次启动后监测振动值变化。\n4. 若积垢严重（效率下降 > 5%），建议停机进行全面离线清洗。",
            "prevention": "1. 定期检查和更换空气过滤器滤芯（一般 2000~4000 小时更换周期）。\n2. 每季度执行一次在线清洗，高粉尘环境下缩短为每月一次。\n3. 监控压气机效率趋势，建立效率-压比基准线，偏离超过 2% 即启动清洗流程。\n4. 安装环境监测设备，在大气污染高发期提前安排清洗。",
            "updated": "2026-04-15",
            "source": "manual",
            "content_type": "text",
        },
        {
            "id": "K002",
            "title": "燃烧器喷嘴堵塞故障诊断与处理",
            "category": "燃烧室",
            "type": "故障诊断",
            "equipment": "燃烧器燃料喷嘴（DLN 燃烧器）",
            "severity": "高",
            "keywords": ["燃烧器", "喷嘴", "堵塞", "压差", "DLN", "NOx"],
            "symptoms": "燃烧室出口各热电偶温度分布不均匀性增大，分散度超过设计允许值（通常 ±30°C）；排烟 CO 排放突然升高；NOx 排放异常波动；燃料母管压力升高但天然气瞬时流量不变或下降；燃烧脉动（动态压力）幅值增大，可能触发燃烧监测保护。",
            "analysis": "喷嘴堵塞通常由以下原因引起：\n1. 天然气中携带的粉尘、铁锈、管道施工残留物在喷嘴小孔处积聚。\n2. 燃气调压站过滤精度不足或滤芯破损。\n3. 长期低负荷运行导致喷嘴出口温度低，燃气中的重烃组分凝结附着。\n4. 检修后管道吹扫不彻底。堵塞导致该喷嘴对应的燃料分配不均，局部燃烧温度偏离设计值，引起热应力增大和排放恶化。",
            "solution": "1. 紧急处理：降低负荷至 50% 以下，观察温度分散度是否改善。若改善，确认喷嘴堵塞。\n2. 在线处理：利用机组停备期间，通过燃料管路反吹口引入高压氮气进行反吹疏通。\n3. 停机处理：拆卸堵塞喷嘴，用超声波清洗设备清洗喷嘴内部流道。对于 DLN 燃烧器，需同时检查预混旋流器是否堵塞。\n4. 更换损坏喷嘴：若喷嘴孔径已变形或内壁损伤，需更换新喷嘴（建议备 2~3 支备件）。\n5. 系统清洗：清洗完成后，检查燃料管路调压站至喷嘴前所有过滤器。",
            "prevention": "1. 确保燃料气调压站过滤精度达到 5μm 以下，定期更换滤芯。\n2. 每次检修后严格执行燃料管路吹扫程序。\n3. 监控燃料母管压差趋势，超过基准值 10% 时安排检查。\n4. 避免长期极低负荷运行（< 30% 额定负荷）。\n5. 定期化验天然气组分，关注重烃含量变化。",
            "updated": "2026-04-20",
            "source": "manual",
            "content_type": "text",
        },
        {
            "id": "K003",
            "title": "透平叶片高温氧化与裂纹无损检测标准",
            "category": "透平",
            "type": "检测标准",
            "equipment": "透平一级/二级动叶、静叶",
            "severity": "高",
            "keywords": ["透平", "叶片", "裂纹", "无损检测", "高温氧化", "TBC"],
            "symptoms": "透平出口温度 T4 分布出现局部热点（某热电偶偏高 20°C 以上）；振动值在暖机阶段异常升高；透平效率持续下降。内窥镜检查可见叶片表面热障涂层（TBC）剥落、叶尖间隙增大、前缘出现微裂纹。",
            "analysis": "透平叶片长期在 1100~1300°C 高温燃气环境下工作，承受高温氧化、热疲劳和蠕变三重损伤。叶片表面的热障涂层（TBC）在热循环作用下产生热应力，导致涂层开裂和剥落。剥落后基体合金直接暴露于高温燃气中，加速氧化和裂纹萌生。裂纹通常从叶片前缘、尾缘或冷却孔边缘开始扩展。透平一级叶片承受温度最高，是最易失效的部位。",
            "solution": "1. 无损检测方法：\n   - 荧光渗透检测（FPI）：检测叶片表面开口裂纹，灵敏度 0.1mm。\n   - 涡流检测：检测近表面裂纹和涂层厚度变化。\n   - 工业内窥镜：检查叶片内部冷却通道堵塞和表面状况。\n   - X 射线检测：对重点怀疑区域进行体积型缺陷检测。\n2. 评估标准：\n   - 裂纹长度 < 2mm 且非关键部位：可继续运行，缩短检测周期至 2000 小时。\n   - 裂纹长度 2~5mm：在下个检修窗口更换叶片。\n   - 裂纹长度 > 5mm 或位于叶根/榫槽：立即更换，禁止继续运行。\n   - TBC 面积剥落 > 10%：安排重新喷涂或更换叶片。",
            "prevention": "1. 严格控制透平进口温度 T3 不超过设计允许上限。\n2. 优化启停速率，避免急剧温度变化造成热冲击。\n3. 每 8000 小时（约 1 年）安排一次内窥镜检查。\n4. 建立叶片寿命管理系统，记录每片叶片的累计运行时间和启停次数。\n5. 监控冷却空气压力，确保叶片内部冷却有效。",
            "updated": "2026-03-10",
            "source": "manual",
            "content_type": "text",
        },
        {
            "id": "K004",
            "title": "燃气轮机大修周期与关键检修项目清单",
            "category": "整机",
            "type": "检修规程",
            "equipment": "燃气轮机整机（含压气机、燃烧室、透平、发电机）",
            "severity": "中",
            "keywords": ["大修", "周期", "检修项目", "燃烧检验", "热通道"],
            "symptoms": "运行指标全面偏离设计值：热耗率上升超过 5%，联合循环效率下降 3% 以上，各部件效率持续劣化且在线维护无法恢复。累计运行达到检修周期（燃烧检验 8000h / 热通道检验 24000h / 大修 48000h）。",
            "analysis": "燃气轮机检修分为三个等级：\n1. 燃烧检验（CI，8000 小时）：检查燃烧器、火焰筒、过渡段等燃烧室部件。\n2. 热通道检验（HGP，24000 小时）：覆盖燃烧检验全部内容，增加透平叶片、喷嘴环检查。\n3. 大修（MI，48000 小时）：全机解体检查，包括压气机叶片、转子、轴承、气缸等全部部件。检修周期的制定基于制造商推荐的等效运行小时数，需综合考虑实际运行工况（燃料类型、启停次数、负荷变化率）进行修正。",
            "solution": "大修主要项目清单：\n1. 压气机：叶片清洗/更换、入口导叶（IGV）执行机构校验、气缸中分面密封检查。\n2. 燃烧室：燃烧器喷嘴清洗/更换、火焰筒检查、过渡段裂纹检查与补焊、燃料分配阀校验。\n3. 透平：各级叶片无损检测、叶片更换（达到寿命上限）、热障涂层重新喷涂、叶尖间隙测量与调整。\n4. 转子：轴承间隙测量、轴颈检查、动平衡校验、联轴器对中。\n5. 密封系统：所有迷宫密封和碳环密封间隙检查与更换。\n6. 控制系统：传感器校验、伺服阀特性试验、保护定值校验。\n7. 发电机：绕组绝缘测试、冷却系统检查、励磁碳刷更换。\n8. 辅机系统：润滑油系统清洗、液压油系统滤芯更换、冷却水系统化学清洗。",
            "prevention": "1. 严格执行制造商推荐的检修周期，不超期运行。\n2. 建立完整的设备台账和检修档案。\n3. 每次检修后进行全套性能试验，建立修后基准数据。\n4. 制定备件储备计划，关键备件（叶片、轴承、密封件）提前 6 个月采购。\n5. 检修过程中执行严格的质量控制和验收标准。",
            "updated": "2026-05-01",
            "source": "manual",
            "content_type": "text",
        },
        {
            "id": "K005",
            "title": "发电机轴承振动异常诊断处理案例",
            "category": "发电机",
            "type": "处理案例",
            "equipment": "发电机前后轴承（#1/#2 轴承）",
            "severity": "高",
            "keywords": ["振动", "轴承", "轴向", "垂向", "动平衡", "不对中"],
            "symptoms": "振动_轴向或振动_垂向持续超过 4.5 mm/s 报警值；振动频谱分析显示 1 倍频（1X）分量为主（不平衡）或 2 倍频（2X）分量为主（不对中）；振动值随转速变化明显；轴承温度可能同时升高。",
            "analysis": "振动异常是燃气轮机最常见的机械故障之一，主要原因按概率排序：\n1. 转子质量不平衡（约占 40%）：叶片磨损/断裂、积垢脱落不均、平衡块松动。\n2. 轴系不对中（约占 25%）：热膨胀导致基础标高变化、联轴器对中超差、管道热膨胀力传递。\n3. 轴承故障（约占 15%）：巴氏合金磨损、油膜振荡、润滑油品质劣化。\n4. 结构共振（约占 10%）：支撑刚度变化、基础松动。\n5. 其他（约占 10%）：电磁激振、热弯曲等。频谱分析是定位振动原因的关键手段。",
            "solution": "1. 频谱分析定位：\n   - 1X 为主 → 质量不平衡 → 安排现场动平衡。\n   - 2X 为主 → 不对中 → 检查并重新对中联轴器。\n   - 0.42~0.48X 出现 → 油膜涡动/振荡 → 调整轴承间隙和润滑油参数。\n   - 宽频随机振动 → 轴承损伤 → 安排更换轴承。\n2. 紧急处理：振动超跳闸值（通常 11 mm/s）立即停机。振动在报警值和跳闸值之间，降低负荷并安排检修。\n3. 现场动平衡：在透平端和发电机端分别加重，目标将振动值降至 2.8 mm/s 以下。\n4. 联轴器对中：使用激光对中仪，确保冷态对中值预留热膨胀补偿量。",
            "prevention": "1. 每日巡检记录振动趋势，建立振动基准数据库。\n2. 定期进行油样光谱分析，监控轴承磨损金属元素含量。\n3. 每 8000 小时检查轴承间隙和巴氏合金表面状况。\n4. 严格控制润滑油温度和压力在正常范围内。\n5. 避免机组在临界转速区间长时间停留。",
            "updated": "2026-04-28",
            "source": "manual",
            "content_type": "text",
        },
        {
            "id": "K006",
            "title": "余热锅炉受热面管束泄漏应急处理规程",
            "category": "余热锅炉",
            "type": "检修规程",
            "equipment": "HRB 高压蒸发器/过热器管束",
            "severity": "高",
            "keywords": ["余热锅炉", "管束泄漏", "爆管", "给水品质", "蒸汽温度"],
            "symptoms": "HRB 出口烟温异常升高（给水泄漏导致蒸汽量减少、换热面积减小）；主蒸汽流量异常波动；HRB 蒸汽压力不稳定；给水流量与蒸汽流量不平衡（给水 > 蒸汽 + 排污）；可能听到炉内有异响（蒸汽喷射声）；烟囱冒白烟加重。",
            "analysis": "管束泄漏主要原因：\n1. 给水品质不合格导致管内壁结垢和腐蚀，局部过热→蠕变→泄漏。\n2. 烟气侧腐蚀：低温区域（省煤器/蒸发器）露点腐蚀，高温区域（过热器）高温氧化。\n3. 热疲劳：频繁启停导致管壁交变热应力，管子与管板焊缝处开裂。\n4. 振动疲劳：烟气横向冲刷管束引起卡门涡街激振，长期导致管子疲劳断裂。\n5. 制造缺陷：管材夹杂、焊缝未熔合等制造遗留问题。",
            "solution": "1. 紧急处置：\n   - 立即降低燃气轮机负荷至最低稳定运行负荷。\n   - 关闭泄漏管束所在回路的给水隔离阀。\n   - 开启紧急放水阀，防止水位过高进入透平。\n   - 监控排烟温度，若超限则停机。\n2. 临时堵管：停炉冷却后，对泄漏管两端安装管塞（堵管率不超过 10% 可继续运行）。\n3. 水压试验：对整台锅炉进行 1.25 倍工作压力的水压试验，检查所有管束。\n4. 管子更换：割除泄漏管段，更换新管并焊接。焊接后进行 100% 射线检测。\n5. 化学清洗：若因结垢导致泄漏，更换管束后需对整个回路进行化学清洗。",
            "prevention": "1. 严格控制给水品质：pH 9.2~9.6、电导率 < 10 μS/cm、溶解氧 < 7 ppb。\n2. 每次检修进行管壁测厚，壁厚减薄超过 30% 的管子预防性更换。\n3. 定期进行给水和炉水化学监督化验。\n4. 优化启停曲线，控制管壁温度变化率 < 2°C/min。\n5. 安装声学泄漏监测系统，实现早期泄漏预警。",
            "updated": "2026-05-05",
            "source": "manual",
            "content_type": "text",
        },
    ],
    "expert_rules": [
        {
            "id": "R001",
            "name": "排气温度超限预警规则",
            "condition": "透平出口温度 T4 > 580°C 且持续 3 个采样周期",
            "conclusion": "燃烧器状态异常或燃气品质变化，可能导致透平叶片过热",
            "confidence": 0.85,
            "severity": "高",
            "related_params": ["透平出口温度_T4", "透平进口温度_T3", "天然气瞬时流量", "排烟含氧量"],
            "recommended_actions": "1. 立即检查 T4 温度分布是否均匀\n2. 对比 T3 温度判断是否燃烧室侧异常\n3. 检查燃料流量和热值是否突变\n4. 若 T4 > 600°C 触发降负荷保护",
        },
        {
            "id": "R002",
            "name": "压气机效率劣化诊断规则",
            "condition": "压气机等熵效率 < 86% 或较基准值下降超过 2 个百分点",
            "conclusion": "叶片积垢或入口滤网堵塞，导致压气机性能下降",
            "confidence": 0.80,
            "severity": "中",
            "related_params": ["压气机进口温度_T1", "压气机进口压力_P1", "压气机出口温度_T2", "压气机出口压力_P2", "空气流量"],
            "recommended_actions": "1. 检查压气机入口滤网压差\n2. 安排在线清洗（50~70% 负荷下执行）\n3. 若在线清洗无效，安排离线清洗\n4. 复核空气过滤器滤芯状态",
        },
        {
            "id": "R003",
            "name": "热耗率偏离设计值规则",
            "condition": "热耗率偏差 > 200 kJ/kWh（偏离设计值 > 2.5%）",
            "conclusion": "综合性能劣化，需逐级分解定位：压气机/燃烧室/透平/余热锅炉",
            "confidence": 0.90,
            "severity": "中",
            "related_params": ["天然气瞬时流量", "天然气低位热值", "发电机有功功率", "透平出口温度_T4"],
            "recommended_actions": "1. 执行逐级分解分析，定位效率损失最大环节\n2. 对比各部件效率与设计值偏差\n3. 检查燃料热值是否有变化\n4. 评估是否需要安排检修",
        },
        {
            "id": "R004",
            "name": "振动超限紧急规则",
            "condition": "振动_轴向 > 7.0 mm/s 或 振动_垂向 > 7.0 mm/s",
            "conclusion": "转子系统异常（不平衡/不对中/轴承故障），需立即处置",
            "confidence": 0.92,
            "severity": "高",
            "related_params": ["振动_轴向", "振动_垂向", "发电机有功功率"],
            "recommended_actions": "1. 振动 > 11 mm/s 立即跳闸停机\n2. 7~11 mm/s 降负荷至 50% 并安排检修\n3. 频谱分析确定振动主导频率\n4. 检查轴承温度和润滑油系统",
        },
        {
            "id": "R005",
            "name": "余热锅炉效率下降规则",
            "condition": "HRB 出口烟温 > 120°C（较设计值升高 20°C 以上）",
            "conclusion": "余热锅炉换热效率下降，可能原因：管束积灰/结垢、给水品质劣化、管束泄漏",
            "confidence": 0.78,
            "severity": "中",
            "related_params": ["HRB进口烟温", "HRB出口烟温", "HRB蒸汽温度", "HRB蒸汽压力", "主蒸汽流量"],
            "recommended_actions": "1. 对比进出口烟温差变化趋势\n2. 检查蒸汽流量是否异常减少\n3. 检查给水品质是否合格\n4. 若怀疑管束泄漏，安排停炉检查",
        },
        {
            "id": "R006",
            "name": "排放超标预警规则",
            "condition": "CO排放 > 15 ppm 或 未燃碳氢 > 8 ppm",
            "conclusion": "燃烧不充分，可能导致燃烧室部件损坏和环保超标",
            "confidence": 0.88,
            "severity": "中",
            "related_params": ["CO排放", "未燃碳氢", "排烟含氧量", "天然气瞬时流量", "透平进口温度_T3"],
            "recommended_actions": "1. 检查排烟含氧量是否异常偏低\n2. 核实燃烧器燃料-空气配比\n3. 检查燃料喷嘴是否堵塞\n4. 评估燃烧器是否需要清洗或更换",
        },
    ],
    "vector_kb_sources": [
        {"id": "V001", "name": "燃机运维向量知识库", "url": "http://192.168.1.200:8001/api/vectors", "embedding_model": "bge-large-zh", "doc_count": 1240, "status": "connected"},
        {"id": "V002", "name": "设备手册知识库", "url": "http://192.168.1.200:8002/api/vectors", "embedding_model": "bge-large-zh", "doc_count": 356, "status": "disconnected"},
    ],
    "causal_graph": {
        "nodes": [
            {"id": "n1", "name": "热耗率偏高", "type": "symptom"},
            {"id": "n2", "name": "压气机效率下降", "type": "subsystem"},
            {"id": "n3", "name": "燃烧效率下降", "type": "subsystem"},
            {"id": "n4", "name": "透平效率下降", "type": "subsystem"},
            {"id": "n5", "name": "叶片积垢", "type": "root_cause"},
            {"id": "n6", "name": "入口滤网堵塞", "type": "root_cause"},
            {"id": "n7", "name": "喷嘴堵塞", "type": "root_cause"},
            {"id": "n8", "name": "叶片磨损", "type": "root_cause"},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "weight": 0.4},
            {"source": "n1", "target": "n3", "weight": 0.3},
            {"source": "n1", "target": "n4", "weight": 0.3},
            {"source": "n2", "target": "n5", "weight": 0.6},
            {"source": "n2", "target": "n6", "weight": 0.4},
            {"source": "n3", "target": "n7", "weight": 0.7},
            {"source": "n4", "target": "n8", "weight": 0.8},
        ],
    },
}


@router.get("/models")
async def get_models():
    """获取已注册的小模型 API 列表。"""
    return {"models": MODEL_APIS, "total": len(MODEL_APIS)}


@router.post("/models")
async def register_model():
    """注册新的小模型 API。"""
    return {"success": True, "message": "模型注册成功"}


@router.get("/models/{model_id}/health")
async def check_model_health(model_id: str):
    """检查小模型 API 健康状态。"""
    model = next((m for m in MODEL_APIS if m["id"] == model_id), None)
    if model is None:
        return {"error": "模型不存在"}
    return {"id": model_id, "status": model["status"], "last_check": model["last_check"]}


@router.post("/models/{model_id}/test")
async def test_model_connection(model_id: str):
    """联通测试 — 向模型 API 发送探测请求，返回连通性和延迟。"""
    model = next((m for m in MODEL_APIS if m["id"] == model_id), None)
    if model is None:
        return {"success": False, "error": "模型不存在"}

    url = model["url"]
    method = model.get("method", "POST").upper()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            import time
            start = time.monotonic()
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json={}, timeout=5.0)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

        is_success = 200 <= resp.status_code < 300
        model["status"] = "online" if is_success else "offline"
        model["last_check"] = now_str
        return {
            "success": is_success,
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "last_check": now_str,
            "message": "联通成功" if is_success else f"返回状态码 {resp.status_code}",
        }
    except httpx.ConnectError:
        model["status"] = "offline"
        model["last_check"] = now_str
        return {"success": False, "error": "连接失败，目标服务不可达", "last_check": now_str}
    except httpx.TimeoutException:
        model["status"] = "offline"
        model["last_check"] = now_str
        return {"success": False, "error": "连接超时（5s）", "last_check": now_str}
    except Exception as e:
        model["status"] = "offline"
        model["last_check"] = now_str
        return {"success": False, "error": str(e), "last_check": now_str}


@router.get("/knowledge/maintenance")
async def get_maintenance_knowledge(category: str = None):
    """获取检维修知识条目。"""
    items = KNOWLEDGE_BASE["maintenance"]
    if category:
        items = [k for k in items if k["category"] == category]
    return {"items": items, "total": len(items)}


@router.post("/knowledge/maintenance")
async def add_maintenance_knowledge(
    title: str = Form(...),
    category: str = Form(...),
    type: str = Form(...),
    keywords: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """添加检维修知识条目（支持文本 + 文件上传）。"""
    import os
    new_id = f"K{str(len(KNOWLEDGE_BASE['maintenance']) + 1).zfill(3)}"
    content_type = "text"
    file_info = ""
    if file and file.filename:
        content_type = "document"
        file_info = f" (附件: {file.filename})"

    entry = {
        "id": new_id,
        "title": title + file_info,
        "category": category,
        "type": type,
        "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "source": "upload" if file else "manual",
        "content_type": content_type,
    }
    KNOWLEDGE_BASE["maintenance"].append(entry)
    return {"success": True, "id": new_id, "message": "知识条目已添加"}


@router.get("/knowledge/rules")
async def get_expert_rules():
    """获取专家规则条目。"""
    return {"rules": KNOWLEDGE_BASE["expert_rules"], "total": len(KNOWLEDGE_BASE["expert_rules"])}


@router.get("/knowledge/vector-sources")
async def get_vector_kb_sources():
    """获取已接入的外部向量知识库列表。"""
    return {"sources": KNOWLEDGE_BASE["vector_kb_sources"], "total": len(KNOWLEDGE_BASE["vector_kb_sources"])}


@router.post("/knowledge/vector-sources")
async def add_vector_kb_source(body: dict):
    """接入新的外部向量知识库。"""
    new_id = f"V{str(len(KNOWLEDGE_BASE['vector_kb_sources']) + 1).zfill(3)}"
    entry = {
        "id": new_id,
        "name": body.get("name", ""),
        "url": body.get("url", ""),
        "embedding_model": body.get("embedding_model", "bge-large-zh"),
        "doc_count": 0,
        "status": "disconnected",
    }
    KNOWLEDGE_BASE["vector_kb_sources"].append(entry)
    return {"success": True, "id": new_id, "message": "向量知识库已接入"}


@router.post("/knowledge/vector-sources/{source_id}/test")
async def test_vector_kb_connection(source_id: str):
    """测试向量知识库联通性。"""
    source = next((s for s in KNOWLEDGE_BASE["vector_kb_sources"] if s["id"] == source_id), None)
    if source is None:
        return {"success": False, "error": "向量知识库不存在"}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            import time
            start = time.monotonic()
            resp = await client.get(source["url"], timeout=5.0)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

        is_success = 200 <= resp.status_code < 300
        source["status"] = "connected" if is_success else "disconnected"
        return {
            "success": is_success,
            "latency_ms": latency_ms,
            "status": source["status"],
            "last_check": now_str,
            "message": "联通成功" if is_success else f"返回状态码 {resp.status_code}",
        }
    except Exception as e:
        source["status"] = "disconnected"
        return {"success": False, "error": str(e), "status": "disconnected", "last_check": now_str}


@router.get("/knowledge/causal-graph")
async def get_causal_graph():
    """获取因果图定义。"""
    return KNOWLEDGE_BASE["causal_graph"]
