# HONS 进销存管理系统

基于 Flask 的轻量级进销存管理系统，专为医药/商品流通行业设计，支持商品管理、批次追踪、库存管理、采购销售、财务统计、随货同行单打印等功能。

[![Flask](https://img.shields.io/badge/Flask-3.1.3-000000?style=flat-square&logo=flask)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.2.0-blue?style=flat-square)](#更新日志)

---

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| **后端** | Flask 3.1.3 + SQLAlchemy 2.0 + SQLite (可切换 MySQL) |
| **前端** | Bootstrap 5 + jQuery + Font Awesome |
| **部署** | Gunicorn + Nginx |
| **Python** | 3.10+ (推荐 3.12) |

---

## 功能特性

### 核心业务

| 模块 | 功能说明 |
|------|---------|
| **商品管理** | SKU 编码、分类、规格、条形码、剂型、生产厂家、批准文号 |
| **批次管理** | 生产批号、生产日期、有效期、批次码段追踪、防串货 |
| **仓库管理** | 多仓库、库存调拨、库存预警、实时库存 |
| **采购管理** | 采购单、入库验收、供应商管理 |
| **销售管理** | 出库管理、客户管理、随货同行单打印 |
| **平台对接** | 预留淘宝/京东/抖音/拼多多订单同步接口 |

### 财务管理

| 模块 | 功能说明 |
|------|---------|
| **账户管理** | 银行账户、资金流水 |
| **应收应付** | 收款/付款、对账核销 |
| **财务报表** | 利润分析、收支统计 |

### 系统管理

| 模块 | 功能说明 |
|------|---------|
| **表单配置** | 自定义出入库单/随货同行单字段，实时预览 |
| **权限管理** | 角色权限、用户管理、操作日志 |
| **数据备份** | 自动备份、邮件发送、数据恢复 |
| **数据导入** | Excel 批量导入商品/客户/供应商 |

### 打印与导出

- **动态表单** — 按表单配置动态生成导出 Excel 和打印模板
- **随货同行单** — 公司名称可自定义，字段按配置动态显示，含规格/码段信息
- **出入库单** — 支持导出 Excel 和打印，字段与表单配置同步

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://gitee.com/den7hon/jxc.git
cd jxc
```

### 2. 安装依赖（推荐 Python 3.12）

```bash
# 方式一：虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\activate             # Windows

pip install --upgrade pip
pip install -r requirements.txt

# 方式二：直接安装（Windows 测试环境）
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python init_database.py
```

> 首次运行会生成：数据库 `inventory.db`、2 个默认仓库、14 个示例商品、3 套表单配置、管理员账号。

### 4. 启动应用

```bash
# 开发模式（本地调试）
python app.py

# 生产模式
gunicorn -w 4 -b 127.0.0.1:5001 wsgi:application
```

访问 http://127.0.0.1:5001

### 5. 默认账号

| 角色 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| 管理员 | `admin` | `Admin@2026!` | 首次登录强制改密 |

---

## 项目文档

| 文档 | 说明 |
|------|------|
| [README.md](README.md) | 项目总览（本文档） |
| [开发指南](docs/DEVELOPMENT.md) | 二次开发文档（业务逻辑/API/开发规范） |
| [数据库设计](docs/DATABASE.md) | 数据库表结构说明 |
| [部署指南](deploy/部署指南.md) | 部署与运维说明 |
| [宝塔部署](deploy/宝塔部署指南.md) | 宝塔面板部署说明 |

## 系统要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| Python | 3.10+ | 3.12 |
| 内存 | 512 MB | 2 GB |
| 磁盘 | 1 GB | 5 GB |
| 系统 | Ubuntu 20.04 / CentOS 8 | Ubuntu 22.04 |

---

## 部署指南

### ⚠️ 部署前必读：权限问题

**宝塔面板 Python 权限问题**（必须先处理）：

| 问题 | 解决 |
|------|------|
| `/usr/bin/python3: Permission denied` | `chmod +x /usr/bin/python3.12`（宝塔安装 Python 后权限可能被重置为只读） |
| `supervisorctl: command not found` | 在宝塔【软件商店】中管理，或使用完整路径 `/www/server/panel/pyenv/bin/supervisorctl` |
| 端口占用 (Address already in use) | `fuser -k 5001/tcp` 释放端口后重启守护进程 |

---

### 🚀 方式一：一键安装脚本（推荐）

项目已内置一键安装脚本，自动处理权限问题、虚拟环境、依赖安装、数据库初始化、目录权限设置。

```bash
# 1. 克隆项目
cd /www/wwwroot/你的站点目录
git clone https://gitee.com/den7hon/jxc.git .

# 2. 赋予执行权限
chmod +x deploy/install.sh

# 3. 运行安装
bash deploy/install.sh
```

脚本会自动完成以下操作：

1. ✅ 检测并修复 `/usr/bin/python3.12 权限（宝塔常见问题）
2. ✅ 创建 Python 虚拟环境
3. ✅ 安装依赖（使用清华镜像加速）
4. ✅ 初始化数据库
5. ✅ 设置目录权限
6. ✅ 输出 Supervisor 和 Nginx 配置指引

安装完成后，按脚本提示在宝塔面板中：

- **Supervisor 配置**：添加守护进程，启动命令为脚本会完整路径
- **Nginx 配置**：添加反向代理到 127.0.0.1:5001

---

### 方式二：宝塔面板手动部署

**核心方案：Supervisor + Nginx**（Python 项目管理器已停止维护，新用户不推荐）

1. 宝塔【软件商店】→ 安装 **Nginx** + **Supervisor**
2. 【网站】→【添加站点】→ 域名 + 纯静态
3. 【终端】→ 进入站点目录 → 下载代码
4. 执行一键安装脚本（见上方方式一）
5. 在 Supervisor 中添加守护进程：

| 字段 | 内容 |
|------|------|
| 进程名称 | `inventory` |
| 运行用户 | `www` |
| 运行目录 | `/www/wwwroot/你的域名` |
| 启动命令 | `/www/wwwroot/你的域名/venv/bin/gunicorn -w 2 --threads 2 --worker-class gthread --max-requests 500 --timeout 60 -b 127.0.0.1:5001 wsgi:application` |
| 开机自启 | ✅ |

6. 【网站】→ 站点设置 → 反向代理 → 添加反向代理到 `http://127.0.0.1:5001`

---

### 方式三：本地开发环境

```bash
# Windows / Mac / Linux 本地开发
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python init_database.py
python app.py
# 访问 http://127.0.0.1:5001
```

---

### 非宝塔环境部署

详见 [deploy/部署指南.md](deploy/部署指南.md)（Systemd / Docker 两种方式）。

### 方式四：Systemd + Nginx 反向代理（推荐用于独立服务器）

仓库内 [deploy/inventory.service](deploy/inventory.service) 为可直接使用的 systemd 单元模板，
提供开机自启与崩溃自动重启。

```bash
# 1. 按实际路径修改 WorkingDirectory / ExecStart 后安装
sudo install -m 644 deploy/inventory.service /etc/systemd/system/inventory.service
sudo systemctl daemon-reload

# 2. 启用并启动（enable 即开机自启）
sudo systemctl enable --now inventory

# 3. 确认状态
systemctl status inventory
```

日常运维命令：

```bash
systemctl restart inventory     # 重启
systemctl reload inventory      # 平滑重载（改代码后用这个，不中断请求）
journalctl -u jxc -f      # 实时日志
```

要点说明：

- Gunicorn 只监听 `127.0.0.1:5001`，不直接对外暴露，公网入口交给 Nginx
- 单元文件内显式设置了 `PATH`，避免宿主机全局环境变量（如 `NODE_ENV`）干扰
- `Restart=always` + `RestartSec=5`，进程异常退出后自动拉起
- `--max-requests 500` 配合 jitter 定期回收 worker，缓解长时间运行的内存增长

Nginx 反向代理与 HTTPS 证书配置要点：

- 反代到 `http://127.0.0.1:5001`，转发 `Host` / `X-Real-IP` /
  `X-Forwarded-For` / `X-Forwarded-Proto`
- HTTP 强制跳转 HTTPS 时，需放行 `/.well-known/` 路径，否则证书自动续期会失败
- 若项目目录位于 `/root` 下，Nginx 的 `www` 用户无读取权限，
  静态文件应继续交由 Flask 提供，不要配 `alias` 直接托管
- Excel 批量导入需要放宽 `client_max_body_size`（建议 50m）

### 2H2G 低配服务器优化

详见 [deploy/宝塔部署指南.md](deploy/宝塔部署指南.md) 的 Gunicorn 参数说明与 Nginx 优化配置。

---

## 常用脚本

| 脚本 | 用途 |
|------|------|
| `python init_database.py` | 初始化数据库（首次运行） |
| `python scripts/clear_test_data.py` | 清除测试数据（保留商品/仓库/用户） |
| `python scripts/generate_full_test_data.py` | 生成完整测试数据 |
| `python scripts/strip_duplicate_page_titles.py --dry-run` | 检查模板中与顶栏重复的页内标题（仅预览） |
| `python scripts/strip_duplicate_page_titles.py` | 清除重复标题并保持按钮右对齐 |

---

## 安全说明

- **SQLite 单文件数据库** — 便于迁移与备份，可切换 MySQL（修改 `config.py` 的 `SQLALCHEMY_DATABASE_URI`）
- **密码加密** — 使用 `werkzeug.security` 存储哈希
- **CSRF 防护** — 所有 POST 表单自动校验
- **登录失败锁定** — 防暴力破解
- **操作日志** — 全量记录关键操作
- **SECRET_KEY 持久化** — 生成后写入 `.secret_key` 文件，重启不变化
- **接口限流** — `Flask-Limiter` 防止恶意请求
- **Session 安全** — HTTPOnly + Samesite，生产环境启用 Secure Cookie

---

## 时区说明（重要）

系统**强制使用中国时区（Asia/Shanghai，UTC+8）**，所有时间字段（创建时间、更新时间、
出入库时间、操作日志等）均按北京时间存储和显示，不受服务器所在时区影响。

- **代码层**：`app.py` 启动时执行 `os.environ['TZ']='Asia/Shanghai'; time.tzset()`，
  使进程内所有 `datetime.now()` 一律为北京时间，从而根治「时间显示为美国时间」问题。
- **进程层**：`/etc/systemd/system/inventory.service`（或 `deploy/inventory.service`）
  已设置 `Environment="TZ=Asia/Shanghai"`，双保险。
- **迁移注意**：只要目标服务器能解析 `Asia/Shanghai`（主流 Linux 自带
  `/usr/share/zoneinfo/Asia/Shanghai`），部署后时间即自动正确，无需手动改代码。
- **历史数据校正**：v2.2.1 提供 `scripts/fix_timezone_cst.py`，可把历史上误按 UTC
  存储的时间批量校正回北京时间（智能逐行判定，先 `--dry-run` 预览，执行前自动备份）。

```bash
python scripts/fix_timezone_cst.py --dry-run      # 预览影响
python scripts/fix_timezone_cst.py                # 实际校正（自动备份 inventory.db）
```

---

## 迁移到新服务器

本系统为单目录 + 单文件 SQLite，迁移非常轻量。以下步骤假设目标服务器已装好
Python 3.10+、Nginx（可按需加宝塔 / Supervisor）。

### 1. 在源服务器打包

```bash
cd /www/wwwroot/jxc
# 停服，保证 inventory.db 处于一致状态
sudo systemctl stop inventory
# 打包代码 + 数据库 + 密钥（不含 venv / 缓存 / 日志 / 旧备份）
tar -czf /tmp/jxc_migrate.tar.gz \
    --exclude=venv --exclude=__pycache__ --exclude=.cache \
    --exclude=logs --exclude=backups .
sudo systemctl start inventory     # 打包完立即恢复服务
```

> 数据库 `inventory.db` 和密钥 `.secret_key` 已包含在打包内，无需单独导出。

### 2. 传输到目标服务器

```bash
scp /tmp/jxc_migrate.tar.gz user@新服务器IP:/tmp/
```

### 3. 在目标服务器部署

```bash
mkdir -p /www/wwwroot/jxc && tar -xzf /tmp/jxc_migrate.tar.gz -C /www/wwwroot/jxc
cd /www/wwwroot/jxc

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 安装 systemd 服务（服务名固定为 inventory）
sudo install -m 644 deploy/inventory.service /etc/systemd/system/inventory.service
sudo systemctl daemon-reload
sudo systemctl enable --now inventory

# Nginx 反代到 127.0.0.1:5001（复用原 jxc.hons.fun 配置或新建）
```

### 4. 时区无需特殊处理

目标服务器只要时区数据完整（绝大多数 Linux 默认完整），`app.py` 与
`inventory.service` 中的 `TZ=Asia/Shanghai` 会自动保证时间为北京时间。

### 5. 验证

```bash
curl -s -o /dev/null -w "%{http_code}" https://jxc.hons.fun/   # 应返回 302
sudo journalctl -u inventory -n 20                              # 确认无报错
```

### ⚠️ 迁移易错点

- **服务名是 `inventory`，不是 `jxc`**：线上真正运行与开机自启的服务单元是
  `inventory.service`（历史命名原因）。旧文档若写 `jxc.service` 已失效，请勿照搬。
- **不要同时启用两个 service 模板**：`deploy/inventory.service` 与 `deploy/jxc.service`
  监听同一端口，同时启用会端口冲突。迁移请统一用 `inventory`。
- **备份恢复**：若想先空库初始化再恢复，把源服务器的 `inventory.db` 直接覆盖到目标
  目录同名文件即可（SQLite 单文件，停服替换最稳妥）。

---

## 依赖版本

| 包 | 版本 | 说明 |
|----|------|------|
| Flask | 3.1.3 | Web 框架 |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| SQLAlchemy | 2.0.36 | 数据库引擎 |
| Gunicorn | 23.0.0 | WSGI 服务器 |
| APScheduler | 3.11.0 | 定时任务 |
| openpyxl | 3.1.5 | Excel 处理 |
| Flask-Limiter | 3.9.2 | 限流 |
| Flask-Caching | 2.3.0 | 文件缓存 |

所有依赖均支持 Python 3.10+。

---

## 注意事项

1. 首次启动前必须运行 `python init_database.py`
2. 生产环境请立即修改默认密码
3. 定期进行数据备份（系统支持一键备份）
4. `.gitignore` 已排除 `.db`, `.secret_key`, `*.log`, `static/uploads/` 等敏感与运行时文件
5. 上传到 Git 仓库的代码不包含数据库和密钥

### 前端改动注意

修改栅格类时请注意：`static/css/modern-style.css` 自带一套栅格实现，
与所加载的 Bootstrap 构建并存。新增 `col-*` 断点类前，请先确认该类在
上述 CSS 中确有定义——若两边都缺失，类名会静默失效并被同元素上的
其它断点类接管，页面不报错但布局错乱。

### 密钥管理

`.secret_key` 用于 Flask 会话签名，**不得纳入版本控制**。

该文件虽已列入 `.gitignore`，但在项目初期就已被 git 跟踪——
`.gitignore` 对**已跟踪**文件不生效，因此它长期随仓库一同发布。
v2.2.0 已通过 `git rm --cached .secret_key` 将其移出版本控制，
并轮换了密钥。

克隆本仓库后首次运行时，`config.py` 会自动生成新的 `.secret_key`，
无需手动创建。若需主动轮换（例如怀疑泄漏）：

```bash
# 轮换后所有用户的登录态会失效，需重新登录
python -c "import secrets; open('.secret_key','w').write(secrets.token_hex(32))"
chmod 600 .secret_key
sudo systemctl restart inventory
```

> 注意：旧密钥仍存在于 git 历史中。如对安全要求较高，除轮换密钥外
> 还需考虑清理历史（`git filter-repo`），但这会重写已发布的提交。

### 定时任务与多 worker

自动备份由 APScheduler 在应用进程内调度。**多 worker 部署时需注意**：
gunicorn 每个 worker 都会执行 `create_app()`，若各自注册定时任务，
同一时刻备份会被执行多次，备份历史中会出现同一时间点的重复记录。

`deploy/jxc.service` 已通过 `--preload` 解决：`create_app()` 只在主进程
执行一次，worker 由 fork 产生，而 APScheduler 的后台线程不随 fork 复制，
因此任务只注册一份。

若不使用 `--preload`，可选以下任一方式：

```bash
# 方式一：单 worker
gunicorn --workers 1 -b 127.0.0.1:5001 wsgi:application

# 方式二：为额外进程关闭调度器
RUN_SCHEDULER=0 gunicorn --workers 4 -b 127.0.0.1:5001 wsgi:application
```

验证只注册了一份任务：

```bash
grep -c "已加载自动备份任务" logs/error.log   # 每次重启应只 +1
```

---

## 开源协议

MIT License

---

## 更新日志

### v2.2.1 (2026-08)

**时区修正（重要）**

- 强制中国时区（Asia/Shanghai）：`app.py` 启动时设置 `TZ=Asia/Shanghai` 并 `time.tzset()`，
  使进程内所有 `datetime.now()` 一律按北京时间计算，根治「记录显示为美国时间」问题
- systemd 单元 `inventory.service` 增加 `Environment="TZ=Asia/Shanghai"`，双重保险
- 新增 `scripts/fix_timezone_cst.py`：智能逐行校正历史数据中误按 UTC 存储的时间
  （先 `--dry-run` 预览，执行前自动备份 `inventory.db`）；已对存量数据完成校正（579 个字段）
- 文档同步更新：README / 部署指南新增「时区说明」「迁移到新服务器」章节
- 修正文档中过时的服务名引用（`jxc.service` 早已停用，线上实际为 `inventory.service`）

### v2.2.0 (2026-07)

**布局修复**

- **补全栅格 xl / xxl 断点** — `modern-style.css` 自实现的栅格原先只定义到 `lg`，
  而所加载的 Bootstrap 构建同样不含 `xl` 层级，导致模板中的 `col-xl-*`
  匹配不到任何规则、被同元素上的 `col-md-6`(50%) 接管。表现为仪表盘 8 个
  统计卡在宽屏下挤成 2 列 4 行，把图表挤出首屏。修复后统计卡恢复 4 列
- 同时补齐 `lg` 层级缺失的 8 / 9 / 12 列

**仪表盘与数据报表**

- 趋势图改为双 Y 轴（左入库 / 右出库）。此前入库峰值近 3000、出库仅数十，
  共用单轴时出库被压成贴底直线，无法判断走势
- 图表由 `canvas height` 属性改为定高容器，并统一设置
  `maintainAspectRatio: false`（缺此项时定高容器不生效）
- 表格长文本列（仓库名、商品名）改为单行省略 + 悬停显示全称，
  行高由 88px 降至 67px
- 出入库比率补充单位显示为「32.07 : 1」；分类占比百分比取整

**页面标题统一**

- 新增 `PAGE_TITLES` 端点映射与上下文处理器，顶栏标题按路由自动推导。
  此前 `base.html` 的 `page_title` 块默认写死"仪表盘"且仅 2 个模板覆盖了它，
  导致几乎所有页面顶栏都显示"仪表盘"
- 清除 42 个模板中与顶栏重复的页内标题。这些标题多与操作按钮同处
  `justify-content-between` 容器，故同步改为 `justify-content-end`
  以保持按钮右对齐
- 保留打印单据抬头、卡片内小节标题等非重复标题

**错误页重构**

- 新增 `static/css/error-pages.css`，改用项目既有设计令牌
  （主色 `#2563eb`、8px 网格、Inter 字体），替换原紫色渐变样式
- 支持深色模式跟随系统、`prefers-reduced-motion`、键盘焦点环
- 400 / 403 / 404 / 500 页原使用 `bi-*`(Bootstrap Icons) 图标类，
  但项目仅加载 Font Awesome，图标一直显示为空白方块，现统一为 `fa-*`
- **429 限流页修正冷却时间** — 原页面写死"10 秒后可重试"并自动刷新，
  而实际限流窗口为每分钟（登录 5/min、接口 60/min），倒计时结束后
  必然再次触发 429。现从 Flask-Limiter 异常解析真实冷却秒数，
  并写入 `Retry-After` 响应头

**数据备份**

- 补充缺失的 `templates/backup/files.html`——该模板被 `backup.files`
  路由引用但从未创建，访问 `/backup/files` 一直返回 500
- 历史记录列表由 20 条改为 10 条
- 备份统计改为数据库全量聚合。此前直接用 history 列表长度计算，
  统计范围受列表上限约束，"总备份数"名不符实

**定时备份修复**

- **修复定时任务重复注册** — gunicorn 每个 worker 都会执行 `create_app()`
  并各自注册 `daily_backup`，导致同一时刻备份被执行多次（备份历史中
  每天出现一条失败 + 一条成功的成对记录）。`deploy/jxc.service` 增加
  `--preload`，使 `create_app()` 仅在主进程执行一次；同时新增
  `RUN_SCHEDULER` 环境变量开关，供不使用 preload 的部署方式关闭额外进程的调度器
- **修复定时任务递归创建应用** — `_run_backup_with_context()` 原先在任务
  内部调用 `create_app()`，而 `create_app()` 本身又会注册定时任务并启动
  调度器，形成递归初始化。现改为使用注册时绑定的 app 实例
- 定时任务补充 `coalesce=True` / `max_instances=1` / `misfire_grace_time`，
  避免积压补跑时重复执行与并发执行
- `atexit` 关闭调度器改为容错实现，避免进程退出阶段抛异常

**部署**

- 新增 `deploy/jxc.service`（systemd 单元），支持开机自启与崩溃自动重启
- 新增 `scripts/strip_duplicate_page_titles.py`（含 `--dry-run` 预览）
- `.gitignore` 追加 `static/uploads/`（用户上传的 LOGO 属运行时数据）

### v2.1.0 (2026-06)

- **表单配置**支持实时预览与字段动态渲染
- **随货同行单**规格字段自动显示，码段信息自动补全
- **出库记录**备注自动写入批次码段信息
- **Excel 导出**按表单配置动态生成表头与字段
- 商品模型优化：生产日期/过期时间移至批次管理
- 修复表单编辑 CSRF 校验问题
- 修复导出字段代码匹配问题

### v2.0.0 (2026-05)

- 新增表单配置模块
- 新增随货同行单功能
- 优化出库单验证逻辑
- 修复库存调拨问题
- 完善操作日志记录

### v1.0.0 (2025-05)

- 初始版本发布
- 完整进销存功能
- 支持 Python 3.12
- 支持宝塔面板一键部署
