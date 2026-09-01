# HONS 进销存管理系统 - 二次开发文档

本文档面向二次开发者，详细阐述系统的业务逻辑、核心机制、接口设计和开发规范。

---

## 目录

- [1. 系统架构概览](#1-系统架构概览)
- [2. 核心业务逻辑](#2-核心业务逻辑)
- [3. 表单配置与动态渲染](#3-表单配置与动态渲染)
- [4. 批次码段与防串货](#4-批次码段与防串货)
- [5. 库存服务详解](#5-库存服务详解)
- [6. 平台对接接口设计](#6-平台对接接口设计)
- [7. 数据备份与恢复](#7-数据备份与恢复)
- [8. 权限系统设计](#8-权限系统设计)
- [9. 前端模板结构](#9-前端模板结构)
- [10. API接口文档](#10-api接口文档)
- [11. 开发规范与注意事项](#11-开发规范与注意事项)
- [12. 常见问题排查](#12-常见问题排查)

---

## 1. 系统架构概览

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────┐
│  前端层    Bootstrap 5 + jQuery + Font Awesome       │
│            Jinja2 模板引擎                           │
├─────────────────────────────────────────────────────┤
│  路由层    Flask Blueprint（16个蓝图）               │
│            URL前缀 + 视图函数                        │
├─────────────────────────────────────────────────────┤
│  服务层    InventoryService / BackupService / ...    │
│            业务逻辑封装                              │
├─────────────────────────────────────────────────────┤
│  模型层    SQLAlchemy ORM（22张表）                  │
│            数据模型 + 关联关系                       │
├─────────────────────────────────────────────────────┤
│  数据层    SQLite（可切换 MySQL）                    │
└─────────────────────────────────────────────────────┘
```

### 1.2 蓝图注册清单

| 蓝图名 | URL前缀 | 功能模块 |
|--------|---------|----------|
| `auth` | `/auth` | 登录/登出 |
| `dashboard` | `/dashboard` | 仪表盘/数据报表 |
| `products` | `/products` | 商品管理 |
| `warehouses` | `/warehouses` | 仓库管理 |
| `suppliers` | `/suppliers` | 供应商管理 |
| `customers` | `/customers` | 客户管理 |
| `inventory` | `/inventory` | 库存查询/入库/出库/调拨/盘点 |
| `stock_transactions` | `/stock-transactions` | 出入库记录/打印/导出 |
| `purchase_orders` | `/purchase-orders` | 采购管理 |
| `platform_orders` | `/platform-orders` | 平台订单 |
| `batches` | `/batches` | 批次管理/批次码 |
| `form_config` | `/form-config` | 表单配置 |
| `finance` | `/finance` | 财务管理 |
| `users` | `/users` | 用户管理 |
| `roles` | `/roles` | 角色管理 |
| `backup` | `/backup` | 数据备份 |
| `data_import` | `/data-import` | 数据导入 |
| `operation_logs` | `/operation-logs` | 操作日志 |
| `system_config` | `/system-config` | 系统配置 |

### 1.3 服务层清单

| 服务 | 文件 | 职责 |
|------|------|------|
| InventoryService | `services/inventory_service.py` | 入库/出库/调拨/盘点 |
| BackupService | `services/backup_service.py` | 备份创建/校验/恢复/邮件发送 |
| SchedulerService | `services/scheduler_service.py` | APScheduler 定时任务管理 |
| ImportService | `services/import_service.py` | Excel 数据导入 |
| LogService | `services/log_service.py` | 操作日志记录 |
| OrderSyncService | `services/order_sync_service.py` | 平台订单同步 |
| RollbackService | `services/rollback_service.py` | 操作回滚 |
| AppLogging | `services/app_logging.py` | 应用日志配置 |

---

## 2. 核心业务逻辑

### 2.1 入库流程

```
用户填写入库单 → 校验商品/仓库/数量 → 生成单号(INyymmddXXX)
→ 解析批次码（支持范围格式 100001-100500）→ 创建批次和批次码
→ 创建 StockTransaction 记录 → 更新 Inventory 库存
→ 记录操作日志 → 提交事务
```

**关键方法**：`InventoryService.stock_in()`

**批次码解析规则**：
- 范围格式：`PREFIX100001-PREFIX100500` → 自动展开为数组
- 逗号分隔：`100001,100002,100003` → 直接拆分
- 范围上限：单次不超过 10000 个码

### 2.2 出库流程

```
用户填写出库单 → 校验库存是否充足 → 校验批次码有效性
→ 更新批次码状态为 sold → 更新批次剩余数量
→ 自动在备注中补充码段信息 → 创建 StockTransaction
→ 扣减库存 → 记录日志 → 提交事务
```

**关键方法**：`InventoryService.stock_out()`

**码段自动补全**：出库时自动在备注中追加 `[BATCH-xxx: start-end]` 格式的码段信息。

### 2.3 调拨流程

```
调出仓库扣减库存 → 批次码状态改为 transferred
→ 在调入仓库创建新批次（新 batch_no，保留原码段/日期/成本）
→ 在调入仓库创建新批次码（状态 in_stock）
→ 调入仓库增加库存 → 记录日志 → 提交事务
```

**关键方法**：`InventoryService.transfer()`

### 2.4 采购流程

```
创建采购单(POyymmddXXX) → 状态 draft → 确认后 pending
→ 采购入库确认 → 创建 StockTransaction(stock_in)
→ 更新采购单状态(partial/received) → 更新库存
```

### 2.5 库存预警

商品模型 `min_stock` 字段定义最低库存预警值。仪表盘统计低于预警值的商品并展示。

---

## 3. 表单配置与动态渲染

### 3.1 数据模型

**FormConfig（表单配置）**：
- `form_code`：唯一标识（如 `stock_in_form`、`stock_out_form`、`delivery_note_form`）
- `form_name`：显示名称
- `company_name`：随货同行单打印的公司名称
- `fields`：关联的 FormFieldConfig 列表

**FormFieldConfig（字段配置）**：
- `field_code`：字段代码（如 `product_name`、`batch_no`、`quantity`）
- `field_name`：表头显示名称
- `field_type`：字段类型（text/number/date/select）
- `is_visible`：是否显示
- `sort_order`：排序权重
- `default_value`：默认值
- `options`：选项（JSON，用于 select 类型）

### 3.2 默认表单配置

系统初始化时自动创建 3 套表单：

| form_code | 用途 | 默认字段 |
|-----------|------|----------|
| `stock_in_form` | 入库单打印/导出 | 序号、商品名称、规格、批次号、生产日期、有效期、数量、单价、金额、备注 |
| `stock_out_form` | 出库单打印/导出 | 序号、商品名称、规格、批次号、生产日期、有效期、数量、单价、金额、收货方、备注 |
| `delivery_note_form` | 随货同行单 | 序号、商品名称、规格、生产厂家、批准文号、批次号、生产日期、有效期、数量、备注 |

### 3.3 动态渲染机制

**导出 Excel 流程**：
1. 从 `FormConfig` 读取 `form_code` 对应的字段配置
2. 遍历 `form_fields`（按 `sort_order` 排序）
3. 对每条 `StockTransaction` 调用 `_get_field_value(tx, field_code, batch_info, product, customer)`
4. 按 `headers` 顺序生成 Excel 列

**字段值解析函数** `_get_field_value()`：
```python
def _get_field_value(tx, field_code, batch_info, product, customer=None):
    # 根据 field_code 返回对应值
    mapping = {
        'idx': lambda: idx,
        'product_name': lambda: tx.product.name if tx.product else '',
        'product_sku': lambda: tx.product.sku if tx.product else '',
        'specification': lambda: tx.product.specification if tx.product else '',
        'batch_no': lambda: tx.batch_no,
        'production_date': lambda: batch_info.get('production_date', '') if batch_info else '',
        'expire_date': lambda: batch_info.get('expire_date', '') if batch_info else '',
        'quantity': lambda: tx.quantity,
        'unit_cost': lambda: tx.unit_cost,
        'amount': lambda: tx.unit_cost * tx.quantity,
        'warehouse_name': lambda: tx.warehouse.name if tx.warehouse else '',
        'customer_name': lambda: tx.customer_name or (customer.name if customer else ''),
        'manufacturer': lambda: tx.product.manufacturer if tx.product else '',
        'approval_no': lambda: tx.product.approval_no if tx.product else '',
        'remark': lambda: tx.remark,
    }
    return mapping.get(field_code, lambda: '')()
```

**打印模板**：使用 Jinja2 模板遍历 `form_fields` 动态渲染表格列。

### 3.4 新增表单字段

如需在导出/打印中添加自定义字段：

1. 在 `FormFieldConfig` 中添加新记录
2. 在 `_get_field_value()` 的 `mapping` 字典中添加对应解析逻辑
3. 模板会自动按 `sort_order` 渲染新字段

---

## 4. 批次码段与防串货

### 4.1 码段结构

```
批次 (ProductBatch)
├── batch_no: BATCH-20260516-001
├── code_start: 100001
├── code_end: 100500
├── total_quantity: 500
├── remaining_quantity: 500
└── 批次码 (BatchCode) × 500
    ├── code: "100001", status: "in_stock"
    ├── code: "100002", status: "in_stock"
    └── ...
```

### 4.2 防串货机制

**码的生命周期**：
```
创建(入库) → in_stock → 出库 → sold → 记录 customer_id + sold_at
                          → 调拨 → transferred → 记录 transferred_at
```

**防串货校验**：
- 出库时必须指定有效的批次码
- 批次码必须属于该商品、该仓库、且状态为 `in_stock`
- 校验失败拒绝出库，防止串货

**追溯查询**：
- 通过 `BatchCode.code` 查询该码的流向（哪个客户、哪个出库单、何时售出）
- 通过 `BatchCode.batch_id` 查询该批次所有码的状态

### 4.3 批次号生成

```python
# 格式：BATCH-YYYYMMDD-XXX
# XXX 为当天序号（从 001 开始）
@staticmethod
def generate_batch_no():
    date_str = datetime.now().strftime('%Y%m%d')
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = ProductBatch.query.filter(ProductBatch.created_at >= today_start).count()
    return f'BATCH-{date_str}-{str(count + 1).zfill(3)}'
```

### 4.4 码段范围输入

入库时支持范围格式输入：
- `100001-100500` → 自动展开为 500 个码
- `PREFIX100001-PREFIX100500` → 保留前缀展开
- 范围上限 10000，超出报错

---

## 5. 库存服务详解

### 5.1 InventoryService 方法清单

| 方法 | 功能 | 参数 |
|------|------|------|
| `stock_in()` | 入库 | product_id, warehouse_id, quantity, unit_cost, batch_codes, production_date, expire_date |
| `stock_out()` | 出库 | product_id, warehouse_id, quantity, customer_id, batch_codes |
| `transfer()` | 调拨 | product_id, from_warehouse_id, to_warehouse_id, quantity, batch_codes |
| `adjust()` | 盘点调整 | product_id, warehouse_id, new_quantity, operator, remark |

### 5.2 出库码段自动记录

出库时如果提供了 `batch_codes`：

1. 校验每个码的有效性（存在、属于该商品/仓库、状态 in_stock）
2. 更新每个码的状态为 `sold`，记录 `customer_id`、`sold_at`
3. 更新所属批次的 `remaining_quantity`
4. 如果批次剩余为 0，状态改为 `depleted`
5. 自动在备注中追加码段信息：
   ```
   批次码段：[BATCH-20260516-001: 100001-100100]；[BATCH-20260517-002: 200001-200050]
   ```

### 5.3 库存扣减规则

- 出库时检查 `inventory.quantity >= quantity`
- 调拨时检查调出仓库库存
- 盘点调整直接设置 `inventory.quantity = new_quantity`
- 所有库存操作在事务中完成，失败自动回滚

---

## 6. 平台对接接口设计

### 6.1 抽象基类 PlatformAPI

```python
class PlatformAPI(ABC):
    @abstractmethod
    def authorize() -> str          # 授权获取 access_token
    @abstractmethod
    def get_orders(start_time, end_time, page, page_size) -> Dict   # 获取订单列表
    @abstractmethod
    def get_order_detail(order_no) -> Dict   # 获取订单详情
    def refresh_token() -> str     # 刷新 token（可选）
    def parse_order_data(raw) -> Dict   # 解析为统一格式
```

### 6.2 已实现的平台适配器

| 平台 | 文件 | 状态 |
|------|------|------|
| 淘宝 | `services/platform/taobao.py` | 预留（需实现签名逻辑） |
| 京东 | `services/platform/jd.py` | 预留 |
| 抖音 | `services/platform/douyin.py` | 预留 |
| 拼多多 | `services/platform/pdd.py` | 预留 |

### 6.3 统一订单格式

```python
{
    'platform_order_no': '平台订单号',
    'order_status': '状态',
    'buyer_info': {'name': '', 'phone': '', 'address': ''},
    'total_amount': 0,
    'shipping_fee': 0,
    'payment': 0,
    'order_time': '下单时间',
    'pay_time': '付款时间',
    'items': [{'product_name': '', 'sku': '', 'quantity': 0, 'price': 0}]
}
```

### 6.4 配置参数

在 `config.py` 中配置各平台的 AppKey/AppSecret：
```python
TAOBAO_APP_KEY = ''
TAOBAO_APP_SECRET = ''
# ... 其他平台类似
```

---

## 7. 数据备份与恢复

### 7.1 备份流程

```
触发备份 → 生成文件名(inventory_backup_YYYYMMDD_HHMMSS.zip)
→ SQLite .backup() 创建一致性副本 → 第一级校验（数据库完整性）
→ 压缩为 zip → 第二级校验（压缩包完整性）
→ 记录 BackupHistory → 可选发送邮件
```

### 7.2 备份校验

**第一级（数据库）**：
- 文件存在且 ≥ 32KB
- 不低于源库 50%
- `PRAGMA integrity_check` 通过
- 核心表齐全（users, products, warehouses, inventory, stock_transactions）
- users 表至少 1 条记录

**第二级（压缩包）**：
- zip 文件可读、未截断
- 内含 .db 文件
- 尺寸与第一级校验结果一致

### 7.3 恢复流程

```
上传/选择备份文件 → 校验文件有效性
→ 创建当前库临时备份 → 替换数据库文件
→ 失败自动回滚
```

### 7.4 定时备份

通过 APScheduler 每日定时执行：
- 默认时间：凌晨 2:00
- 时间可配置（`EmailConfig.backup_hour` / `backup_minute`）
- 多 worker 部署时通过 `RUN_SCHEDULER=0` 避免重复执行
- 使用 `coalesce=True` / `max_instances=1` 防止积压补跑

### 7.5 邮件发送

- 支持 SSL（端口 465）和 STARTTLS（端口 587/25）
- 发信前再次校验附件完整性
- 支持模板变量替换（日期、时间、文件名、文件大小等）

---

## 8. 权限系统设计

### 8.1 权限模块定义

系统预定义 9 个权限模块，共 35+ 个细粒度权限：

| 模块 | 标识 | 权限数 |
|------|------|--------|
| 仪表盘 | `dashboard` | 2 |
| 商品管理 | `product` | 5 |
| 仓库管理 | `warehouse` | 4 |
| 供应商管理 | `supplier` | 4 |
| 库存管理 | `inventory` | 6 |
| 采购管理 | `purchase` | 5 |
| 电商对接 | `platform` | 2 |
| 系统管理 | `system` | 6 |
| 财务管理 | `finance` | 5 |

### 8.2 默认角色

| 角色 | 权限范围 |
|------|----------|
| 管理员 | 全部权限 |
| 操作员 | 除电商对接、系统管理、财务管理外的所有权限 |

### 8.3 权限校验装饰器

```python
@utils.decorators.login_required      # 登录校验
@utils.decorators.admin_required      # 管理员权限校验
```

权限校验在 `Role.has_permission()` 中实现，通过 JSON 数组存储权限列表。

---

## 9. 前端模板结构

### 9.1 模板目录

```
templates/
├── base.html                    # 布局母版（侧边栏 + 顶栏）
├── dashboard.html               # 仪表盘
├── errors/                      # 错误页
│   ├── 400.html
│   ├── 403.html
│   ├── 404.html
│   ├── 429.html                 # 限流页（含 Retry-After 倒计时）
│   └── 500.html
├── products/                    # 商品管理
├── warehouses/                  # 仓库管理
├── suppliers/                   # 供应商管理
├── customers/                   # 客户管理
├── inventory/                   # 库存管理
│   ├── list.html                # 库存查询
│   ├── stock_in.html            # 入库操作
│   ├── stock_out.html           # 出库操作
│   ├── transfer.html            # 调拨操作
│   └── adjust.html              # 盘点调整
├── stock_transactions/          # 出入库记录
│   ├── list.html
│   ├── print_stock_in.html      # 入库单打印
│   ├── print_stock_out.html     # 出库单打印
│   └── print_delivery_note.html # 随货同行单打印
├── batches/                     # 批次管理
│   ├── list.html
│   ├── add.html
│   ├── edit.html
│   ├── codes.html               # 批次码明细
│   └── select_codes.html        # 出库码段选择
├── purchase_orders/             # 采购管理
├── platform_orders/             # 平台订单
├── finance/                     # 财务管理
├── users/                       # 用户管理
├── roles/                       # 角色管理
├── backup/                      # 数据备份
├── data_import/                 # 数据导入
├── operation_logs/              # 操作日志
├── system_config/               # 系统配置
├── form_config/                 # 表单配置
└── auth/                        # 登录
```

### 9.2 设计令牌（CSS 变量）

```css
/* static/css/modern-style.css */
:root {
  --primary: #2563eb;        /* 主色 */
  --primary-dark: #1d4ed8;   /* 主色深 */
  --success: #10b981;        /* 成功 */
  --warning: #f59e0b;        /* 警告 */
  --danger: #ef4444;         /* 危险 */
  --gray-50: #f9fafb;
  --gray-100: #f3f4f6;
  --gray-200: #e5e7eb;
  --gray-800: #1f2937;
  --radius: 8px;             /* 圆角 */
  --shadow: 0 1px 3px rgba(0,0,0,.1);
}
```

### 9.3 顶栏标题自动推导

`PAGE_TITLES` 字典按 `blueprint.endpoint` 自动映射顶栏标题，无需每个模板手动设置。

### 9.4 响应式设计

- 栅格系统：`modern-style.css` 自实现 + Bootstrap 5 并存
- 断点：`sm/md/lg/xl/xxl`（v2.2.0 补齐 xl/xxl）
- 移动端适配：表格横向滚动、卡片式布局

---

## 10. API接口文档

### 10.1 认证相关

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| GET | `/auth/login` | 登录页 | 公开 |
| POST | `/auth/login` | 提交登录 | 公开 |
| GET | `/auth/logout` | 登出 | 登录 |

### 10.2 库存相关

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| GET | `/inventory/` | 库存查询 | 登录 |
| GET/POST | `/inventory/stock_in` | 入库操作 | 登录 |
| GET/POST | `/inventory/stock_out` | 出库操作 | 登录 |
| GET/POST | `/inventory/transfer` | 调拨操作 | 登录 |
| GET/POST | `/inventory/adjust` | 盘点调整 | 登录 |
| GET | `/inventory/export` | 导出库存 | 登录 |
| GET | `/inventory/api/check` | AJAX查库存 | 登录 |
| GET | `/inventory/api/products-by-warehouse` | AJAX查商品 | 登录 |

### 10.3 批次相关

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| GET | `/batches/` | 批次列表 | 登录 |
| GET/POST | `/batches/add` | 添加批次 | 登录 |
| GET/POST | `/batches/edit/<id>` | 编辑批次 | 登录 |
| POST | `/batches/delete/<id>` | 删除批次 | 登录 |
| GET | `/batches/codes/<id>` | 批次码明细 | 登录 |
| GET | `/batches/query-codes` | 查询可用码段 | 登录 |
| GET | `/batches/select-codes` | 选择码段页面 | 登录 |

### 10.4 出入库记录

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| GET | `/stock-transactions/` | 出入库记录 | 登录 |
| GET | `/stock-transactions/export` | 导出记录 | 登录 |
| GET | `/stock-transactions/export/stock-in` | 导出入库单 | 登录 |
| GET | `/stock-transactions/export/stock-out` | 导出出库单 | 登录 |
| GET | `/stock-transactions/export/delivery-note` | 导出随货同行单 | 登录 |
| GET | `/stock-transactions/print/stock-in` | 打印入库单 | 登录 |
| GET | `/stock-transactions/print/stock-out` | 打印出库单 | 登录 |

### 10.5 其他模块路由

其他模块（商品、仓库、供应商、客户、采购、财务、用户、角色、备份、导入、日志、配置）遵循 RESTful 风格：

| 方法 | 路径模式 | 功能 |
|------|----------|------|
| GET | `/module/` | 列表 |
| GET/POST | `/module/create` | 新增 |
| GET/POST | `/module/edit/<id>` | 编辑 |
| POST | `/module/delete/<id>` | 删除 |
| GET | `/module/export` | 导出 |

---

## 11. 开发规范与注意事项

### 11.1 时间处理规范

**强制中国时区**：
- `app.py` 启动时执行 `os.environ['TZ']='Asia/Shanghai'; time.tzset()`
- systemd 单元设置 `Environment="TZ=Asia/Shanghai"`
- 所有 `datetime.now()` 一律为北京时间

**数据库时间格式**：
- DATETIME 列：`YYYY-MM-DD HH:MM:SS.ffffff`（6位微秒，不可截断）
- DATE 列：`YYYY-MM-DD`（纯日期，不含时间）
- 禁止截断微秒为毫秒，否则 SQLAlchemy C 扩展解析失败

### 11.2 事务管理

所有数据库操作必须使用事务：
```python
try:
    # 业务逻辑
    db.session.commit()
except ValueError:
    db.session.rollback()
    raise
except Exception as e:
    db.session.rollback()
    logger.error(f'操作失败: {e}', exc_info=True)
    raise ValueError(f'操作失败: {str(e)}')
```

### 11.3 日志记录

使用 `LogService.log_operation()` 记录关键操作：
```python
LogService.log_operation(
    user_id=session.get('user_id'),
    username=session.get('username'),
    operation_type='create/update/delete/export/print',
    module='product/inventory/...',
    description='操作描述',
    reference_type='关联类型',
    reference_no='关联单号',
    before_data={'旧值': ...},
    after_data={'新值': ...}
)
```

### 11.4 安全规范

- 所有 POST 表单必须包含 `csrf_token`（自动注入）
- 密码使用 `werkzeug.security` 哈希存储
- 登录失败锁定（Flask-Limiter）
- 接口限流：默认 60/分钟、200/小时、1000/天
- Session 24小时过期

### 11.5 前端改动注意

- `modern-style.css` 自实现栅格与 Bootstrap 5 并存
- 新增 `col-*` 断点类前需确认在 CSS 中有定义
- 顶栏标题自动推导，无需手动设置
- 错误页使用 Font Awesome（非 Bootstrap Icons）

### 11.6 多 worker 部署注意

- 定时任务通过 `RUN_SCHEDULER=0` 控制只在一个进程运行
- 或使用 `--preload` 参数让 `create_app()` 只执行一次
- 缓存使用 `FileSystemCache`（非内存），避免多进程缓存不一致

---

## 12. 常见问题排查

### 12.1 500 错误：时间格式问题

**现象**：`ValueError: Invalid isoformat string: '2025-11-17 08:00:00.000000'`

**原因**：
- DATETIME 列被写入带时间的字符串（如毫秒格式或补零后的微秒格式）
- DATE 列被写入带时间的字符串

**修复**：
```python
# DATE 列：截回纯日期
UPDATE product_batches SET production_date = SUBSTR(production_date, 1, 10);

# DATETIME 列：确保 6 位微秒格式
UPDATE stock_transactions SET created_at = SUBSTR(created_at, 1, 23) || '000'
WHERE LENGTH(created_at) = 23;
```

### 12.2 定时任务重复执行

**现象**：备份历史中出现同一时间点的重复记录

**原因**：多 worker 部署时每个 worker 都注册了定时任务

**解决**：
```bash
# 方式一：使用 --preload
gunicorn --preload -w 2 -b 127.0.0.1:5001 wsgi:application

# 方式二：非主进程关闭调度器
RUN_SCHEDULER=0 gunicorn -w 2 -b 127.0.0.1:5001 wsgi:application
```

### 12.3 端口占用

```bash
fuser -k 5001/tcp  # 释放端口
systemctl restart inventory
```

### 12.4 权限问题（宝塔）

```bash
chmod +x /usr/bin/python3.12  # 修复 Python 权限
```

### 12.5 数据库锁定

SQLite 不支持高并发写入。如遇锁定：
- 检查是否有未提交的事务
- 检查是否有其他进程正在备份
- 考虑切换 MySQL

---

## 附录：数据库表清单

| 表名 | 说明 | 核心字段 |
|------|------|----------|
| products | 商品 | sku, name, category, min_stock, barcode |
| warehouses | 仓库 | name, code |
| suppliers | 供应商 | name, contact_person, contact_phone |
| customers | 客户 | name, contact, phone, address |
| inventory | 库存 | product_id, warehouse_id, quantity |
| stock_transactions | 出入库记录 | transaction_no, type, quantity, batch_no |
| product_batches | 批次 | batch_no, code_start, code_end, remaining_quantity |
| batch_codes | 批次码 | batch_id, code, status, customer_id |
| purchase_orders | 采购单 | po_no, supplier_id, status |
| purchase_order_items | 采购明细 | purchase_order_id, product_id, quantity |
| bank_accounts | 资金账户 | name, type, current_balance |
| financial_transactions | 收支记录 | transaction_no, type, amount, direction |
| accounts_receivable | 应收款 | transaction_no, customer_id, amount, pending_amount |
| accounts_payable | 应付款 | transaction_no, supplier_id, amount, pending_amount |
| users | 用户 | username, password_hash, role_id |
| roles | 角色 | name, permissions(JSON) |
| operation_logs | 操作日志 | user_id, operation_type, module, description |
| system_config | 系统配置 | config_key, config_value |
| email_config | 邮箱配置 | smtp_server, sender_email, receiver_email |
| email_templates | 邮件模板 | name, subject, body |
| backup_history | 备份历史 | filename, file_size, status |
| form_config | 表单配置 | form_code, form_name, company_name |
| form_field_config | 字段配置 | form_config_id, field_code, field_name, sort_order |
| platform_orders | 平台订单 | platform_type, platform_order_no, status |
| platform_order_items | 平台订单明细 | platform_order_id, product_name, quantity |

---

*文档版本：v2.2.1 | 最后更新：2026-09-01*
