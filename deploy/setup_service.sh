#!/bin/bash
#===============================================================================
# HONS 进销存管理系统 - 开机自启服务配置脚本
# 独立于安装脚本，可单独运行以配置或重新配置开机自启服务
# 
# 功能：
#   1. 检测当前进程管理器类型（Systemd/Supervisor）
#   2. 配置开机自启服务
#   3. 支持服务端口自定义
#   4. 验证服务状态
#   5. 提供服务管理命令
# 
# 用法：bash deploy/setup_service.sh [端口号]
#       bash deploy/setup_service.sh          # 使用默认端口 5001
#       bash deploy/setup_service.sh 8000     # 使用自定义端口 8000
#===============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${CYAN}===== $1 =====${NC}"; }

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REAL_PROJECT_DIR=$(readlink -f "$PROJECT_DIR")

# 默认端口
DEFAULT_PORT=5001
SERVICE_PORT=${1:-$DEFAULT_PORT}

#-------------------------------------------------------------------------------
# 1. 检查 root 权限
#-------------------------------------------------------------------------------
log_step "HONS 进销存管理系统 - 开机自启服务配置"

if [ "$(id -u)" != "0" ]; then
    log_warn "当前用户不是 root，尝试使用 sudo..."
    if command -v sudo &>/dev/null; then
        sudo -p "请输入 sudo 密码：" echo "" || {
            log_error "sudo 验证失败，无法继续"
            exit 1
        }
    else
        log_error "未找到 sudo，需要以 root 用户运行"
        exit 1
    fi
fi

#-------------------------------------------------------------------------------
# 2. 检测进程管理器
#-------------------------------------------------------------------------------
log_step "检测进程管理器"

PROCESS_MANAGER="unknown"

if command -v supervisord &>/dev/null; then
    PROCESS_MANAGER="supervisor"
    log_success "检测到 Supervisor"
elif command -v /www/server/panel/pyenv/bin/supervisorctl &>/dev/null; then
    PROCESS_MANAGER="bt_supervisor"
    log_success "检测到宝塔 Supervisor"
elif command -v systemctl &>/dev/null; then
    PROCESS_MANAGER="systemd"
    log_success "检测到 Systemd"
else
    log_error "未找到 Supervisor 或 Systemd"
    echo ""
    echo -e "${YELLOW}请安装以下任一进程管理器：${NC}"
    echo "  - Supervisor: sudo apt install supervisor"
    echo "  - Systemd: 大多数 Linux 发行版默认包含"
    exit 1
fi

#-------------------------------------------------------------------------------
# 3. 检测虚拟环境
#-------------------------------------------------------------------------------
log_step "检测虚拟环境"

if [ -d "$REAL_PROJECT_DIR/venv" ]; then
    log_success "虚拟环境已存在"
else
    log_warn "未找到虚拟环境，尝试创建..."
    
    # 查找 Python
    PYTHON_CANDIDATES=("python3.12" "python3.11" "python3.10" "python3")
    PYTHON_PATH=""
    
    for py in "${PYTHON_CANDIDATES[@]}"; do
        if command -v "$py" &>/dev/null && [ -x "$(command -v "$py")" ]; then
            PYTHON_PATH=$(command -v "$py")
            break
        fi
    done
    
    if [ -n "$PYTHON_PATH" ]; then
        "$PYTHON_PATH" -m venv "$REAL_PROJECT_DIR/venv"
        log_success "虚拟环境创建成功"
    else
        log_error "未找到可用的 Python，无法创建虚拟环境"
        exit 1
    fi
fi

#-------------------------------------------------------------------------------
# 4. 确定运行用户
#-------------------------------------------------------------------------------
CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" = "root" ]; then
    if id "www" &>/dev/null; then
        WEB_USER="www"
        WEB_GROUP="www"
    else
        WEB_USER="root"
        WEB_GROUP="root"
    fi
else
    WEB_USER="$CURRENT_USER"
    WEB_GROUP="$CURRENT_USER"
fi

log_info "运行用户: $WEB_USER"

#-------------------------------------------------------------------------------
# 5. 停止现有服务（如果存在）
#-------------------------------------------------------------------------------
log_step "停止现有服务"

if [ "$PROCESS_MANAGER" = "supervisor" ]; then
    if sudo supervisorctl status inventory &>/dev/null; then
        sudo supervisorctl stop inventory
        log_info "已停止现有 Supervisor 服务"
    fi
elif [ "$PROCESS_MANAGER" = "systemd" ]; then
    if sudo systemctl is-active inventory &>/dev/null; then
        sudo systemctl stop inventory
        log_info "已停止现有 Systemd 服务"
    fi
fi

#-------------------------------------------------------------------------------
# 6. 创建服务配置
#-------------------------------------------------------------------------------
log_step "创建服务配置"

# --preload 必须保留：create_app() 只在主进程执行一次，worker 由 fork 产生，
# APScheduler 的后台线程不随 fork 复制，因此定时备份只注册一份。
# 去掉它则每个 worker 各注册一份任务，同一秒触发会算出相同的备份中间文件名
# 并互相覆盖、截断，产生残缺的 zip。详见 deploy/jxc.service 的说明。
GUNICORN_CMD="$REAL_PROJECT_DIR/venv/bin/gunicorn --preload -w 2 --threads 2 --worker-class gthread --max-requests 500 --timeout 60 -b 127.0.0.1:$SERVICE_PORT wsgi:application"

if [ "$PROCESS_MANAGER" = "supervisor" ] || [ "$PROCESS_MANAGER" = "bt_supervisor" ]; then
    # Supervisor 配置
    SUPERVISOR_CONF="/etc/supervisor/conf.d/inventory.conf"
    
    cat > "$SUPERVISOR_CONF" << EOF
