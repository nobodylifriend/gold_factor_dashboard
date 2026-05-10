# 阿里云 ECS Dashboard 部署设计

日期：2026-05-10

适用范围：

- `visuals/gold_macro_dashboard`
- `scripts/`
- `data/`
- 部署目标主机：`Ubuntu 24.04` on Alibaba Cloud ECS

## 目标

将当前黄金宏观 dashboard 部署为一个可公开访问的网页，同时保留现有的 Python 数据抓取与预处理链路，使 `data/` 和 `visuals/gold_macro_dashboard/data/dashboard_data.json` 可以在服务器上每日自动更新。

## 现状

当前 dashboard 是一个纯静态前端：

- 页面入口：`visuals/gold_macro_dashboard/index.html`
- 前端脚本：`visuals/gold_macro_dashboard/app.js`
- 数据文件：`visuals/gold_macro_dashboard/data/dashboard_data.json`

数据更新链路目前依赖本地 PowerShell 脚本：

- `scripts/run_daily_update.ps1`

该脚本会依次执行：

1. `python -m gold_data update`
2. `python scripts/fetch_xau_data.py`
3. `python scripts/fetch_gld_options_iv_data.py`
4. `python scripts/fetch_fx_data.py`
5. `python scripts/fetch_stock_index_data.py`
6. `python scripts/fetch_stock_volatility_data.py`
7. `python scripts/fetch_us_debt_data.py`
8. `python scripts/build_gold_macro_dashboard_data.py`

因此网页托管本身很轻，但必须把“每日更新任务”一起部署到服务器。

## 方案选择

### 方案 A：ECS + Nginx + systemd timer

优点：

- 最贴合当前仓库结构
- 静态网页与数据更新职责清晰
- 成本低，部署简单
- 不需要把数据链路重写成云函数或 Workers

缺点：

- 需要自行维护一台 Linux 服务器

### 方案 B：ECS + Docker Compose

优点：

- 环境更一致，迁移更方便

缺点：

- 当前仓库尚未容器化，首次部署复杂度更高

### 方案 C：OSS 静态网站 + ECS 同步产物

优点：

- 前端托管更轻

缺点：

- 会引入“生成产物后再同步到 OSS”的额外链路
- 对当前项目来说收益不明显

### 结论

采用 `方案 A：ECS + Nginx + systemd timer`。

## 目标架构

### 对外访问

- 用户通过域名访问 `Nginx`
- `Nginx` 直接提供 `visuals/gold_macro_dashboard/` 下的静态文件

### 服务器内更新流程

- 服务器每日定时执行一个 Linux 更新脚本
- 更新脚本在仓库根目录运行现有 Python 数据抓取流程
- 更新完成后覆盖：
  - `data/` 下各类 CSV / manifest / catalog
  - `visuals/gold_macro_dashboard/data/dashboard_data.json`

### 部署目录

建议固定为：

- 仓库目录：`/srv/gold_price_analysis`
- 日志目录：`/srv/gold_price_analysis/logs`
- 虚拟环境：`/srv/gold_price_analysis/.venv`

## 需要新增的交付物

### 1. Linux 每日更新脚本

新增一个 Bash 脚本，功能上等价于 `scripts/run_daily_update.ps1`，建议路径：

- `scripts/run_daily_update.sh`

要求：

- 使用 `set -euo pipefail`
- 自动切换到仓库根目录
- 激活虚拟环境
- 顺序执行全部更新命令
- 支持从 `.env` 读取环境变量
- 把标准输出与错误输出写入日志文件

### 2. systemd service 与 timer 模板

新增部署模板文件，建议路径：

- `deploy/systemd/gold-dashboard-update.service`
- `deploy/systemd/gold-dashboard-update.timer`

职责：

- `service` 只负责执行更新脚本
- `timer` 负责每日定时触发

建议每天北京时间凌晨或清晨执行一次，例如 `06:10 Asia/Shanghai` 对应的服务器本地时间。

### 3. Nginx 站点配置模板

新增模板文件，建议路径：

- `deploy/nginx/gold-dashboard.conf`

职责：

