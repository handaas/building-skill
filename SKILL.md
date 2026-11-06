---
name: building-report
description: Use for generating a professional building / office-address big-data report (楼宇大数据报告) from the HandaaS building MCP — covering 企业办公地址详情、办公地址分布统计、楼宇查询明细（写字楼/产业园/综合体/公寓酒店/展会中心）. Trigger when users ask for “楼宇大数据报告”, “办公地址分析”, “查一家公司的办公地址”, “办公地址统计”, “楼宇查询”, “写字楼入驻分析”, or “企业办公网络画像”. Infer the canonical enterprise name (auto-fuzzy-completing a keyword), pick the right MCP tools, and produce HTML + Markdown + JSON reports automatically. MCP 服务名称触发词：楼宇资产信息。
---

# 楼宇大数据报告

## 用户契约

把“楼宇大数据报告”作为面向用户的调用短语。`building-report` 仅为内部包名。

当本 skill 处于激活状态：

1. 不要向用户索要 product_id、MCP 工具名、API 字段、内部参数或凭证信息；只接受企业名称、统一社会信用代码、注册号或企业 ID。
2. 接受自然目标，例如“查一下某某公司的办公地址”“分析这家企业的办公网络”“给我一份某某公司的楼宇报告”“看看这个区域的写字楼入驻情况”。
3. 当用户只给关键词时，自动调用关键词模糊查询补全企业全称，再查办公地址/楼宇详情。
4. 优先使用 MCP 连接（`BUILDING_MCP_URL` Remote MCP 或本地 `handaas-mcp-server/building-mcp-server`）；不要让用户处理签名或凭证。
5. 同时产出 HTML（可分享交付）、Markdown（知识库 / wiki）、JSON（系统集成）三类产物。
6. 报告正文必须是专业研究报告风格：只见楼宇/办公地址事实与结构化数据，绝不出现工具名、入参、product_id、内部字段或空表。
7. 绝不打印 `secret_id`、`secret_key`、签名、token 或原始签名请求。
8. 默认 dry-run；真实付费 / 凭证调用需用户明确要求且 MCP 连接配置完整。
9. 数据为空时明确说明数据范围 / 口径，不渲染空表、不臆造事实。


- MCP 返回的嵌套 JSON 字符串（如金额 `{"coinType":"人民币","value":430000000.0}`、地址 `{"city":"杭州市",...}`）必须解析为可读文本（如"4.30 亿 人民币"、"浙江省杭州市"），绝不在报告正文、表格或指标中输出原始 JSON 字符串。
- 报告所有章节标题、指标卡标签必须用中文；`core_analysis.sections` 的 `title` 字段必须中文，不可显示英文 key（如 `holders`、`investments`）。
- 指标值必须可读化：金额格式为"X 亿/万 + 币种"，地址拼接省市区，比率显示百分号。详见 `references/report-output.md` 的「数据格式约束」。

## 付费调用纪律（先规划后查询）

每次真实调用均按接口/页计费，必须先规划再查询，不得默认全量拉取：

1. 每一次业务/工具调用、每一页都可能收费。想算 total / 页数不是无限制取全量的授权。
2. 调用前先推导：需要哪些结论、需要哪些数据维度、工具与参数计划、必要页数与最大调用预算。total 未知时，第一个必要的明细页同时完成 total 发现并直接作为报告数据，绝不为此多付一次（首屏响应必须复用，不重复拉取）。
3. 优先用统计 / 画像 / 聚合接口回答能回答的问题（办公地址统计、模糊查询企业画像优先）；明细接口仅取结论、图表、代表性记录或用户明确的全量/计数需求所需的行数。只有用户明确要全面报告时才跑全面管线，绝不因为工具存在就全部调用。
4. 在 schema 允许范围内用合理的大 pageSize（≤10，办公地址详情与楼宇查询的接口上限），取得所需证据 / 样本即停，且不超出显式预算。更多调用必须有“缺失结论”的正当理由，不能只为填满章节。不得用样本分布冒充全量结论。
5. 复用当前任务 / 报告内的相同请求（含首屏规划数据）；不要为渲染重跑 compose/MCP，用已保存 JSON 本地重渲染。不自动重试、不重复拉取同一统计或明细、不并行独立拉取相同数据。任何补充查询必须先列缺口并复用已返回记录。
6. `total_pages` / `remaining_pages` 是按请求 pageSize 的估算；短而非空页面仍有剩余记录时在预算内继续。只有稳定有效的 total 等于实际扫描条数才算完整采集；错误、提前空页、重复页、total 变化/缺失、数量溢出均视为不完整。显式预算 / 样本停止即部分采集，绝不宣称全量。
7. 预算不足以支撑用户要求的关键结论时：先说明证据缺口与预计需要追加的调用数，再请求扩大授权（提高 `--max-pages`）；不静默降级结论，也不擅自扩大计费范围。

