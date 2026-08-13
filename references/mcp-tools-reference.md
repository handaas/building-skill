# MCP 工具参考 — building-mcp-server

本 skill 连接的 MCP server：`handaas-mcp-server/building-mcp-server`（“楼宇大数据”）。

> **重要**：办公地址类工具入参为 `matchKeyword`（**企业全称** / 注册号 / 统一社会信用代码 / 企业 id）+ `keywordType`；
> `building_bigdata_building_query` 的 `matchKeyword` 可为楼宇名称 / 楼宇别名（用于市场检索）；当用户只给企业关键词时，必须先调关键词模糊查询补全全称。

## 通用约定

- `keywordType` 枚举：`name`（企业名称）/ `nameId`（企业 id）/ `regNumber`（注册号）/ `socialCreditCode`（统一社会信用代码）。
- `estatePropertyType` 枚举：`写字楼` / `产业园` / `综合体` / `公寓酒店` / `展会中心`。
- `address`：支持筛选省/市，不可多选，省市之间用英文逗号分隔，输入示例：`广东省,广州市`。
- 分页：`pageIndex` 从 1 开始；办公地址/楼宇查询 `pageSize` 单页最多 10。

---

## 工具清单

### 1. `building_bigdata_fuzzy_search` — 关键词模糊查询企业

用途：根据企业名称 / 人名 / 品牌 / 产品 / 岗位等关键词模糊查询企业列表，用于补全企业全称。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 匹配关键词 |
| `pageIndex` | int | 否 | 分页开始位置（默认 1） |
| `pageSize` | int | 否 | 单页最多 50 |

返回：`total` + 企业列表（`name`、`nameId`、`regCapitalValue`、`foundTime`、`operStatus`、`address`、`legalRepresentative`、`enterpriseType`、`catchReason` 命中原因等）。

product_id：`675cea1f0e009a9ea37edaa1`。

---

### 2. `building_bigdata_office_address_details` — 企业办公地址详情

用途：按企业主体返回办公地址明细，包括办公地址、所在楼宇、入驻方式、地址来源等。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称 / 注册号 / 统一社会信用代码 / 企业 id（无全称则先调 fuzzy_search） |
| `address` | string | 否 | 地区筛选，省/市英文逗号分隔，如 `广东省,广州市` |
| `pageIndex` | int | 否 | 从 1 开始（默认 1） |
| `keywordType` | string | 否 | 主体类型：name / nameId / regNumber / socialCreditCode |
| `pageSize` | int | 否 | 单页最多 10 |

返回（list + `total`）：`officeAddress`（地址）、`officeSourceType`（地址来源）、`officeSettleType`（入驻方式：工商注册入驻 / 办公地址入驻）、`estateName`（所在楼宇）、`estateId`（楼宇 id）。

product_id：`6786528b1677add9f934358f`。

---

### 3. `building_bigdata_office_address_stats` — 企业办公地址统计

用途：按企业主体返回办公地址城市分布统计。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 是 | 企业名称 / 注册号 / 统一社会信用代码 / 企业 id |
| `keywordType` | string | 否 | 主体类型：name / nameId / regNumber / socialCreditCode |

返回：`officeCityStats`（list of {city, count}：办公城市 / 办公地址数量）。

product_id：`6786528b1677add9f934359d`。

---

### 4. `building_bigdata_building_query` — 楼宇查询

用途：按楼宇名称 / 楼宇类型 / 地区查询楼盘信息，包括楼宇名称、楼宇别名、楼宇地址、楼宇类型、入驻企业数量。支持市场检索模式（不依赖企业主体）。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `matchKeyword` | string | 否 | 查询楼宇名称/别名包含关键词的楼盘 |
| `pageIndex` | int | 否 | 从 1 开始（默认 1） |
| `address` | string | 否 | 地区筛选，省/市英文逗号分隔 |
| `pageSize` | int | 否 | 单页最多 10（默认 10） |
| `estatePropertyType` | string | 否 | 楼宇类型：写字楼 / 产业园 / 综合体 / 公寓酒店 / 展会中心 |

返回（list + `total`）：`estateName`（楼宇名称）、`estateId`（楼宇 id）、`estateAliasName`（楼宇别名）、`estateAddress`（楼宇地址）、`estatePropertyType`（楼宇类型）、`estateEnterpriseCount`（入驻企业数量）。

product_id：`6786528b1677add9f93435db`。

---

## 推荐调用顺序（报告编排）

1. （若仅有关键词）`building_bigdata_fuzzy_search` → 取 `name` 作为全称。
2. `building_bigdata_office_address_details` → 办公地址明细（可加 `address` 过滤）。
3. `building_bigdata_office_address_stats` → 城市分布统计。
4. `building_bigdata_building_query` → 楼宇库存查询（可按 `address` / `estatePropertyType` 检索目标区域楼盘）。

> 单次企业报告通常调用 3-4 个工具；办公地址类工具入参为企业主体 `matchKeyword` + `keywordType`，楼宇查询可独立按地区/类型检索。
