# building-skill：已验收示例

本目录只展示 **4 个完全通过的真实正向场景**（最低要求4例）。

每例均为真实、非空、非缓存调用；技术检查、独立业务检查和离线浏览器检查全部通过。不把空数据、报错处理或仅生成页面计作通过。历史验收记录保留在本地 test-records/；本目录的 HTML/Markdown 由原 JSON 重渲染，不代表重新查询或重新验收。

| 场景 | 真实使用需求 | 报告 |
|---|---|---|
| [地产集团办公网络](01-developer-office-network/README.md) | 请分析万科企业股份有限公司的办公地址分布和关联楼宇。 | [HTML](01-developer-office-network/report.html) / [MD](01-developer-office-network/report.md) / [JSON](01-developer-office-network/report.json) |
| [广州写字楼筛选](03-guangzhou-office-filter/README.md) | 请分析华为技术有限公司在广东省广州市的办公记录，并查看当地写字楼结果。 | [HTML](03-guangzhou-office-filter/report.html) / [MD](03-guangzhou-office-filter/report.md) / [JSON](03-guangzhou-office-filter/report.json) |
| [深圳产业园筛选](04-shenzhen-industrial-park/README.md) | 请查看比亚迪股份有限公司在广东省深圳市的办公地址，并筛选产业园楼宇。 | [HTML](04-shenzhen-industrial-park/report.html) / [MD](04-shenzhen-industrial-park/report.md) / [JSON](04-shenzhen-industrial-park/report.json) |
| [杭州综合体市场候选清单](09-hangzhou-complex-market-scan/README.md) | 以杭州商务拜访选址为背景，请单独筛选杭州市综合体楼宇候选，列出实际返回的楼宇名称，并按可用字段补充地址或物业类型；不要把市场候选解释为阿里巴巴的办公地址。 | [HTML](09-hangzhou-complex-market-scan/report.html) / [MD](09-hangzhou-complex-market-scan/report.md) / [JSON](09-hangzhou-complex-market-scan/report.json) |

- [逐例验收结果](results.json) · [业务复核](review.json) · [证据摘要](evidence-index.json)
- 完整测试记录仅存于本地 test-records/live-replaced-20261027/（仅本地审计用，不随本目录发布），不属于可展示示例。
- 当前数据与结论限于原查询时点及公开样本；覆盖率不代表准确率或低风险。
