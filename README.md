# 校园能源与电动车充电管理程序

对应 ITS72604 Final Examination 的 **Section A 代码示例和 Section B 程序功能**。Python 代码含中文注释；网页和图表采用英文标签，便于报告截图。当前是可本地运行、经过测试的课程项目，不是已获生产部署认证的系统。

## 先运行

在 PyCharm 打开本目录，解释器选择 `.venv/bin/python`。本机环境基于已有 Anaconda Python 3.13，复用其已安装库，没有修改全局依赖。

右上角运行配置：

1. **01 数据清洗与图表**：运行 `run_pipeline.py`，输出清洗 CSV、质量审计和图表。
2. **02 启动能源仪表盘**：启动 Streamlit；访问 http://127.0.0.1:8512 。若端口已被预览占用，直接使用已打开的网页，或先停止旧进程。

也可在 PyCharm 的终端执行：

```bash
.venv/bin/python section_a.py
.venv/bin/python run_pipeline.py
.venv/bin/python -m streamlit run app.py --server.port 8512
.venv/bin/python -m unittest discover -s tests -v
```

复制到其他电脑后，创建新的虚拟环境，不要复制本机 `.venv`：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py
python -m streamlit run app.py
```

不要直接以 `python app.py` 代替 Streamlit 启动。`requirements.txt` 固定的是本机已验证版本。

## 完整演示模式（本次新增）

根据用户要求，默认开启 **Complete demonstration mode**，以独立生成的日期、环境温度、电网负荷、太阳能输出及虚构站点补充缺项，五类图表和日期筛选可运行。原有充电值与账单不变。页面、CSV 和导出图表都保留模拟标记；时间变化与模拟字段相关性不作为实测结论。取消勾选可返回原附件模式。

生成规则和英文报告说明见 `SIMULATION_NOTES.md`；补充数据及完整图表在 `results/demonstration/`。原始模式的审计与图表仍保留在 `results/`。是否允许模拟数据正式提交，应以老师要求为准。

## 三份附件的用途（已接入）

| 附件 | 行数 | 用途 |
|---|---:|---|
| `ev_campus_dataset.csv` | 1,200 | 原始充电会话，复现清洗并核对 |
| `data/cleaned_energy_sales_data.csv` | 1,200 | 用户提供的已清理参考数据；默认仪表盘保留其账单原值 |
| `data/sales_data.csv` | 500 | 独立销售探索页面，不与充电会话强行合并 |

下载目录的三个原文件均未改动。旧模拟数据移至 `examples/synthetic_ev_sessions.csv`，不再作为默认来源。

原始充电数据中 25 个时长缺失值用中位数 97 分钟填补；35 个电量缺失值用 13.28 kWh 填补。逐会话核对原始清洗结果与参考文件，结果输出到 `results/source_reconciliation.csv`。代码统一内部字段名，参考文件原样保留在 `data/`。

收费规则是从已清理附件推导并逐行验证的复现规则，不代表独立确认的学校价目表：

- AC 每小时 RM6，DC 每小时 RM15，基础费 = 时长/60 × 小时单价。
- 开始小时为 12 至 17（含 17）时，加收基础费的 25%。
- 超时前 15 分钟免费，超过部分每分钟 RM0.50。
- 净账单 = 基础费 + 高峰费 + 超时费；最终金额按附件的 Pandas/NumPy 两位小数舍入规则复现。
- 功率 = 电量/小时；碳减排 = 电量 × 0.475，附件碳减排值保留两位小数。
- Section A 的 15% 风险附加费是独立演算，结果列为 `scenario_risk_surcharge`，不重复加进用户提供的账单。温度滑块只改变告警。

## 数据缺项与题目覆盖

原附件目前只有上述三个文件；下述限制适用于关闭模拟补充时的原始模式。充电数据只有 `Start_Hour`，没有日期、站点、环境温度、电网负荷、太阳能发电量或电池 SoC。因此：

- 充电页使用开始小时、电量及 AC/DC 筛选；日期筛选和前期 KPI 差值不可用。
- 电网与太阳能曲线、环境温度/时长/电网负荷热图显示缺项原因。不能把 `Grid_Status_Label` 当成 kW，也不能把电池温度当成环境温度。
- 已实现可计算的小时收入柱图、用户费用箱线图、电池温度与电量散点及趋势线。
- 销售数据自身的 `Transaction_Date` 只用于销售页日期筛选，不能用来填充充电日期。
- 未来上传含 `session_start`、`hub_id`、`ambient_temperature_c`、`grid_load_kw`、`solar_generation_kw` 等完整扩展字段的文件时，原有遥测图和日期功能仍可用。扩展演示路径使用 `config.py` 的演示收费规则，与课程附件规则分开。

销售探索保留原始 15 个未知销量和 20 个缺失收入；仅在销量、单价均存在时重建缺失收入，另存 `Analysis_Revenue_MYR` 和重建标记。不能恢复的收入保持为空，统计明确标为“已知/可恢复收入”。页面包含日期和站点筛选、类别收入、每日收入、站点收入、数据及 CSV 下载。

## 代码入口

- `course_data.py`：实际附件字段适配、清洗、收费复现、逐 ID 对账和销售探索准备。
- `pipeline.py`：自动识别课程格式或扩展遥测格式，校验并导出。
- `run_pipeline.py`：生成清洗结果、对账表、销售探索文件和图表。
- `app.py` / `views/`：四个页面，充电分析、风险告警、下载、销售探索。
- `section_a.py`：NumPy / Pandas 示例及 filter → map → reduce 风险附加费演算。
- `visualizations.py`：绘图和缺项提示。

## Section A 的理解要点

NumPy 的同类型数组适合数值矩阵操作，底层向量化计算减少逐元素 Python 解释器开销；二维切片通常创建视图，布尔索引则会分配新数组。Pandas 在数值数组之上增加列标签、索引、分组与缺失值语义，适合表达“按充电桩统计收入”等业务逻辑。两者结合时，Pandas 负责表结构与清洗，NumPy/向量化表达式负责批量计算；并非所有向量化操作都零拷贝，巨大临时数组仍需关注内存。

`filter()` 和 `map()` 惰性地产生记录，`reduce()` 只保留累计值，因此中间处理不需要再复制完整列表。若输入本身已经是列表，输入列表的内存仍然存在；只有展示全部处理记录时才用 `list()`。筛选 lambda 是只读谓词，累计 lambda 不修改输入；金额转换放在命名函数里便于独立测试。

Matplotlib 适合精确控制坐标轴、并列柱宽、图例和导出尺寸；Seaborn 在其基础上提供按类别绘制箱线图、回归图及热图的更高层接口。AC/DC 使用固定且色盲友好的两种颜色；金额和时间单位明确；Pearson 热图固定为 -1 至 1，以零为中心，数值注释避免依赖颜色猜读。三联图分别回答峰值负荷、费用离散性与温度关系，减少管理者跨图搜索信息的负担。趋势线和相关系数都不能证明因果关系；样本不足或变量恒定时不勉强画出趋势。

## 输出与验证

`results/` 包含清洗后的充电数据、拒收记录、清洗审计、原始/参考文件核对表、两组 PNG/PDF 图表、销售探索 CSV、销售质量报告和分类收入表。图表中不可计算的面板明确标注缺失字段。

测试覆盖收费边界、中位数插补、参考文件账单保持不变、全部 1,200 条会话对账、日期与小时筛选、缺项图表、告警、销售空筛选及导出。执行记录见 `tests_run.log` 和 `results_run.log`。

## 正式提交尚需你完成

题目另要求不超过 20 页的 `StudentName_FE.pdf`，含封面、Section A 理论答案、Section B 说明、代码摘录/清单、真实运行截图、图表、APA 参考文献、GitHub URL 和视频演示 URL。本项目没有代替你的报告，也没有上传、发布或提交到学校。请理解和验证代码，再录制演示与整理报告。代码附中文注释便于学习，不保证查重或 AI 指标。

建议演示顺序：运行 A 的示例 → 运行数据管道 → 查看审计与图表 → 打开网页 → 修改小时/充电桩/电量 → 调整温度查看告警 → 预览并下载过滤 CSV。演示中明确附件缺项及销售数据与充电数据各自的统计口径。

## 官方技术资料

- Streamlit 多页面：[st.Page 与 st.navigation](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- Streamlit 测试：[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
- Pandas 时间聚合：[Resampling](https://pandas.pydata.org/docs/reference/resampling.html)

代码由 AI 辅助编写；报告中的工具声明应如实描述使用范围，不应将本 README 原样当成个人考试论述。