分页收集默认每次明细调用预算 `--max-pages 1`（每明细接口）；明细接口的 total、实际取数、完整性披露写入报告 `data_source.pagination`，报告级去重统计写入 `data_source.call_usage`.

**楼宇基本信息 ID 关联**：当未指定 `--address` / `--property-type` 时，报告从办公地址明细页中提取明确的楼宇 ID（estateId），按 ID 调用 `building_bigdata_building_basic_info`（非分页，每 ID 一次业务调用，ID 数量 = 当前页明细内去重的 estateId 数量）；这些调用同样纳入 `call_usage` 计数。计划时需估算当前页楼宇去重数量，不因“补充基本信息”自动扩大至所有 estateId；仅取本报告结论、图表和代表性记录所需的楼宇字段。

## MCP 服务入口

- MCP 服务当前名称：楼宇资产信息（连接仍使用原服务目录标识）。

- 上游 MCP 项目：`handaas-mcp-server/building-mcp-server`（位于 `HANDAAS_MCP_SERVER_ROOT` 或本仓库同级目录）。
- Remote MCP：设置环境变量 `BUILDING_MCP_URL`（streamable-http），可选 `BUILDING_MCP_TOKEN`。
- 本地 MCP：设置 `HANDAAS_MCP_SERVER_ROOT` 指向 `handaas-mcp-server` 仓库根目录；该 server 自己的 `.env` 提供 `INTEGRATOR_ID` / `SECRET_ID` / `SECRET_KEY`。
- 首次真实查询前，运行 `scripts/mcp_client.py ping` 与 `scripts/mcp_client.py list-tools` 验证连通。

## 按需加载 references

- 不清楚该 MCP 有哪些工具、参数、返回字段、何时调用：`references/mcp-tools-reference.md`。
- 报告结构、章节、质量底线、渲染工作流：`references/report-output.md`。

## 意图路由

| 用户意图 | 内部工作流 |
| --- | --- |
| 查一家公司的全维度楼宇/办公地址报告 | 调办公地址详情 + 办公地址统计 + 楼宇查询组装全量报告；`compose_report.py --enterprise ...` |
| 只要办公地址统计 / 楼宇查询 | 仅调对应工具，按统一骨架组装 |
| 按地区筛选办公地址 / 楼宇 | `compose_report.py --address "广东省,广州市"` |
| 按楼宇类型筛选（写字楼/产业园/综合体/公寓酒店/展会中心） | `compose_report.py --property-type 写字楼` |
| 只给关键词（不是全称） | 先 `building_bigdata_fuzzy_search` 补全全称，再查详情 |
| 只要 JSON / 只要 HTML / 只要 Markdown | 用 `--output`（JSON）或 `--report-output`（HTML+MD），或 `render_report.py` 重渲染 |
| 连接 / 工具不存在 / 传参错误 | `mcp_client.py ping` / `list-tools` 排查；报脱敏后的缺失项 |

## Golden path for 楼宇大数据报告

1. **解析企业全称**：若输入含“公司/集团/有限/院/厂/中心/事务所/合作社/合伙”等后缀视为全称；否则调 `building_bigdata_fuzzy_search` 取首个命中。
2. **调用楼宇工具**：`building_bigdata_office_address_details`（办公地址详情：地址/楼宇/入驻方式/来源，分页，默认 1 页预算）、`building_bigdata_office_address_stats`（按城市统计）、`building_bigdata_building_query`（按地区/类型/关键词检索楼盘，分页，默认 1 页预算）。企业主体工具入参为 `matchKeyword`（企业全称）+ `keywordType`；明细按 total 驱动、在 `--max-pages`（默认 1）预算内翻页，超出预算时报告披露未纳入条数而非宣称全量。
3. **组装统一报告**：核心分析含办公地址详情（表）、办公地址统计（表）、楼宇查询明细（表）。
4. **渲染三件套**：`compose_report.py --enterprise ... --output ... --report-output ...` 直接产出 JSON + HTML + Markdown；或 `render_report.py --input ... --output ...` 重渲染。
5. **返回路径**：返回 JSON、HTML、Markdown 文件路径，以及企业全称映射与数据口径。

## 内容整理与交付审校

