# 模拟补充说明 / Simulation disclosure

原始充电记录、清洗后的充电时长、电量、电池温度和账单均来自用户提供的文件。仅为展示题目要求的日期筛选、时期对比、电网/太阳能曲线和相关性热图，新增模拟字段；这些字段不是校园实测数据。

| 字段 | 自定义规则 |
|---|---|
| session_start | 演示期间为 2026-09-01 至 2026-09-14；会话 ID 稳定分配日期，保留原有开始小时，分钟设为 00 |
| ambient_temperature_c | 日周期 29±4°C 加小幅随机扰动，范围限制在 23–36°C |
| solar_generation_kw | 06–18 点正弦日照曲线，峰值上限 120 kW，每日云量系数 0.55–1；夜间为 0 |
| grid_load_kw | 虚拟校园净电网输入：基础 220 kW，加工作日/晚间/温度情景项，减太阳能，添加扰动，最低 50 kW |
| hub_id | 虚构站点 DEMO_CAMPUS，仅用于统一遥测去重，与销售站点无对应关系 |

固定种子 72604。同一时刻共享同一组遥测值，不按充电会话重复累计负荷。未涉及的小时不填零；图表只显示所选会话关联的观测。未给电池 SoC 生成数据，因为该字段不是本次四项补充需求。

所有原有列保持不变，模拟字段带 `supplement_origin` 和 `simulated_fields` 标记。CSV、页面和导出图表均标注模拟属性。相关系数受生成规则影响，日期分组和增长值受模拟日期影响，不能作为真实校园的实证结论。

默认打开 Complete demonstration mode；取消勾选可查看仅使用原附件的版本。独立补充版位于 `results/demonstration/`。运行 `python run_pipeline.py` 可复现所有结果，`python simulate_missing.py` 可单独生成补充版。

## 可用于报告的方法说明（英文）

The supplied cleaned dataset contains 1,200 charging sessions but does not include calendar dates, ambient temperature, grid load or solar generation. For software demonstration, these fields were generated using a reproducible scenario with a fixed seed of 72604. Original session attributes and billable amounts were preserved. A fictional site identifier was added to support hourly telemetry aggregation. All supplementary fields are explicitly labelled as simulated. The resulting time comparisons and correlations demonstrate application functionality and are not evidence of measured campus conditions. Use of this supplemented dataset for assessment is subject to the instructor's requirements.
