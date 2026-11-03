# 地产集团办公网络

- 用户需求：请分析万科企业股份有限公司的办公地址分布和关联楼宇。
- 决策用途：集团办公网络与区域覆盖判断
- 本轮结果：**本轮检查通过**
- 实际工具调用：13；失败 0
- 章节覆盖率：100%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 办公地址详情和城市统计互相可核对
- 关联楼宇仅使用 MCP 返回的 estateId 去重
- 入驻方式与来源字段保持原值语义
- 不把办公地址解释为资产所有权

## 本轮自动检查发现


## 使用局限

- 办公地址不代表物业所有权或实际持续办公
- 关联楼宇取决于地址数据中的楼宇名称

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 building-skill/scripts/compose_report.py --enterprise '万科企业股份有限公司' --page-size 10 --output building-skill/output/01-developer-office-network/report.json --report-output building-skill/output/01-developer-office-network/report.html
```

## 逐场景业务复核

当前真实产物逐项复核通过；结论限于本次上游公开样本与报告声明口径。

- **pass** 办公地址详情和城市统计互相可核对：已证明“办公地址详情和城市统计互相可核对”。 当前事实={"technical_status":"passed","successful_data_calls":13,"calls":[{"tool":"building_bigdata_fuzzy_search","status":"data","row_count":1,"reported_total":198,"arguments":{"matchKeyword":"万科企业股份有限公司","pageSize":1}},{"tool":"building_bigdata_office_address_details","status":"data","row_count":10,"reported_total":13,"arguments":{"matchKeyword":"万科企业股份有限公司","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"building_bigdata_office_address_stats","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"万科企业股份有限公司","keywordType":"name"}},{"tool":"building_bigdata_building_basic_info","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"407aa79540860faa"…
- **pass** 关联楼宇仅使用 MCP 返回的 estateId 去重：已证明“关联楼宇仅使用 MCP 返回的 estateId 去重”。 实际调用=[{"tool":"building_bigdata_fuzzy_search","status":"data","row_count":1,"reported_total":198,"arguments":{"matchKeyword":"万科企业股份有限公司","pageSize":1}},{"tool":"building_bigdata_office_address_details","status":"data","row_count":10,"reported_total":13,"arguments":{"matchKeyword":"万科企业股份有限公司","keywordType":"name","pageIndex":1,"pageSize":10}},{"tool":"building_bigdata_office_address_stats","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"万科企业股份有限公司","keywordType":"name"}},{"tool":"building_bigdata_building_basic_info","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"407aa79540860faa"}},{"tool":"building_bigdata_building_basic_info","status":"data… subject={"enterprise":"万科企业股份有限公司","matchKeyword":"万科企业股份有限公司","keywordType":"name","match_raw":"万科企业股份有限公司","resolved":true,"resolve_reason":"视为企业全称","building_query_scope":"explicit_estate_id_association"} 口径={"match_target":"万科企业股份有限公司","match_type":"楼宇/办公地址数据按企业主体匹配（keywordType=name）；楼宇查询支持按地区/楼宇类型/关键词检索","data_scope":"企业模糊查询、企业办公地址详情、企业办公地址统计、楼宇基础信息","products":["企业模糊查询","企业办公地址详情","企业办公地址统计","楼宇基础信息"],"limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。"} 实际记录样本={"office_details":[{"办公地址":"深圳市盐田区大梅沙环梅路33号万科中心","所在城市":"深圳市","所在区域":"盐田区","所在楼宇":"万科国际会议中心","楼宇ID":"d144fc5820d38c6f","入驻方式":"工商注册入驻","地址来源":"工商登记"},{"办公地址":"四川省成都市锦江区静安路1号万科城市花园98栋4楼1座","所在城市":"成都市","所在区域":"锦江区","所在楼宇":"阳光广场","楼宇ID":"d9b1bb10de28f662","入驻方式":"办公地址入驻","地址来源":"办公地址"}],"office_province":[{"省份":"广东省","办公点数":"5"},{"省份":"浙江省","办公点数":"2"}],"office_stats":[{"城市":"深圳市","办公地址数量":"4"},{"城市":"广州市","办公地址数量":"2"}],"settle_type":[{"入驻方式":"办公地址入驻","数量":"9"},{"入驻方式":"工商注册入驻","数量":"1"}],"source_type":[{"地址来源":"招聘信息","数量":"8"},{"地址来源":"工商登记","数量":"1"}],"building_query":[{"楼宇名称":"万科大厦","楼宇类型":"写字楼","楼宇地址":"广东省广州市番禺区兴泰路296号(番禺大道南交叉口西100米路南)","入驻企业数":"139","楼宇ID":"407aa79540860faa","关联依据":"办公地址明细明确返回的楼宇ID"},{"楼宇名称":"青岛国际金融中心","楼宇类型":"写字楼","楼宇地址":"山东省青岛市市南区香港中路59号","入驻企业数":"201","楼宇ID":"42b03f5754e73b48","关联依据":"办公地址明细明确返回的楼宇ID"}],"building_type":[{"楼宇类型":"写字楼","数量":"6"},{"楼宇类型":"产业园","数量":"1"}]} 可见章节=[{"title":"办公地址详情","note":"展示 10 条办公地址记录；上游总量 13"},{"title":"办公地址省份分布","note":"按办公地址所在省份聚合办公点数量"},{"title":"办公地址城市分布（全国口径）","note":"按企业全国办公地址统计城市分布"},{"title":"入驻方式分布","note":"按入驻方式（工商注册入驻 / 办公地址入驻）统计"},{"title":"地址来源分布","note":"按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计"},{"title":"明确ID关联楼宇明细","note":"仅由办公地址明细明确返回的楼宇ID关联；展示 10 个楼盘；上游总量 10"},{"title":"楼宇类型分布","note":"按楼宇类型聚合命中楼盘数量"}]
- **pass** 入驻方式与来源字段保持原值语义：已证明“入驻方式与来源字段保持原值语义”。 实际记录样本={"office_details":[{"办公地址":"深圳市盐田区大梅沙环梅路33号万科中心","所在城市":"深圳市","所在区域":"盐田区","所在楼宇":"万科国际会议中心","楼宇ID":"d144fc5820d38c6f","入驻方式":"工商注册入驻","地址来源":"工商登记"},{"办公地址":"四川省成都市锦江区静安路1号万科城市花园98栋4楼1座","所在城市":"成都市","所在区域":"锦江区","所在楼宇":"阳光广场","楼宇ID":"d9b1bb10de28f662","入驻方式":"办公地址入驻","地址来源":"办公地址"}],"office_province":[{"省份":"广东省","办公点数":"5"},{"省份":"浙江省","办公点数":"2"}],"office_stats":[{"城市":"深圳市","办公地址数量":"4"},{"城市":"广州市","办公地址数量":"2"}],"settle_type":[{"入驻方式":"办公地址入驻","数量":"9"},{"入驻方式":"工商注册入驻","数量":"1"}],"source_type":[{"地址来源":"招聘信息","数量":"8"},{"地址来源":"工商登记","数量":"1"}],"building_query":[{"楼宇名称":"万科大厦","楼宇类型":"写字楼","楼宇地址":"广东省广州市番禺区兴泰路296号(番禺大道南交叉口西100米路南)","入驻企业数":"139","楼宇ID":"407aa79540860faa","关联依据":"办公地址明细明确返回的楼宇ID"},{"楼宇名称":"青岛国际金融中心","楼宇类型":"写字楼","楼宇地址":"山东省青岛市市南区香港中路59号","入驻企业数":"201","楼宇ID":"42b03f5754e73b48","关联依据":"办公地址明细明确返回的楼宇ID"}],"building_type":[{"楼宇类型":"写字楼","数量":"6"},{"楼宇类型":"产业园","数量":"1"}]} 可见章节=[{"title":"办公地址详情","note":"展示 10 条办公地址记录；上游总量 13"},{"title":"办公地址省份分布","note":"按办公地址所在省份聚合办公点数量"},{"title":"办公地址城市分布（全国口径）","note":"按企业全国办公地址统计城市分布"},{"title":"入驻方式分布","note":"按入驻方式（工商注册入驻 / 办公地址入驻）统计"},{"title":"地址来源分布","note":"按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计"},{"title":"明确ID关联楼宇明细","note":"仅由办公地址明细明确返回的楼宇ID关联；展示 10 个楼盘；上游总量 10"},{"title":"楼宇类型分布","note":"按楼宇类型聚合命中楼盘数量"}]
- **pass** 不把办公地址解释为资产所有权：已证明“不把办公地址解释为资产所有权”。 摘要/局限={"summary":"本报告以“万科企业股份有限公司”为分析对象，基于楼宇/办公地址大数据，系统呈现企业办公地址详情、地址分布统计（城市/省份/入驻方式/来源）与楼宇查询明细。关键指标包括：办公地址总数 13、覆盖城市数 8、覆盖省份数 5、CR3城市集中度 62%、明确ID关联楼宇数 10。报告同时给出办公地址规模、城市分布广度、入驻方式结构与楼宇库存的多维度解读，便于选址招商、市场分析与竞争格局研究参考。","limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。","insights":[{"feature":"办公地址规模","evidence":"企业办公地址总数 13，地均 1.6 个/城市。","interpretation":"办公地址记录仅是公开来源线索，可用于后续核验；不能据此推断资产所有权、持续入驻、人员规模或实际经营状态。"},{"feature":"全国口径城市分布集中度","evidence":"“深圳市”公开办公地址统计占比约 31%，全国前 3 城市合计 62%（CR3）。","interpretation":"该集中度只描述公开地址统计的全国分布，不与地区筛选明细合并，也不证明实际经营覆盖或地址所有权。"}]}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)
[页面截图](browser.png)