- 站点根目录指向 `/srv/gold_price_analysis/visuals/gold_macro_dashboard`
- 默认首页为 `index.html`
- 对静态资源开启基础缓存
- 不缓存 `data/dashboard_data.json`，避免用户看到旧数据

### 4. 部署说明文档

新增一份面向运维步骤的文档，建议路径：

- `docs/deployment/aliyun-ecs-dashboard.md`

内容包括：

- ECS 初始化
- Python 与依赖安装
- 仓库拉取
- `.env` 配置
- 手工首次运行更新脚本
- Nginx 配置与 HTTPS
- systemd timer 启用
- 常见排障命令

## 环境约束

### 操作系统

- `Ubuntu 24.04`

### 运行时

- `Python 3.12`
- `nginx`
- `git`
- `systemd`

### 密钥与环境变量

`.env` 至少应包含：

- `FRED_API_KEY`

如果部分抓数源需要代理，则不把本地固定代理地址写死在 Linux 脚本中，而是改为“按环境变量透传”：

- 有代理时由服务器环境显式提供 `HTTP_PROXY` / `HTTPS_PROXY`
- 无代理时脚本应继续可运行

原因：

- 本地开发时使用的 `127.0.0.1:4780` 不能默认假定服务器存在
- 把本地代理地址硬编码进生产脚本会导致部署后直接失败

## 数据与代码更新策略

服务器上的自动更新分为两层：

### 数据层

每日定时脚本直接更新仓库工作区中的 `data/` 和 dashboard JSON。

### 代码层

初版不做自动 `git pull`。

原因：

- 自动拉代码会把“代码变更”和“数据更新”混在同一条定时任务里
- 当依赖、配置或脚本结构变化时，自动 `git pull` 更容易把服务带入半更新状态

初版策略：

- 日常只自动更新数据
- 代码发布由人工执行：`git pull`、更新虚拟环境、手动跑一次更新脚本验证

## 日志与可观测性

更新脚本必须产生日志文件，建议按日期写入：

- `logs/daily_update_YYYY-MM-DD.log`

要求：

- 出错时保留完整 traceback
- 脚本结尾输出成功或失败状态
- systemd 可通过 `journalctl` 二次查看

## 错误处理

### 更新脚本失败

- 任一关键命令失败即退出非零状态
- 不继续执行后续步骤，避免产物部分更新

### 页面访问

- 若当天更新失败，网页继续提供上一次成功生成的静态文件
- 不因数据更新失败导致页面服务整体中断

这意味着网页服务与更新任务必须解耦：

- `Nginx` 独立运行
- 定时任务只更新磁盘上的数据文件

## 测试与验收

### 本地验收

在 Windows 本地至少需要验证：

- Linux 脚本内容与 PowerShell 脚本步骤一致
- 部署文档中的命令顺序完整
- Nginx 与 systemd 模板引用的路径一致

### 服务器验收

上线时需完成以下检查：

1. `python scripts/build_gold_macro_dashboard_data.py` 能成功生成 dashboard JSON
2. `bash scripts/run_daily_update.sh` 能手工成功执行
3. `sudo systemctl start gold-dashboard-update.service` 执行成功
4. `sudo systemctl status gold-dashboard-update.timer` 显示定时器已启用
5. Nginx 能返回 dashboard 首页
6. 页面能正常读取 `data/dashboard_data.json`

## 实现范围

本次实现包含：

- Linux 更新脚本
- Nginx 配置模板
- systemd 模板
- 阿里云 Ubuntu 24.04 部署文档

本次不包含：

- Docker 化
- 自动 `git pull`
- 自动告警
- 多机部署
- OSS/CDN 同步链路

## 风险与后续扩展

### 主要风险

- 某些抓数源在 ECS 环境下可能需要额外系统依赖或网络策略
- 若服务器无出网代理，而上游源访问受限，更新任务可能失败
- 当前仓库若缺少统一依赖文件，首次部署需要手工安装 Python 包

### 后续可扩展方向

- 增加 `requirements.txt` 或更明确的依赖锁定文件
- 为更新脚本增加失败通知
- 将静态资源前置到阿里云 CDN
- 增加健康检查页面或最近更新时间展示
