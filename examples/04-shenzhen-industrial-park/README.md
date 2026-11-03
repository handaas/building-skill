# 深圳产业园筛选

- 用户需求：请查看比亚迪股份有限公司在广东省深圳市的办公地址，并筛选产业园楼宇。
- 决策用途：供应链拜访与产业集聚研究
- 本轮结果：**本轮检查通过**
- 实际工具调用：4；失败 0
- 章节覆盖率：100%（不代表证据质量）

## 预期业务检查（不自动宣称通过）

- 企业办公明细和产业园查询分别标明口径
- 楼宇类型为产业园
- 地区限制为深圳市
- 报告不输出未返回的 estateId 或推造关联

## 本轮自动检查发现


## 使用局限

- 产业园检索是地点线索而非厂区权属证明
- 办公地址数据不等同于生产基地清单

## 证据与复现

- [审计结果](result.json)
- [工具调用、结果形态与响应摘要哈希](calls.json)
- [JSON](report.json) / [HTML](report.html) / [Markdown](report.md)

```bash
python3 building-skill/scripts/compose_report.py --enterprise '比亚迪股份有限公司' --address '广东省,深圳市' --property-type '产业园' --page-size 10 --output building-skill/output/04-shenzhen-industrial-park/report.json --report-output building-skill/output/04-shenzhen-industrial-park/report.html
```

## 逐场景业务复核

当前真实产物逐项复核通过；结论限于本次上游公开样本与报告声明口径。

