# HONS 进销存系统 - 数据库设计文档

**数据库类型：** SQLite  
**ORM框架：** SQLAlchemy (Python)  
**数据库名：** inventory.db  
**总表数：** 22张

---

## 目录

- [1. 商品管理模块](#1-商品管理模块)
- [2. 仓库管理模块](#2-仓库管理模块)
- [3. 库存管理模块](#3-库存管理模块)
- [4. 批次管理模块](#4-批次管理模块)
- [5. 采购管理模块](#5-采购管理模块)
- [6. 客户管理模块](#6-客户管理模块)
- [7. 财务管理模块](#7-财务管理模块)
- [8. 用户权限模块](#8-用户权限模块)
- [9. 系统管理模块](#9-系统管理模块)
- [10. 平台订单模块](#10-平台订单模块)
- [11. 备份与邮件模块](#11-备份与邮件模块)
- [12. 表单配置模块](#12-表单配置模块)
- [表关系总结](#表关系总结)

---

## 1. 商品管理模块

### 1.1 products（商品表）

**表说明：** 存储商品基础信息，支持药品相关字段（剂型、生产厂家、批准文号）

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| sku | VARCHAR(64) | 商品编码 | 唯一，不可为空 | - |
| name | VARCHAR(128) | 商品名称 | 不可为空 | - |
| category | VARCHAR(64) | 商品分类 | - | '' |
| unit | VARCHAR(32) | 计量单位 | - | '个' |
| specification | VARCHAR(256) | 商品规格 | - | '' |
| barcode | VARCHAR(128) | 条形码（防窜货） | 唯一 | NULL |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| dosage_form | VARCHAR(64) | 剂型（药品） | - | '' |
| manufacturer | VARCHAR(256) | 生产厂家（药品） | - | '' |
| approval_no | VARCHAR(128) | 批准文号（药品） | - | '' |
| cost_price | NUMERIC(10,2) | 成本价 | - | 0 |
| selling_price | NUMERIC(10,2) | 售价 | - | 0 |
| description | TEXT | 商品描述 | - | '' |
| **min_stock** | INTEGER | **最低库存预警值** | - | 0 |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**关联关系：**
- `inventory_records` → Inventory（一对多，级联删除）
- `stock_transactions` → StockTransaction（一对多，保留历史）
- `purchase_order_items` → PurchaseOrderItem（一对多，级联删除）
- `batches` → ProductBatch（一对多，级联删除）

**索引：**
- UNIQUE(sku)
- UNIQUE(barcode)

---

## 2. 仓库管理模块

### 2.1 warehouses（仓库表）

**表说明：** 支持多仓库管理，每个仓库独立记录库存

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(128) | 仓库名称 | 不可为空 | - |
| code | VARCHAR(32) | 仓库编码 | 唯一，不可为空 | - |
| address | VARCHAR(256) | 仓库地址 | - | '' |
| contact_person | VARCHAR(64) | 联系人 | - | '' |
| contact_phone | VARCHAR(32) | 联系电话 | - | '' |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| created_at | DATETIME | 创建时间 | - | NOW |

**关联关系：**
- `inventory_records` → Inventory（一对多）
- `stock_transactions` → StockTransaction（一对多）
- `purchase_orders` → PurchaseOrder（一对多）
- `batches` → ProductBatch（一对多）

**索引：**
- UNIQUE(code)

---

## 3. 库存管理模块

### 3.1 inventory（库存表）

**表说明：** 记录商品在各仓库的实时库存数量

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| product_id | INTEGER | 商品ID | 外键 → products.id，不可为空 | - |
| warehouse_id | INTEGER | 仓库ID | 外键 → warehouses.id，不可为空 | - |
| **quantity** | INTEGER | **库存数量** | 不可为空 | 0 |
| updated_at | DATETIME | 更新时间 | - | NOW |

**唯一约束：** (product_id, warehouse_id) —— 同一商品在同一仓库只能有一条库存记录

**索引：**
- UNIQUE(product_id, warehouse_id)

---

### 3.2 stock_transactions（出入库记录表）

**表说明：** 记录所有出入库操作，支持入库、出库、调拨、盘点

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| transaction_no | VARCHAR(32) | 单号 | 唯一，不可为空 | 自动生成 |
| type | VARCHAR(32) | 类型 | 不可为空 | - |
| product_id | INTEGER | 商品ID | 外键（可为NULL） | NULL |
| product_name | VARCHAR(128) | 商品名称快照 | - | '' |
| warehouse_id | INTEGER | 仓库ID | 外键，不可为空 | - |
| customer_id | INTEGER | 客户ID | 外键 | NULL |
| customer_name | VARCHAR(128) | 客户名称 | - | '' |
| customer_address | VARCHAR(256) | 收货地址 | - | '' |
| quantity | INTEGER | 数量 | 不可为空 | - |
| unit_cost | NUMERIC(10,2) | 单位成本 | - | 0 |
| reference_no | VARCHAR(64) | 关联单号 | - | '' |
| batch_no | VARCHAR(64) | 批次号 | - | '' |
| batch_codes | TEXT | 批次码列表 | - | '' |
| remark | VARCHAR(256) | 备注 | - | '' |
| operator | VARCHAR(64) | 操作人 | - | '' |
| created_at | DATETIME | 创建时间 | - | NOW |

**type 可选值：**
- `stock_in` — 入库
- `stock_out` — 出库
- `transfer_in` — 调入
- `transfer_out` — 调出
- `adjustment` — 盘点调整

**单号格式：** IN20260516001 / OUT20260516001 / TI20260516001 / TO20260516001 / AD20260516001

**索引：**
- UNIQUE(transaction_no)
- INDEX(type)
- INDEX(product_id)
- INDEX(warehouse_id)
- INDEX(created_at)
- INDEX(type, created_at)

---

## 4. 批次管理模块（防窜货）

### 4.1 product_batches（商品批次表）

**表说明：** 管理入库批次，支持生产日期、有效期、防窜货码段

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| batch_no | VARCHAR(64) | 批次号 | 唯一，不可为空 | 自动生成 |
| product_id | INTEGER | 商品ID | 外键，不可为空 | - |
| warehouse_id | INTEGER | 仓库ID | 外键，不可为空 | - |
| supplier_id | INTEGER | 供应商ID | 外键 | NULL |
| code_start | INTEGER | 码段起始 | 不可为空 | - |
| code_end | INTEGER | 码段结束 | 不可为空 | - |
| total_quantity | INTEGER | 总数量 | 不可为空 | - |
| remaining_quantity | INTEGER | 剩余数量 | 不可为空 | - |
| cost_price | NUMERIC(10,2) | 采购成本 | - | 0 |
| production_date | DATE | 生产日期 | - | NULL |
| expire_date | DATE | 有效期至 | - | NULL |
| status | VARCHAR(20) | 状态 | - | 'active' |
| remark | TEXT | 备注 | - | '' |
| operator | VARCHAR(64) | 操作人 | - | '' |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**status 可选值：**
- `active` — 活跃
- `used` — 已使用
- `depleted` — 已耗尽
- `cancelled` — 已取消

**批次号格式：** BATCH-YYYYMMDD-XXX（如 BATCH-20260516-001）

**索引：**
- UNIQUE(batch_no)

---

### 4.2 batch_codes（批次码明细表）

**表说明：** 存储每个独立的防窜货码，追溯商品流向

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| batch_id | INTEGER | 批次ID | 外键，不可为空 | - |
| code | VARCHAR(64) | 商品码 | 不可为空 | - |
| status | VARCHAR(20) | 状态 | - | 'in_stock' |
| customer_id | INTEGER | 售往客户ID | 外键 | NULL |
| customer_name | VARCHAR(128) | 售往客户名称 | - | NULL |
| stock_out_id | INTEGER | 出库记录ID | - | NULL |
| stock_out_no | VARCHAR(64) | 出库单号 | - | NULL |
| sold_at | DATETIME | 销售时间 | - | NULL |
| transferred_at | DATETIME | 调拨时间 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |

**status 可选值：**
- `in_stock` — 在库
- `sold` — 已售
- `reserved` — 已预留
- `transferred` — 已调拨

**索引：**
- INDEX(batch_id)
- INDEX(status)
- INDEX(code)

---

## 5. 采购管理模块

### 5.1 suppliers（供应商表）

**表说明：** 供应商信息管理

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(128) | 供应商名称 | 不可为空 | - |
| contact_person | VARCHAR(64) | 联系人 | - | '' |
| contact_phone | VARCHAR(32) | 联系电话 | - | '' |
| email | VARCHAR(128) | 邮箱 | - | '' |
| address | VARCHAR(256) | 地址 | - | '' |
| description | TEXT | 备注 | - | '' |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| created_at | DATETIME | 创建时间 | - | NOW |

**关联关系：**
- `purchase_orders` → PurchaseOrder（一对多）
- `batches` → ProductBatch（一对多）
- `payables` → AccountsPayable（一对多）

---

### 5.2 purchase_orders（采购单表）

**表说明：** 采购订单主表

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| po_no | VARCHAR(32) | 采购单号 | 唯一，不可为空 | 自动生成 |
| supplier_id | INTEGER | 供应商ID | 外键，不可为空 | - |
| warehouse_id | INTEGER | 入库仓库ID | 外键，不可为空 | - |
| status | VARCHAR(32) | 状态 | - | 'draft' |
| total_amount | NUMERIC(12,2) | 总金额 | - | 0 |
| remark | TEXT | 备注 | - | '' |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**status 可选值：**
- `draft` — 草稿
- `pending` — 待入库
- `partial` — 部分入库
- `received` — 已入库
- `cancelled` — 已取消

**采购单号格式：** POYYYYMMDDXXX（如 PO20260516001）

**索引：**
- UNIQUE(po_no)

---

### 5.3 purchase_order_items（采购单明细表）

**表说明：** 采购单商品明细

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| purchase_order_id | INTEGER | 采购单ID | 外键，不可为空 | - |
| product_id | INTEGER | 商品ID | 外键，不可为空 | - |
| quantity | INTEGER | 采购数量 | 不可为空 | - |
| unit_cost | NUMERIC(10,2) | 单位成本 | - | 0 |
| received_quantity | INTEGER | 已入库数量 | - | 0 |

---

## 6. 客户管理模块

### 6.1 customers（客户表）

**表说明：** 客户信息管理，支持发票信息

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(128) | 客户名称 | 不可为空 | - |
| contact | VARCHAR(64) | 联系人 | - | NULL |
| phone | VARCHAR(20) | 联系电话 | - | NULL |
| address | VARCHAR(256) | 收货地址 | - | NULL |
| email | VARCHAR(120) | 电子邮箱 | - | NULL |
| tax_no | VARCHAR(64) | 税号 | - | NULL |
| bank | VARCHAR(128) | 开户行 | - | NULL |
| account_no | VARCHAR(64) | 账号 | - | NULL |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| remark | TEXT | 备注 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**关联关系：**
- `stock_transactions` → StockTransaction（一对多）
- `receivables` → AccountsReceivable（一对多）
- `batch_codes` → BatchCode（一对多）

---

## 7. 财务管理模块

### 7.1 bank_accounts（资金账户表）

**表说明：** 管理银行账户、现金、信用卡等资金账户

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(64) | 账户名称 | 不可为空 | - |
| code | VARCHAR(32) | 账户编码 | - | NULL |
| type | VARCHAR(32) | 类型 | - | 'bank' |
| account_no | VARCHAR(64) | 账号 | - | NULL |
| opening_balance | NUMERIC(12,2) | 期初余额 | - | 0 |
| current_balance | NUMERIC(12,2) | 当前余额 | - | 0 |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| remark | TEXT | 备注 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**type 可选值：**
- `cash` — 现金
- `bank` — 银行账户
- `card` — 信用卡

---

### 7.2 financial_transactions（收支记录表）

**表说明：** 记录所有收支流水

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| transaction_no | VARCHAR(32) | 单号 | 唯一，不可为空 | 自动生成 |
| type | VARCHAR(32) | 类型 | 不可为空 | - |
| category | VARCHAR(64) | 收支分类 | 不可为空 | - |
| amount | NUMERIC(12,2) | 金额 | 不可为空 | - |
| account_id | INTEGER | 账户ID | 外键 | NULL |
| direction | VARCHAR(16) | 方向 | - | 'in' |
| related_type | VARCHAR(32) | 关联类型 | - | NULL |
| related_id | INTEGER | 关联ID | - | NULL |
| counterparty_name | VARCHAR(128) | 对方单位/个人 | - | NULL |
| payment_method | VARCHAR(32) | 付款方式 | - | NULL |
| status | VARCHAR(16) | 状态 | - | 'completed' |
| transaction_date | DATE | 交易日期 | 不可为空 | - |
| operator | VARCHAR(64) | 操作人 | - | NULL |
| remark | TEXT | 备注 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |

**type 可选值：**
- `income` — 收入
- `expense` — 支出
- `transfer` — 转账

**payment_method 可选值：**
- `cash` — 现金
- `bank` — 银行转账
- `card` — 刷卡
- `alipay` — 支付宝
- `wechat` — 微信

**status 可选值：**
- `pending` — 待确认
- `completed` — 已完成
- `cancelled` — 已取消

**单号格式：** INC20260516001（收入）/ EXP20260516001（支出）/ TRF20260516001（转账）

---

### 7.3 accounts_receivable（应收款表）

**表说明：** 记录客户应收账款

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| transaction_no | VARCHAR(32) | 单号 | 唯一，不可为空 | 自动生成 |
| customer_id | INTEGER | 客户ID | 外键 | NULL |
| customer_name | VARCHAR(128) | 客户名称 | 不可为空 | - |
| customer_address | VARCHAR(256) | 收货地址 | - | NULL |
| amount | NUMERIC(12,2) | 应收金额 | 不可为空 | - |
| paid_amount | NUMERIC(12,2) | 已收金额 | - | 0 |
| pending_amount | NUMERIC(12,2) | 待收金额 | 不可为空 | - |
| invoice_no | VARCHAR(64) | 发票号 | - | NULL |
| due_date | DATE | 到期日 | - | NULL |
| related_type | VARCHAR(32) | 关联类型 | - | NULL |
| related_id | INTEGER | 关联ID | - | NULL |
| related_no | VARCHAR(64) | 关联单号 | - | NULL |
| status | VARCHAR(16) | 状态 | - | 'pending' |
| remark | TEXT | 备注 | - | NULL |
| operator | VARCHAR(64) | 操作人 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**status 可选值：**
- `pending` — 待收款
- `partial` — 部分收款
- `received` — 已收清
- `written_off` — 已核销

**单号格式：** ARYYYYMMDDXXX（如 AR20260516001）

---

### 7.4 accounts_payable（应付款表）

**表说明：** 记录供应商应付账款

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| transaction_no | VARCHAR(32) | 单号 | 唯一，不可为空 | 自动生成 |
| supplier_id | INTEGER | 供应商ID | 外键 | NULL |
| supplier_name | VARCHAR(128) | 供应商名称 | 不可为空 | - |
| supplier_contact | VARCHAR(64) | 供应商联系人 | - | NULL |
| supplier_phone | VARCHAR(20) | 供应商电话 | - | NULL |
| amount | NUMERIC(12,2) | 应付金额 | 不可为空 | - |
| paid_amount | NUMERIC(12,2) | 已付金额 | - | 0 |
| pending_amount | NUMERIC(12,2) | 待付金额 | 不可为空 | - |
| invoice_no | VARCHAR(64) | 发票号 | - | NULL |
| due_date | DATE | 到期日 | - | NULL |
| related_type | VARCHAR(32) | 关联类型 | - | NULL |
| related_id | INTEGER | 关联ID | - | NULL |
| related_no | VARCHAR(64) | 关联单号 | - | NULL |
| status | VARCHAR(16) | 状态 | - | 'pending' |
| remark | TEXT | 备注 | - | NULL |
| operator | VARCHAR(64) | 操作人 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**status 可选值：**
- `pending` — 待付款
- `partial` — 部分付款
- `paid` — 已付清
- `cancelled` — 已取消

**单号格式：** APYYYYMMDDXXX（如 AP20260516001）

---

## 8. 用户权限模块

### 8.1 users（用户表）

**表说明：** 系统用户账号

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| username | VARCHAR(80) | 用户名 | 唯一，不可为空 | - |
| password_hash | VARCHAR(256) | 密码哈希 | 不可为空 | - |
| real_name | VARCHAR(80) | 真实姓名 | - | NULL |
| role | VARCHAR(20) | 角色（兼容） | - | 'user' |
| role_id | INTEGER | 角色ID | 外键 | NULL |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| phone | VARCHAR(20) | 手机号 | - | NULL |
| email | VARCHAR(120) | 邮箱 | - | NULL |
| force_change_password | BOOLEAN | 强制修改密码 | - | FALSE |
| password_changed_at | DATETIME | 密码修改时间 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**密码强度要求：**
- 至少8个字符
- 包含大写字母
- 包含小写字母
- 包含数字
- 包含特殊字符 (!@#$%^&* 等)

**索引：**
- UNIQUE(username)

---

### 8.2 roles（角色表）

**表说明：** 角色与权限管理，支持细粒度权限控制

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(50) | 角色名称 | 唯一，不可为空 | - |
| description | VARCHAR(200) | 角色描述 | - | NULL |
| permissions | TEXT | 权限列表 | - | '[]' |
| is_system | BOOLEAN | 是否系统内置 | - | FALSE |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**权限模块：**

| 模块 | 权限标识 | 说明 |
|------|----------|------|
| 仪表盘 | dashboard.view | 查看仪表盘 |
| 仪表盘 | dashboard.reports | 查看数据报表 |
| 商品管理 | product.view/create/edit/delete/export | 商品CRUD |
| 仓库管理 | warehouse.view/create/edit/delete | 仓库CRUD |
| 供应商管理 | supplier.view/create/edit/delete | 供应商CRUD |
| 库存管理 | inventory.view/stock_in/stock_out/transfer/adjust/records | 库存操作 |
| 采购管理 | purchase.view/create/edit/delete/receive | 采购CRUD+入库 |
| 电商对接 | platform.orders/api_config | 平台订单、API配置 |
| 系统管理 | system.users/roles/config/backup/logs/import | 系统管理 |
| 财务管理 | finance.accounts/transactions/receivables/payables/reports | 财务管理 |

**索引：**
- UNIQUE(name)

---

## 9. 系统管理模块

### 9.1 system_configs（系统配置表）

**表说明：** 存储系统全局配置（键值对）

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| config_key | VARCHAR(100) | 配置键 | 唯一，不可为空 | - |
| config_value | TEXT | 配置值 | - | NULL |
| config_type | VARCHAR(20) | 配置类型 | - | 'text' |
| description | VARCHAR(200) | 配置描述 | - | NULL |
| updated_at | DATETIME | 更新时间 | - | NOW |
| updated_by | INTEGER | 更新人ID | 外键 | NULL |

**config_type 可选值：**
- `text` — 文本
- `number` — 数字
- `image` — 图片
- `color` — 颜色
- `boolean` — 布尔值

**默认配置项：**
- `site_name` — 网站名称
- `site_logo` — 网站LOGO
- `copyright` — 版权信息
- `items_per_page` — 每页显示条数
- `enable_email_notify` — 启用邮件通知
- `low_stock_alert` — 库存预警

**索引：**
- UNIQUE(config_key)

---

### 9.2 operation_logs（操作日志表）

**表说明：** 记录所有关键操作，支持审计追溯

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| user_id | INTEGER | 用户ID | 外键 | NULL |
| username | VARCHAR(80) | 用户名 | - | NULL |
| operation_type | VARCHAR(50) | 操作类型 | - | NULL |
| module | VARCHAR(50) | 模块名 | - | NULL |
| description | TEXT | 操作描述 | - | NULL |
| reference_type | VARCHAR(50) | 关联类型 | - | NULL |
| reference_no | VARCHAR(100) | 关联单号 | - | NULL |
| reference_id | INTEGER | 关联ID | - | NULL |
| before_data | TEXT | 操作前数据(JSON) | - | NULL |
| after_data | TEXT | 操作后数据(JSON) | - | NULL |
| ip_address | VARCHAR(50) | IP地址 | - | NULL |
| user_agent | VARCHAR(200) | 用户代理 | - | NULL |
| request_url | VARCHAR(500) | 请求URL | - | NULL |
| request_method | VARCHAR(10) | 请求方法 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |

**operation_type 可选值：**
- `login` — 登录
- `logout` — 登出
- `create` — 创建
- `update` — 更新
- `delete` — 删除
- `import` — 导入
- `export` — 导出
- `view` — 查看
- `approve` — 审批
- `reject` — 拒绝
- `print` — 打印
- `transfer` — 调拨
- `stock_in` — 入库
- `stock_out` — 出库
- `adjust` — 调整
- `collect` — 收款
- `pay` — 付款
- `backup` — 备份

**module 可选值：**
- `product` — 商品
- `warehouse` — 仓库
- `supplier` — 供应商
- `customer` — 客户
- `inventory` — 库存
- `purchase` — 采购
- `transaction` — 出入库
- `finance` — 财务
- `user` — 用户
- `role` — 角色
- `backup` — 备份
- `system` — 系统
- `auth` — 认证

---

## 10. 平台订单模块

### 10.1 platform_orders（平台订单表）

**表说明：** 电商平台订单同步（预留功能）

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| platform | VARCHAR(32) | 平台 | - | '' |
| platform_order_no | VARCHAR(64) | 平台订单号 | - | '' |
| order_status | VARCHAR(32) | 订单状态 | - | '' |
| buyer_info | TEXT | 买家信息(JSON) | - | '' |
| total_amount | NUMERIC(12,2) | 订单金额 | - | 0 |
| shipping_fee | NUMERIC(10,2) | 运费 | - | 0 |
| payment | NUMERIC(12,2) | 实付金额 | - | 0 |
| order_time | DATETIME | 下单时间 | - | NULL |
| pay_time | DATETIME | 付款时间 | - | NULL |
| remark | TEXT | 备注 | - | '' |
| raw_data | TEXT | 原始数据(JSON) | - | '' |
| synced_at | DATETIME | 同步时间 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |

**platform 可选值：**
- `taobao` — 淘宝
- `jd` — 京东
- `douyin` — 抖音
- `pdd` — 拼多多

---

### 10.2 platform_order_items（平台订单明细表）

**表说明：** 平台订单商品明细

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| platform_order_id | INTEGER | 平台订单ID | 外键，不可为空 | - |
| product_name | VARCHAR(256) | 商品名称 | - | '' |
| sku | VARCHAR(64) | SKU编码 | - | '' |
| quantity | INTEGER | 数量 | - | 0 |
| unit_price | NUMERIC(10,2) | 单价 | - | 0 |
| total_price | NUMERIC(10,2) | 小计 | - | 0 |
| spec | VARCHAR(256) | 规格 | - | '' |

---

## 11. 备份与邮件模块

### 11.1 backup_history（备份历史表）

**表说明：** 记录系统备份历史

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| filename | VARCHAR(200) | 文件名 | 不可为空 | - |
| file_size | INTEGER | 文件大小(字节) | - | NULL |
| backup_type | VARCHAR(20) | 备份类型 | - | 'manual' |
| status | VARCHAR(20) | 状态 | - | 'success' |
| error_message | TEXT | 错误信息 | - | NULL |
| sent_to_email | BOOLEAN | 已发送邮件 | - | FALSE |
| email_status | VARCHAR(20) | 邮件状态 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |

**backup_type 可选值：**
- `manual` — 手动备份
- `auto` — 自动备份

**status 可选值：**
- `success` — 成功
- `failed` — 失败

---

### 11.2 email_configs（邮件配置表）

**表说明：** SMTP邮件发送配置

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| smtp_server | VARCHAR(100) | SMTP服务器 | 不可为空 | 'smtp.qq.com' |
| smtp_port | INTEGER | SMTP端口 | 不可为空 | 587 |
| sender_email | VARCHAR(120) | 发件人邮箱 | 不可为空 | - |
| sender_password | VARCHAR(100) | 授权码/密码 | 不可为空 | - |
| receiver_email | VARCHAR(120) | 收件人邮箱 | 不可为空 | - |
| use_tls | BOOLEAN | 使用TLS | - | TRUE |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| enable_auto_backup | BOOLEAN | 启用自动备份 | - | FALSE |
| backup_hour | INTEGER | 备份小时 | - | 2 |
| backup_minute | INTEGER | 备份分钟 | - | 0 |
| selected_template_id | INTEGER | 当前模板ID | 外键 | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

---

### 11.3 email_templates（邮件模板表）

**表说明：** 备份通知邮件模板

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| name | VARCHAR(100) | 模板名称 | 不可为空 | - |
| description | VARCHAR(255) | 模板描述 | - | NULL |
| subject | VARCHAR(200) | 邮件主题 | 不可为空 | - |
| body | TEXT | 邮件正文 | 不可为空 | - |
| is_builtin | BOOLEAN | 是否内置 | - | FALSE |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| sort_order | INTEGER | 排序 | - | 0 |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**支持变量：**
- `{date}` — 日期
- `{datetime}` — 日期时间
- `{user_name}` — 用户名
- `{filename}` — 备份文件名
- `{file_size}` — 文件大小
- `{backup_type}` — 备份类型
- `{system_name}` — 系统名称
- `{send_time}` — 发送时间

**内置模板：**
- 标准备份通知
- 简洁通知
- 详细报告
- 紧急告警
- 极简模式

---

## 12. 表单配置模块

### 12.1 form_config（表单配置表）

**表说明：** 自定义出入库单、随货同行单字段配置

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| form_code | VARCHAR(50) | 表单代码 | 唯一，不可为空 | - |
| form_name | VARCHAR(100) | 表单名称 | 不可为空 | - |
| description | TEXT | 描述 | - | NULL |
| is_active | BOOLEAN | 是否启用 | - | TRUE |
| company_name | VARCHAR(200) | 公司名称 | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |
| created_by | INTEGER | 创建人ID | - | NULL |

**默认表单：**
- 入库单
- 出库单
- 随货同行单

---

### 12.2 form_field_config（表单字段配置表）

**表说明：** 表单字段详细配置

| 字段名 | 类型 | 说明 | 约束 | 默认值 |
|--------|------|------|------|--------|
| id | INTEGER | 主键 | 自增 | - |
| form_config_id | INTEGER | 表单配置ID | 外键，不可为空 | - |
| field_code | VARCHAR(50) | 字段代码 | 不可为空 | - |
| field_name | VARCHAR(100) | 字段名称（表头） | 不可为空 | - |
| field_type | VARCHAR(50) | 字段类型 | - | 'text' |
| is_visible | BOOLEAN | 是否显示 | - | TRUE |
| is_required | BOOLEAN | 是否必填 | - | FALSE |
| sort_order | INTEGER | 排序 | - | 0 |
| default_value | VARCHAR(255) | 默认值 | - | NULL |
| options | TEXT | 选项(JSON) | - | NULL |
| created_at | DATETIME | 创建时间 | - | NOW |
| updated_at | DATETIME | 更新时间 | - | NOW |

**field_type 可选值：**
- `text` — 文本
- `number` — 数字
- `date` — 日期
- `select` — 下拉选择

**唯一约束：** (form_config_id, field_code)

---

## 表关系总结

```
┌─────────────────────────────────────────────────────────────────────┐
│                         商品管理                                      │
│  products ─┬─ inventory ─────────── warehouses                       │
│            ├─ stock_transactions ─── warehouses, customers           │
│            ├─ purchase_order_items ─ purchase_orders ─ suppliers     │
│            ├─ product_batches ────── warehouses, suppliers          │
│            └─ batch_codes ────────── customers                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         客户管理                                      │
│  customers ─┬─ stock_transactions                                    │
│              ├─ accounts_receivable                                  │
│              └─ batch_codes                                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         供应商管理                                    │
│  suppliers ─┬─ purchase_orders                                       │
│              ├─ accounts_payable                                     │
│              └─ product_batches                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         用户权限                                      │
│  users ─┬─ operation_logs                                            │
│          ├─ roles                                                    │
│          └─ system_configs                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 表统计

| 模块 | 表名 | 说明 |
|------|------|------|
| **商品管理** | products | 商品基础信息 |
| **仓库管理** | warehouses | 仓库信息 |
| **库存管理** | inventory | 实时库存 |
| | stock_transactions | 出入库记录 |
| **批次管理** | product_batches | 批次管理 |
| | batch_codes | 防窜货码 |
| **采购管理** | suppliers | 供应商 |
| | purchase_orders | 采购单 |
| | purchase_order_items | 采购单明细 |
| **客户管理** | customers | 客户信息 |
| **财务管理** | bank_accounts | 资金账户 |
| | financial_transactions | 收支记录 |
| | accounts_receivable | 应收款 |
| | accounts_payable | 应付款 |
| **用户权限** | users | 用户账号 |
| | roles | 角色权限 |
| **系统管理** | system_configs | 系统配置 |
| | operation_logs | 操作日志 |
| **平台对接** | platform_orders | 平台订单（预留） |
| | platform_order_items | 订单明细（预留） |
| **备份邮件** | backup_history | 备份历史 |
| | email_configs | 邮件配置 |
| | email_templates | 邮件模板 |
| **表单配置** | form_config | 表单配置 |
| | form_field_config | 字段配置 |

**总计：22张表**

---

## 关键设计说明

### 库存预警机制
- 商品表 `products.min_stock` 存储最低库存预警值
- 库存表 `inventory.quantity` 存储实时库存数量
- 系统定期检查 `quantity < min_stock` 的商品，触发预警

### 防窜货追溯
- 批次表 `product_batches` 记录入库码段范围（code_start ~ code_end）
- 批次码表 `batch_codes` 存储每个独立的防窜货码
- 出库时记录批次码流向（customer_id, stock_out_id），实现商品追溯

### 多仓库支持
- 库存按商品+仓库维度管理，同一商品在不同仓库有独立库存
- 支持仓库间调拨（transfer_in / transfer_out）

### 单号生成规则
| 类型 | 格式 | 示例 |
|------|------|------|
| 入库单 | IN + 日期 + 序号 | IN20260516001 |
| 出库单 | OUT + 日期 + 序号 | OUT20260516001 |
| 调拨单 | TI/TO + 日期 + 序号 | TI20260516001 |
| 盘点单 | AD + 日期 + 序号 | AD20260516001 |
| 采购单 | PO + 日期 + 序号 | PO20260516001 |
| 批次号 | BATCH-日期-序号 | BATCH-20260516-001 |
| 应收单 | AR + 日期 + 序号 | AR20260516001 |
| 应付单 | AP + 日期 + 序号 | AP20260516001 |
| 收支单 | INC/EXP/TRF + 日期 + 序号 | INC20260516001 |

---

*文档版本：v1.0*  
*最后更新：2026-07-31*