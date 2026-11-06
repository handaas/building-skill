# 报告输出 — 楼宇大数据报告

本文件规定 `building-report` skill 产出的报告结构、质量底线与渲染工作流。所有产物遵循 `AGENTS.md` 的统一 JSON 骨架与本 skill 的领域裁剪。

## 默认展示模式

- HTML：可分享 / 可交付的可视化报告；独立本地文件，内嵌 CSS，无调试 / 内部段落。
- Markdown：知识库 / wiki / PRD / 后续手工编辑。
- JSON：系统集成或二次处理。

`compose_report.py` 通过 `--report-output <path>` 同时产出 HTML + Markdown；`--output <path>` 产出 JSON。`render_report.py` 可基于已有 JSON 重渲染。

## 报告结构（7 章）

1. **报告摘要**：分析对象、数据覆盖范围、核心发现、关键指标卡。
2. **查询对象与口径**：企业全称、匹配方式、数据范围、产品、局限。
3. **数据总览**：办公地址总数、覆盖城市数、明确楼宇 ID 关联数或独立筛选楼宇命中量等指标卡；零命中不包装为库存指标。
4. **核心分析**（楼宇专属子章节，由 `core_analysis.sections` 驱动渲染）：
   - 办公地址详情（表：办公地址 / 所在楼宇 / 入驻方式 / 地址来源）。
   - 办公地址统计（表：城市 / 办公地址数量）。
   - 关联楼宇明细仅使用办公地址产品明确返回的 `estateId` 查询详情；仅有同名楼宇时不建立企业关联。独立地区/类型楼宇筛选必须标明与企业关联无关。
5. **代表性记录**：关键办公地址 Top N（地址 / 楼宇 / 入驻方式）。
6. **特征与洞察**：结构化解读（办公地址规模 / 城市分布广度 / 楼宇库存参考），每条含 `feature` / `evidence` / `interpretation`。
7. **数据口径与来源**：MCP server、数据产品、生成时间、是否 dry-run。

## 质量底线

- 报告脱离 Skill 上下文也可独立阅读；正文只见楼宇/办公地址事实与结构化数据。
- 绝不出现工具名、入参（如 `matchKeyword=...`）、product_id、内部字段名、空表、调试信息。
- HTML 采用研究报告视觉风格：A4 风、灰色顶部条纹、蓝色报告横幅、左侧目录 / 范围侧栏、深蓝章节标题、深蓝表头、浅蓝斑马行、打印友好分页。
- 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。
- 绝不打印 `secret_id` / `secret_key` / 签名 / token / 原始签名请求。
- 自动补全企业全称时，在报告口径中说明“由关键词模糊查询补全”。

### 数据格式约束（铁律）

以下约束适用于 compose_report.py 组装数据与 render_report.py 渲染输出的全过程：

1. **嵌套 JSON 字符串必须解析**：MCP 返回的某些字段（如 `regCapital`、`addressValue`、`subscriptionDetail`）可能是 JSON 字符串（例：`{"coinType":"人民币","value":430000000.0}`）。compose 层必须调用 `_unwrap_json_str()` / `_parse_reg_capital()` / `_flatten_addr()` 解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市滨江区..."）。绝不在报告正文、表格单元格或指标值中输出原始 JSON 字符串。

2. **section 标题必须用中文**：`core_analysis.sections` 数组中每个 section 的 `title` 字段必须使用中文（如"企业基本信息"、"对外投资"、"股东信息"）。`key` 字段用英文 snake_case 供程序索引，但 `title` 绝不可显示英文 key。即使缺少 sections 数组，渲染器回退逻辑也内置了 `_TITLE_MAP` 映射。

3. **指标值可读化**：所有 `metrics` 的 `value` 字段必须格式化为人类可读形式：
   - 金额：`10995210218.0` → `109.95 亿 人民币`（≥1 亿用亿，≥1 万用万）
   - 地址：嵌套 dict → 省+市+区拼接 或取 `value` 字段
   - 比率：`0.8858` → `88.58%`
   - 日期：保持 `yyyy-MM-dd` 格式
   - "-" 表示字段缺失（MCP 未返回）；`0` 表示真实为零

4. **企业画像指标提取**：有 fuzzy_search 的 skill 必须从返回的 record 中提取 `regCapitalValue` / `foundTime` / `operStatus` / `enterpriseType` / `legalRepresentative`，通过 `_enrich_metrics_with_profile()` 追加为指标卡。

5. **分布派生指标**：`_derive_core_metrics()` 从 core_analysis 各 section 计算分布指标（CR3 集中度、覆盖城市/平台/类目数、价格区间、正面占比等），确保指标总数 M ≥ 6。

## 内容口径与 AI 整理

- **三种口径分离**：筛选后的办公地址明细、全国城市统计、独立楼宇查询不可交叉计算；筛选明细的 total 不是企业全国总数。
- **办公计数口径跟随地区筛选**：只有 `address` 地区筛选会把办公地址计数改为“筛选地区”口径；仅按楼宇类型（`property_type`）做独立市场检索时，办公地址总数仍是企业全量，独立楼宇查询“不代表与查询企业关联”的提示保持不变。
- **地址是线索**：保留地址来源（工商登记/办公地址/招聘信息）与入驻方式；不推断所有权、租赁、实际办公或人员规模。
- **楼宇查询独立**：`关联依据` 为 `-` 时不得写成企业关联楼宇；命中总量与展示条数分开，均值只描述展示样本。
- **不自证**：按楼宇类型筛选后，“该类型占比 100%”是筛选条件，不是结构结论；单一类型时省略类型洞察。
- **缺失与重复**：`-` 是上游未返回，不是 0；代表性记录与明细重复只是展示子集，不增加证据。
- **内容整理**：正常 `build_payload` 与 `--dry-run` 样例生成在写盘前自动调用 `apply_content_review(report)`；对既有 JSON 也可离线调用同一函数，只重标口径与样本文案、抑制自证结论，不查询 MCP、不改原始记录。离线修订件写 `output/content-quality-review/<case>/`。

## 工作流

```bash
# 1. 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --dry-run \
  --output output/building.json \
  --report-output output/building.html

# 2. 真实查询 + 渲染（需 MCP 连接就绪）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --output output/building.json \
  --report-output output/building.html

# 3. 按地区 + 楼宇类型筛选
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --address "广东省,广州市" \
  --property-type 写字楼 \
  --report-output output/building_gz_office.html

# 4. 重渲染已有 JSON
python scripts/render_report.py --input output/building.json --output output/building.html
python scripts/render_report.py --input output/building.json --output output/building.md
```

返回：JSON 路径、HTML 路径、Markdown 路径，以及企业全称映射与数据口径摘要。