[program:inventory]
command=$GUNICORN_CMD
directory=$REAL_PROJECT_DIR
user=$WEB_USER
autostart=true
autorestart=true
startsecs=5
startretries=3
stderr_logfile=$REAL_PROJECT_DIR/logs/error.log
stdout_logfile=$REAL_PROJECT_DIR/logs/app.log
EOF
    
    log_success "Supervisor 配置文件已创建: $SUPERVISOR_CONF"
    
    # 重载配置
    sudo supervisorctl reread
    sudo supervisorctl update
    
    log_success "Supervisor 配置已重载"
    
elif [ "$PROCESS_MANAGER" = "systemd" ]; then
    # Systemd 配置
    SYSTEMD_CONF="/etc/systemd/system/inventory.service"
    
    cat > "$SYSTEMD_CONF" << EOF
[Unit]
Description=HONS 进销存管理系统
After=network.target

[Service]
User=$WEB_USER
Group=$WEB_GROUP
WorkingDirectory=$REAL_PROJECT_DIR
ExecStart=$GUNICORN_CMD
Restart=always
RestartSec=5
Environment="PATH=$REAL_PROJECT_DIR/venv/bin"

[Install]
WantedBy=multi-user.target
EOF
    
    log_success "Systemd 配置文件已创建: $SYSTEMD_CONF"
    
    # 重载配置
    sudo systemctl daemon-reload
    
    log_success "Systemd 配置已重载"
fi

#-------------------------------------------------------------------------------
# 7. 启动服务并设置开机自启
#-------------------------------------------------------------------------------
log_step "启动服务并设置开机自启"

if [ "$PROCESS_MANAGER" = "supervisor" ] || [ "$PROCESS_MANAGER" = "bt_supervisor" ]; then
    # Supervisor 启动
    sudo supervisorctl start inventory
    
    # Supervisor 默认 autostart=true 即开机自启
    
    log_success "服务已启动"
    log_info "开机自启: ✅ 已启用（autostart=true）"
    
elif [ "$PROCESS_MANAGER" = "systemd" ]; then
    # Systemd 启动
    sudo systemctl enable inventory
    sudo systemctl start inventory
    
    log_success "服务已启动"
    log_info "开机自启: ✅ 已启用（systemctl enable）"
fi

#-------------------------------------------------------------------------------
# 8. 验证服务状态
#-------------------------------------------------------------------------------
log_step "验证服务状态"

sleep 2

if [ "$PROCESS_MANAGER" = "supervisor" ] || [ "$PROCESS_MANAGER" = "bt_supervisor" ]; then
    STATUS=$(sudo supervisorctl status inventory 2>/dev/null | awk '{print $2}')
    if [ "$STATUS" = "RUNNING" ]; then
        log_success "服务运行正常"
    else
        log_warn "服务状态: $STATUS"
        log_info "查看日志: tail -f $REAL_PROJECT_DIR/logs/app.log"
    fi
    
elif [ "$PROCESS_MANAGER" = "systemd" ]; then
    STATUS=$(sudo systemctl is-active inventory 2>/dev/null)
    if [ "$STATUS" = "active" ]; then
        log_success "服务运行正常"
    else
        log_warn "服务状态: $STATUS"
        log_info "查看日志: sudo journalctl -u inventory -f"
    fi
fi

#-------------------------------------------------------------------------------
# 9. 输出配置信息
#-------------------------------------------------------------------------------
log_step "配置完成"

echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│              开机自启服务配置完成！                        │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────────────────┘${NC}"
echo ""

echo -e "${CYAN}服务信息：${NC}"
echo "┌──────────────────┬─────────────────────────────┐"
echo "│ 进程管理器       │ $PROCESS_MANAGER"
echo "├──────────────────┼─────────────────────────────┤"
echo "│ 服务端口         │ $SERVICE_PORT"
echo "├──────────────────┼─────────────────────────────┤"
echo "│ 监听地址         │ 127.0.0.1:$SERVICE_PORT"
echo "├──────────────────┼─────────────────────────────┤"
echo "│ 运行用户         │ $WEB_USER"
echo "├──────────────────┼─────────────────────────────┤"
echo "│ 项目目录         │ $REAL_PROJECT_DIR"
echo "├──────────────────┼─────────────────────────────┤"
echo "│ 开机自启         │ ✅ 已启用"
echo "└──────────────────┴─────────────────────────────┘"

echo ""
echo -e "${CYAN}服务管理命令：${NC}"
if [ "$PROCESS_MANAGER" = "supervisor" ] || [ "$PROCESS_MANAGER" = "bt_supervisor" ]; then
    echo "  启动服务:   sudo supervisorctl start inventory"
    echo "  停止服务:   sudo supervisorctl stop inventory"
    echo "  重启服务:   sudo supervisorctl restart inventory"
    echo "  查看状态:   sudo supervisorctl status inventory"
    echo "  查看日志:   tail -f $REAL_PROJECT_DIR/logs/app.log"
elif [ "$PROCESS_MANAGER" = "systemd" ]; then
    echo "  启动服务:   sudo systemctl start inventory"
    echo "  停止服务:   sudo systemctl stop inventory"
    echo "  重启服务:   sudo systemctl restart inventory"
    echo "  查看状态:   sudo systemctl status inventory"
    echo "  查看日志:   sudo journalctl -u inventory -f"
    echo "  取消自启:   sudo systemctl disable inventory"
fi

echo ""
echo -e "${CYAN}验证服务器重启后服务是否自动运行：${NC}"
echo "  1. 执行: sudo reboot"
echo "  2. 重启后执行: sudo systemctl is-active inventory"
echo "  3. 预期输出: active"

echo ""
log_success "开机自启服务配置完成！"