1. **先分清三个口径**：企业办公地址明细（可被地区筛选）、企业办公地址城市统计（全国口径）、独立楼宇查询（市场筛选，不绑定企业）。三者不能相加、相除或互相证明。
2. **筛选明细不是企业总数**：传了 `--address` 时，明细 total 只能写“筛选地区办公地址数”；省份数写“筛选地区覆盖省份数”。不得用筛选后的 8 条推导企业全国布局，也不得与全国统计的 255 条比较占比。
3. **地址线索不是占用**：办公地址可能来自工商登记、办公地址库或招聘信息；同一地址可能只是注册地/招聘露出。保留“地址来源”和“入驻方式”，不推断所有权、租赁、实际办公或人员规模。
4. **楼宇查询不是关联**：`building_query` 是独立地区/类型筛选，`关联依据` 为空即与企业无关；不得写成“企业旗下/入驻楼宇”或“招商资源”。命中总量与展示条数分开写，均值只描述展示样本。
5. **不要自证**：查询已按楼宇类型筛选时，“写字楼占比 100%”是筛选条件本身，不是结构发现；单一类型时不生成类型结构结论。
6. **重复与缺失**：同一办公地址/楼宇在明细与代表性记录中重复出现时，代表性记录只是展示子集，不增加证据；`-` 是上游未返回，不是 0，也不代表企业没有该地址。
7. **内容整理（正常生成 + 离线修订）**：正常 `build_payload` 与 `--dry-run` 样例生成在写 JSON/HTML/MD 前自动调用 `apply_content_review(report)`；同一函数也可基于已有 JSON 重标口径、重算样本文案、抑制自证结论，不调用 MCP、不改原始记录。离线修订件写 `output/content-quality-review/<case>/`。

```bash
python - <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import compose_report as cr
src = Path("examples/03-guangzhou-office-filter/report.json")
raw = src.read_bytes()
report = cr.apply_content_review(json.loads(raw), source_sha256=hashlib.sha256(raw).hexdigest())
out = Path("output/content-quality-review/03-guangzhou-office-filter")
out.mkdir(parents=True, exist_ok=True)
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
PY
```

- **渲染前置检查**：执行会产出含图表 HTML / PDF 的报告命令前，先验证 `node --version` 与本 skill 自带 `assets/vendor/echarts.min.js` 存在；内嵌静态 SVG 的生成需要 Node.js（推荐当前 LTS，无需 npm 包），缺失时报告生成明确报错。查看已生成的 HTML 与 Markdown 输出不需要 Node。

## 脚本速查

```bash
# 校验连接配置（脱敏）
python scripts/validate_config.py --allow-placeholders

# 连通性自测
python scripts/mcp_client.py ping
python scripts/mcp_client.py list-tools

# 干跑（不调真实 API，用样例数据组装报告骨架）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --dry-run \
  --output output/building.json \
  --report-output output/building.html

# 真实查询 + 渲染（需 MCP 连接就绪）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --output output/building.json \
  --report-output output/building.html

# 按地区 + 楼宇类型筛选
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --address "广东省,广州市" \
  --property-type 写字楼 \
  --report-output output/building_gz_office.html

# 按地区 + 楼宇类型筛选（明细翻页预算提升到 3 页）
python scripts/compose_report.py \
  --enterprise "示例科技有限公司" \
  --address "广东省,广州市" \
  --property-type 写字楼 \
  --max-pages 3 \
  --report-output output/building_gz_office.html

# 手动调单个工具
python scripts/mcp_client.py call-tool \
  --tool building_bigdata_office_address_stats \
  --arguments-json '{"matchKeyword": "示例科技有限公司", "keywordType": "name"}'

# 重渲染已有 JSON
python scripts/render_report.py --input output/building.json --output output/building.html
python scripts/render_report.py --input output/building.json --output output/building.md
```

## 输出字段

- `subject`：企业全称、匹配关键词、主体类型、是否自动补全。
- `abstract` / `summary`：封面摘要与详细摘要。
- `metrics`：办公地址总数（或筛选地区办公地址数）、覆盖城市数/筛选地区覆盖省份数、CR3城市集中度（或全国统计CR3）、明确ID关联楼宇数/筛选楼宇命中量。
- `caliber`：匹配对象、匹配方式、数据范围、产品、局限。
- `core_analysis`：办公地址详情（表）、办公地址统计（表）、楼宇查询明细（表）。
- `representative_records`：代表性办公地址（地址 / 楼宇 / 入驻方式）。
- `insights`：结构化解读（办公地址规模 / 城市分布广度 / 楼宇库存参考）。
- `data_source`：MCP server、数据产品、生成时间、是否 dry-run；分页接口的 pagination（每接口上游 total / 请求页数 / 取得条数 / 未纳入条数 / 完整性与停止原因）与 call_usage（本报告实际执行与复用的请求数）。

若 API 调用失败，明确报出缺失的配置 / 缺失的工具 / MCP 错误 / 参数校验错误 / 上游网络错误，给出 dry-run 命令或配置步骤，绝不暴露密钥。