- **pass** 企业办公明细和产业园查询分别标明口径：已证明“企业办公明细和产业园查询分别标明口径”。 实际调用=[{"tool":"building_bigdata_fuzzy_search","status":"data","row_count":1,"reported_total":984,"arguments":{"matchKeyword":"比亚迪股份有限公司","pageSize":1}},{"tool":"building_bigdata_office_address_details","status":"data","row_count":6,"reported_total":6,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name","pageIndex":1,"pageSize":10,"address":"广东省,深圳市"}},{"tool":"building_bigdata_office_address_stats","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name"}},{"tool":"building_bigdata_building_query","status":"data","row_count":10,"reported_total":21763,"arguments":{"pageIndex":1,"pageSize":10,"address":"广东省,深圳市","estatePropertyType":"产业园"}}] subject={"enterprise":"比亚迪股份有限公司","matchKeyword":"比亚迪股份有限公司","keywordType":"name","match_raw":"比亚迪股份有限公司","resolved":true,"resolve_reason":"视为企业全称","building_query_scope":"independent_market_filter"} 口径={"match_target":"比亚迪股份有限公司","match_type":"楼宇/办公地址数据按企业主体匹配（keywordType=name）；楼宇查询支持按地区/楼宇类型/关键词检索","data_scope":"企业模糊查询、企业办公地址详情、企业办公地址统计、楼宇查询","products":["企业模糊查询","企业办公地址详情","企业办公地址统计","楼宇查询"],"limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。"} 实际记录样本={"office_details":[{"办公地址":"深圳市大鹏新区葵涌街道延安路一号","所在城市":"深圳市","所在区域":"龙岗区","所在楼宇":"葵涌工业园","楼宇ID":"f5b9132c9b5393f7","入驻方式":"工商注册入驻","地址来源":"工商登记"},{"办公地址":"广东省深圳市坪山区龙田街道老坑社区光科一路1号深圳百泰黄金珠宝大厦","所在城市":"深圳市","所在区域":"坪山区","所在楼宇":"深圳百泰黄金珠宝大厦","楼宇ID":"acab65b04153af61","入驻方式":"办公地址入驻","地址来源":"办公地址"}],"office_province":[{"省份":"广东省","办公点数":"6"}],"office_stats":[{"城市":"广州市","办公地址数量":"1"},{"城市":"淄博市","办公地址数量":"1"}],"settle_type":[{"入驻方式":"办公地址入驻","数量":"5"},{"入驻方式":"工商注册入驻","数量":"1"}],"source_type":[{"地址来源":"招聘信息","数量":"4"},{"地址来源":"工商登记","数量":"1"}],"building_query":[{"楼宇名称":"塘家第一工业区","楼宇类型":"产业园","楼宇地址":"深圳市光明新区公明街道塘家社区","入驻企业数":"17","楼宇ID":"fd435726863aad90","关联依据":"-"},{"楼宇名称":"光浩工业园","楼宇类型":"产业园","楼宇地址":"广东省深圳市龙华区云峰路23号","入驻企业数":"16","楼宇ID":"4bc949565855b110","关联依据":"-"}],"building_type":[{"楼宇类型":"产业园","数量":"10"}]} 可见章节=[{"title":"办公地址详情","note":"展示 6 条办公地址记录；上游总量 6"},{"title":"办公地址省份分布","note":"按办公地址所在省份聚合办公点数量"},{"title":"办公地址城市分布（全国口径）","note":"企业全国办公地址统计；不与地区筛选后的明细交叉计算比率"},{"title":"入驻方式分布","note":"按入驻方式（工商注册入驻 / 办公地址入驻）统计"},{"title":"地址来源分布","note":"按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计"},{"title":"独立楼宇筛选明细","note":"独立地区/类型筛选，不代表与查询企业关联；展示 10 个楼盘；上游总量 21763"},{"title":"楼宇类型分布","note":"按楼宇类型聚合命中楼盘数量"}]
- **pass** 楼宇类型为产业园：已证明“楼宇类型为产业园”。 实际调用=[{"tool":"building_bigdata_fuzzy_search","status":"data","row_count":1,"reported_total":984,"arguments":{"matchKeyword":"比亚迪股份有限公司","pageSize":1}},{"tool":"building_bigdata_office_address_details","status":"data","row_count":6,"reported_total":6,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name","pageIndex":1,"pageSize":10,"address":"广东省,深圳市"}},{"tool":"building_bigdata_office_address_stats","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name"}},{"tool":"building_bigdata_building_query","status":"data","row_count":10,"reported_total":21763,"arguments":{"pageIndex":1,"pageSize":10,"address":"广东省,深圳市","estatePropertyType":"产业园"}}] subject={"enterprise":"比亚迪股份有限公司","matchKeyword":"比亚迪股份有限公司","keywordType":"name","match_raw":"比亚迪股份有限公司","resolved":true,"resolve_reason":"视为企业全称","building_query_scope":"independent_market_filter"} 口径={"match_target":"比亚迪股份有限公司","match_type":"楼宇/办公地址数据按企业主体匹配（keywordType=name）；楼宇查询支持按地区/楼宇类型/关键词检索","data_scope":"企业模糊查询、企业办公地址详情、企业办公地址统计、楼宇查询","products":["企业模糊查询","企业办公地址详情","企业办公地址统计","楼宇查询"],"limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。"} 实际记录样本={"office_details":[{"办公地址":"深圳市大鹏新区葵涌街道延安路一号","所在城市":"深圳市","所在区域":"龙岗区","所在楼宇":"葵涌工业园","楼宇ID":"f5b9132c9b5393f7","入驻方式":"工商注册入驻","地址来源":"工商登记"},{"办公地址":"广东省深圳市坪山区龙田街道老坑社区光科一路1号深圳百泰黄金珠宝大厦","所在城市":"深圳市","所在区域":"坪山区","所在楼宇":"深圳百泰黄金珠宝大厦","楼宇ID":"acab65b04153af61","入驻方式":"办公地址入驻","地址来源":"办公地址"}],"office_province":[{"省份":"广东省","办公点数":"6"}],"office_stats":[{"城市":"广州市","办公地址数量":"1"},{"城市":"淄博市","办公地址数量":"1"}],"settle_type":[{"入驻方式":"办公地址入驻","数量":"5"},{"入驻方式":"工商注册入驻","数量":"1"}],"source_type":[{"地址来源":"招聘信息","数量":"4"},{"地址来源":"工商登记","数量":"1"}],"building_query":[{"楼宇名称":"塘家第一工业区","楼宇类型":"产业园","楼宇地址":"深圳市光明新区公明街道塘家社区","入驻企业数":"17","楼宇ID":"fd435726863aad90","关联依据":"-"},{"楼宇名称":"光浩工业园","楼宇类型":"产业园","楼宇地址":"广东省深圳市龙华区云峰路23号","入驻企业数":"16","楼宇ID":"4bc949565855b110","关联依据":"-"}],"building_type":[{"楼宇类型":"产业园","数量":"10"}]} 可见章节=[{"title":"办公地址详情","note":"展示 6 条办公地址记录；上游总量 6"},{"title":"办公地址省份分布","note":"按办公地址所在省份聚合办公点数量"},{"title":"办公地址城市分布（全国口径）","note":"企业全国办公地址统计；不与地区筛选后的明细交叉计算比率"},{"title":"入驻方式分布","note":"按入驻方式（工商注册入驻 / 办公地址入驻）统计"},{"title":"地址来源分布","note":"按地址来源类型（工商登记 / 办公地址 / 招聘信息）统计"},{"title":"独立楼宇筛选明细","note":"独立地区/类型筛选，不代表与查询企业关联；展示 10 个楼盘；上游总量 21763"},{"title":"楼宇类型分布","note":"按楼宇类型聚合命中楼盘数量"}]
- **pass** 地区限制为深圳市：已证明“地区限制为深圳市”。 实际调用=[{"tool":"building_bigdata_fuzzy_search","status":"data","row_count":1,"reported_total":984,"arguments":{"matchKeyword":"比亚迪股份有限公司","pageSize":1}},{"tool":"building_bigdata_office_address_details","status":"data","row_count":6,"reported_total":6,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name","pageIndex":1,"pageSize":10,"address":"广东省,深圳市"}},{"tool":"building_bigdata_office_address_stats","status":"data","row_count":null,"reported_total":null,"arguments":{"matchKeyword":"比亚迪股份有限公司","keywordType":"name"}},{"tool":"building_bigdata_building_query","status":"data","row_count":10,"reported_total":21763,"arguments":{"pageIndex":1,"pageSize":10,"address":"广东省,深圳市","estatePropertyType":"产业园"}}] subject={"enterprise":"比亚迪股份有限公司","matchKeyword":"比亚迪股份有限公司","keywordType":"name","match_raw":"比亚迪股份有限公司","resolved":true,"resolve_reason":"视为企业全称","building_query_scope":"independent_market_filter"} 口径={"match_target":"比亚迪股份有限公司","match_type":"楼宇/办公地址数据按企业主体匹配（keywordType=name）；楼宇查询支持按地区/楼宇类型/关键词检索","data_scope":"企业模糊查询、企业办公地址详情、企业办公地址统计、楼宇查询","products":["企业模糊查询","企业办公地址详情","企业办公地址统计","楼宇查询"],"limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。"}
- **pass** 报告不输出未返回的 estateId 或推造关联：已证明“报告不输出未返回的 estateId 或推造关联”。 摘要/局限={"summary":"本报告以“比亚迪股份有限公司”为分析对象，基于楼宇/办公地址大数据，系统呈现企业办公地址详情、地址分布统计（城市/省份/入驻方式/来源）与楼宇查询明细。关键指标包括：办公地址总数 6、覆盖省份数 1、筛选楼宇命中量 21763、注册资本 91.17 亿 人民币、年营业额 10亿以上。报告同时给出办公地址规模、城市分布广度、入驻方式结构与楼宇库存的多维度解读，便于选址招商、市场分析与竞争格局研究参考。","limit":"地址与入驻信息仅为公开数据线索，可能存在更新延迟；不证明楼宇/房产所有权、持续租赁、实际办公或人员驻场。地区筛选明细不得与全国统计交叉计算比率。","insights":[{"feature":"办公地址规模","evidence":"企业办公地址总数 6。","interpretation":"办公地址记录仅是公开来源线索，可用于后续核验；不能据此推断资产所有权、持续入驻、人员规模或实际经营状态。"},{"feature":"全国口径城市分布集中度","evidence":"地区筛选下仍为全国统计口径；“上海市”公开办公地址统计占比约 14%，全国前 3 城市合计 29%（CR3）。","interpretation":"该集中度只描述公开地址统计的全国分布，不与地区筛选明细合并，也不证明实际经营覆盖或地址所有权。"}]}

## 离线浏览器检查

[Ego Lite 离线图表、页面溢出和脚本检查](browser-check.json)