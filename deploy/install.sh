#!/bin/bash
#===============================================================================
# HONS 进销存管理系统 - 交互式一键部署脚本 v3.1
# 适用于 Ubuntu 18.04+ / Debian 9+ / CentOS 7+ / 宝塔面板环境
# 
# 功能：
#   1. 自动检测系统环境（操作系统、Python、Git、Nginx、Systemd/Supervisor）
#   2. 优先使用宝塔自带 Python，版本自动检测（>=3.10）
#   3. 交互式询问是否自动安装缺失环境
#   4. 创建虚拟环境、安装依赖、初始化数据库
#   5. 配置开机自启服务（优先 Systemd，回退 Supervisor）
#   6. 输出未安装的环境清单
# 
# 用法：bash deploy/install.sh
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

cd "$PROJECT_DIR"

# 状态变量
INSTALL_STATUS_SYSTEM="unknown"
INSTALL_STATUS_PYTHON="missing"
INSTALL_STATUS_GIT="missing"
INSTALL_STATUS_NGINX="missing"
INSTALL_STATUS_SUPERVISOR="missing"
INSTALL_STATUS_SYSTEMD="missing"
INSTALL_STATUS_VENV="missing"

MISSING_PYTHON=""
MISSING_GIT=""
MISSING_NGINX=""
MISSING_SUPERVISOR=""

PKG_MANAGER=""
PYTHON_PACKAGE=""
GIT_PACKAGE=""
NGINX_PACKAGE=""
SUPERVISOR_PACKAGE=""

#-------------------------------------------------------------------------------
# 1. 欢迎信息
#-------------------------------------------------------------------------------
log_step "HONS 进销存管理系统 - 交互式一键部署脚本"
echo ""
echo -e "${YELLOW}注意：此脚本需要 root 权限运行${NC}"
echo -e "${YELLOW}请确保服务器已联网，部分安装需要下载依赖${NC}"
echo ""

# 检查是否为 root
if [ "$(id -u)" != "0" ]; then
    log_warn "当前用户不是 root，尝试使用 sudo..."
    if command -v sudo &>/dev/null; then
        sudo -p "请输入 sudo 密码：" echo "" || {
            log_error "sudo 验证失败，无法继续安装"
            exit 1
        }
    else
        log_error "未找到 sudo，需要以 root 用户运行"
        exit 1
    fi
fi

#-------------------------------------------------------------------------------
# 2. 检测操作系统
#-------------------------------------------------------------------------------
log_step "检测操作系统"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME="$NAME"
    OS_VERSION="$VERSION_ID"
    
    if echo "$OS_NAME" | grep -iq "ubuntu"; then
        INSTALL_STATUS_SYSTEM="ubuntu"
        PKG_MANAGER="apt"
        PYTHON_PACKAGE="python3.12 python3.12-venv python3-pip"
        GIT_PACKAGE="git"
        NGINX_PACKAGE="nginx"
        SUPERVISOR_PACKAGE="supervisor"
    elif echo "$OS_NAME" | grep -iq "debian"; then
        INSTALL_STATUS_SYSTEM="debian"
        PKG_MANAGER="apt"
        PYTHON_PACKAGE="python3.12 python3.12-venv python3-pip"
        GIT_PACKAGE="git"
        NGINX_PACKAGE="nginx"
        SUPERVISOR_PACKAGE="supervisor"
    elif echo "$OS_NAME" | grep -iq "centos"; then
        INSTALL_STATUS_SYSTEM="centos"
        PKG_MANAGER="yum"
        PYTHON_PACKAGE="python312 python312-venv python3-pip"
        GIT_PACKAGE="git"
        NGINX_PACKAGE="nginx"
        SUPERVISOR_PACKAGE="supervisor"
    elif echo "$OS_NAME" | grep -iq "rocky" || echo "$OS_NAME" | grep -iq "almalinux"; then
        INSTALL_STATUS_SYSTEM="rhel"
        PKG_MANAGER="dnf"
        PYTHON_PACKAGE="python3.12 python3.12-venv python3-pip"
        GIT_PACKAGE="git"
        NGINX_PACKAGE="nginx"
        SUPERVISOR_PACKAGE="supervisor"
    else
        INSTALL_STATUS_SYSTEM="unknown"
        log_warn "未知操作系统：$OS_NAME，尝试通用检测"
    fi
    
    log_info "检测到：$OS_NAME $OS_VERSION"
else
    log_warn "无法检测操作系统"
fi

#-------------------------------------------------------------------------------
# 3. 检测 Python（优先检测宝塔自带 Python）
#-------------------------------------------------------------------------------
log_step "检测 Python 环境"

MIN_PYTHON_VERSION="3.10"

PYTHON_CANDIDATES=(
    "/www/server/panel/pyenv/bin/python3"
    "python3.12"
    "python3.11"
    "python3.10"
    "python3"
)

INSTALL_STATUS_PYTHON="missing"
PYTHON_PATH=""
PYTHON_VERSION=""

for py in "${PYTHON_CANDIDATES[@]}"; do
    if command -v "$py" &>/dev/null; then
        CURRENT_PY_PATH=$(command -v "$py")
        CURRENT_PY_VERSION=$($py --version 2>&1 | grep -oP '\d+\.\d+\.\d+')
        
        if [ -z "$CURRENT_PY_VERSION" ]; then
            CURRENT_PY_VERSION=$($py --version 2>&1 | grep -oP '\d+\.\d+')
        fi
        
        if [ -x "$CURRENT_PY_PATH" ]; then
            PY_MAJOR=$(echo "$CURRENT_PY_VERSION" | cut -d. -f1)
            PY_MINOR=$(echo "$CURRENT_PY_VERSION" | cut -d. -f2)
            MIN_MAJOR=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f1)
            MIN_MINOR=$(echo "$MIN_PYTHON_VERSION" | cut -d. -f2)
            
            if [ "$PY_MAJOR" -gt "$MIN_MAJOR" ] || \
               ([ "$PY_MAJOR" -eq "$MIN_MAJOR" ] && [ "$PY_MINOR" -ge "$MIN_MINOR" ]); then
                
                PYTHON_PATH="$CURRENT_PY_PATH"
                PYTHON_VERSION="$CURRENT_PY_VERSION"
                INSTALL_STATUS_PYTHON="installed"
                
                if echo "$py" | grep -q "panel/pyenv"; then
                    log_success "找到宝塔 Python: $PYTHON_PATH ($PYTHON_VERSION)"
                else
                    log_success "找到 Python: $PYTHON_PATH ($PYTHON_VERSION)"
                fi
                break
            else
                log_warn "Python 版本过低: $CURRENT_PY_PATH ($CURRENT_PY_VERSION)，需要 >= $MIN_PYTHON_VERSION"
            fi
        else
            log_warn "Python 权限异常: $CURRENT_PY_PATH"
        fi
    fi
done

if [ "$INSTALL_STATUS_PYTHON" = "missing" ]; then
    log_error "未找到可用的 Python（需要 >= $MIN_PYTHON_VERSION）"
    MISSING_PYTHON="Python $MIN_PYTHON_VERSION+"
fi

#-------------------------------------------------------------------------------
# 4. 检测 Git
#-------------------------------------------------------------------------------
log_step "检测 Git"

if command -v git &>/dev/null; then
    GIT_VERSION=$(git --version | grep -oP '\d+\.\d+\.\d+')
    INSTALL_STATUS_GIT="installed"
    log_success "找到 Git: $(command -v git) ($GIT_VERSION)"
else
    log_warn "未找到 Git"
    MISSING_GIT="Git"
fi

#-------------------------------------------------------------------------------
# 5. 检测 Nginx
#-------------------------------------------------------------------------------
log_step "检测 Nginx"

if command -v nginx &>/dev/null; then
    NGINX_VERSION=$(nginx -v 2>&1 | grep -oP '\d+\.\d+\.\d+')
    INSTALL_STATUS_NGINX="installed"
    log_success "找到 Nginx: $(command -v nginx) ($NGINX_VERSION)"
else
    log_warn "未找到 Nginx（用于反向代理，可选）"
    MISSING_NGINX="Nginx"
fi

#-------------------------------------------------------------------------------
# 6. 检测 Systemd / Supervisor（Systemd 优先，更可靠）
#-------------------------------------------------------------------------------
log_step "检测进程管理器"

SUPERVISORCTL_CMD=""
SUPERVISOR_CONF_DIR=""

# 优先检测 Systemd
if command -v systemctl &>/dev/null; then
    INSTALL_STATUS_SYSTEMD="installed"
    log_success "找到 Systemd: $(command -v systemctl)"
fi

# 检测 Supervisor
if command -v supervisord &>/dev/null; then
    SUPERVISOR_VERSION=$(supervisord -v 2>&1 | grep -oP '\d+\.\d+\.\d+')
    INSTALL_STATUS_SUPERVISOR="installed"
    SUPERVISORCTL_CMD="supervisorctl"
    if [ -d "/etc/supervisor/conf.d" ]; then
        SUPERVISOR_CONF_DIR="/etc/supervisor/conf.d"
    elif [ -d "/etc/supervisord.d" ]; then
        SUPERVISOR_CONF_DIR="/etc/supervisord.d"
    fi
    log_success "找到系统 Supervisor: $(command -v supervisord) ($SUPERVISOR_VERSION)"
    log_info "配置目录: $SUPERVISOR_CONF_DIR"

elif [ -f "/www/server/panel/pyenv/bin/supervisorctl" ]; then
    INSTALL_STATUS_SUPERVISOR="installed"
    SUPERVISORCTL_CMD="/www/server/panel/pyenv/bin/supervisorctl"
    if [ -d "/www/server/panel/vhost/supervisor" ]; then
        SUPERVISOR_CONF_DIR="/www/server/panel/vhost/supervisor"
    elif [ -d "/www/server/panel/data/supervisor" ]; then
        SUPERVISOR_CONF_DIR="/www/server/panel/data/supervisor"
    fi
    log_success "找到宝塔 Supervisor: /www/server/panel/pyenv/bin/supervisorctl"
    log_info "配置目录: $SUPERVISOR_CONF_DIR"
fi

if [ "$INSTALL_STATUS_SYSTEMD" != "installed" ] && [ "$INSTALL_STATUS_SUPERVISOR" != "installed" ]; then
    log_warn "未找到 Systemd 或 Supervisor（用于进程守护）"
    MISSING_SUPERVISOR="Systemd 或 Supervisor"
fi

#-------------------------------------------------------------------------------
# 7. 环境检测汇总与交互式安装
#-------------------------------------------------------------------------------
log_step "环境检测汇总"

echo ""
echo -e "${CYAN}当前环境状态：${NC}"
printf "┌%-18s┬%-31s┐\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "项目目录" "$PROJECT_DIR"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "操作系统" "$INSTALL_STATUS_SYSTEM"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Python" "$INSTALL_STATUS_PYTHON"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Git" "$INSTALL_STATUS_GIT"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Nginx" "$INSTALL_STATUS_NGINX"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Supervisor/Systemd" "$INSTALL_STATUS_SUPERVISOR"
printf "└%-18s┴%-31s┘\n" "------------------" "-------------------------------"

# 检查是否有缺失的包
HAS_MISSING=0
[ -n "$MISSING_PYTHON" ] && HAS_MISSING=1
[ -n "$MISSING_GIT" ] && HAS_MISSING=1
[ -n "$MISSING_NGINX" ] && HAS_MISSING=1
[ -n "$MISSING_SUPERVISOR" ] && HAS_MISSING=1

if [ "$HAS_MISSING" = "1" ]; then
    echo ""
    echo -e "${YELLOW}以下环境需要安装：${NC}"
    [ -n "$MISSING_PYTHON" ] && echo "  - $MISSING_PYTHON"
    [ -n "$MISSING_GIT" ] && echo "  - $MISSING_GIT"
    [ -n "$MISSING_NGINX" ] && echo "  - $MISSING_NGINX"
    [ -n "$MISSING_SUPERVISOR" ] && echo "  - $MISSING_SUPERVISOR"
    
    echo ""
    echo -e "${CYAN}是否自动安装以上缺失环境？[Y/n]:${NC}"
    read -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        log_step "开始安装缺失环境"
        
        # 更新包管理器
        if [ "$PKG_MANAGER" = "apt" ]; then
            log_info "更新 apt 源..."
            apt update -y
        elif [ "$PKG_MANAGER" = "yum" ]; then
            log_info "更新 yum 源..."
            yum update -y
        elif [ "$PKG_MANAGER" = "dnf" ]; then
            log_info "更新 dnf 源..."
            dnf update -y
        fi
        
        # 安装 Python
        if [ "$INSTALL_STATUS_PYTHON" = "missing" ] && [ -n "$PYTHON_PACKAGE" ]; then
            log_info "安装 Python..."
            if [ "$PKG_MANAGER" = "apt" ]; then
                apt install software-properties-common -y
                add-apt-repository ppa:deadsnakes/ppa -y
                apt update -y
            fi
            $PKG_MANAGER install $PYTHON_PACKAGE -y
            INSTALL_STATUS_PYTHON="installed"
            
            # 修复权限
            for py in "${PYTHON_CANDIDATES[@]}"; do
                if [ -f "/usr/bin/$py" ]; then
                    chmod +x "/usr/bin/$py"
                fi
            done
            log_success "Python 安装完成"
        fi
        
        # 安装 Git
        if [ "$INSTALL_STATUS_GIT" = "missing" ] && [ -n "$GIT_PACKAGE" ]; then
            log_info "安装 Git..."
            $PKG_MANAGER install $GIT_PACKAGE -y
            INSTALL_STATUS_GIT="installed"
            log_success "Git 安装完成"
        fi
        
        # 安装 Nginx
        if [ "$INSTALL_STATUS_NGINX" = "missing" ] && [ -n "$NGINX_PACKAGE" ]; then
            log_info "安装 Nginx..."
            $PKG_MANAGER install $NGINX_PACKAGE -y
            INSTALL_STATUS_NGINX="installed"
            log_success "Nginx 安装完成"
        fi
        
        # 安装 Supervisor
        if [ "$INSTALL_STATUS_SUPERVISOR" = "missing" ] && [ -n "$SUPERVISOR_PACKAGE" ]; then
            log_info "安装 Supervisor..."
            $PKG_MANAGER install $SUPERVISOR_PACKAGE -y
            INSTALL_STATUS_SUPERVISOR="installed"
            log_success "Supervisor 安装完成"
        fi
    else
        log_warn "跳过环境安装，请确保手动安装后再继续"
    fi
else
    log_success "所有环境已就绪"
fi

#-------------------------------------------------------------------------------
# 8. 创建虚拟环境（处理 ensurepip 缺失问题）
#-------------------------------------------------------------------------------
log_step "创建虚拟环境"

if [ "$INSTALL_STATUS_PYTHON" = "installed" ]; then
    VENV_ACTIVATE="$PROJECT_DIR/venv/bin/activate"
    
    if [ -d "$PROJECT_DIR/venv" ] && [ -f "$VENV_ACTIVATE" ]; then
        log_warn "虚拟环境已存在，跳过创建"
        INSTALL_STATUS_VENV="exists"
    else
        if [ -d "$PROJECT_DIR/venv" ] && [ ! -f "$VENV_ACTIVATE" ]; then
            log_warn "虚拟环境目录存在但不完整，删除后重新创建"
            rm -rf "$PROJECT_DIR/venv"
        fi
        
        log_info "创建虚拟环境..."
        
        if ! "$PYTHON_PATH" -m venv "$PROJECT_DIR/venv" 2>&1; then
            log_warn "虚拟环境创建失败，可能缺少 ensurepip/venv 模块"
            
            if [ "$PKG_MANAGER" = "apt" ]; then
                PY_VENV_PACKAGE="python3-venv"
                if echo "$PYTHON_VERSION" | grep -q "^3\.12"; then
                    PY_VENV_PACKAGE="python3.12-venv"
                elif echo "$PYTHON_VERSION" | grep -q "^3\.11"; then
                    PY_VENV_PACKAGE="python3.11-venv"
                elif echo "$PYTHON_VERSION" | grep -q "^3\.10"; then
                    PY_VENV_PACKAGE="python3.10-venv"
                fi
                
                log_info "尝试安装 $PY_VENV_PACKAGE..."
                apt install "$PY_VENV_PACKAGE" -y
                
                log_info "重新创建虚拟环境..."
                "$PYTHON_PATH" -m venv "$PROJECT_DIR/venv"
            else
                log_error "无法自动安装 venv 模块，请手动安装后重试"
                exit 1
            fi
        fi
        
        if [ ! -f "$VENV_ACTIVATE" ]; then
            log_error "虚拟环境创建失败，请检查 Python 环境"
            exit 1
        fi
        
        INSTALL_STATUS_VENV="created"
        log_success "虚拟环境创建成功"
    fi
    
    source "$VENV_ACTIVATE"
    log_info "虚拟环境已激活"
else
    log_error "Python 未安装，无法创建虚拟环境"
    MISSING_PYTHON="Python $MIN_PYTHON_VERSION+"
fi

#-------------------------------------------------------------------------------
# 9. 安装依赖
#-------------------------------------------------------------------------------
log_step "安装 Python 依赖"

if [ "$INSTALL_STATUS_VENV" != "missing" ] && [ "$INSTALL_STATUS_PYTHON" = "installed" ]; then
    log_info "升级 pip..."
    pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        log_info "安装项目依赖..."
        pip install -r "$PROJECT_DIR/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
        log_success "依赖安装完成"
    else
        log_error "未找到 requirements.txt"
        exit 1
    fi
else
    log_warn "跳过依赖安装（Python 或虚拟环境未就绪）"
fi

#-------------------------------------------------------------------------------
# 10. 初始化数据库
#-------------------------------------------------------------------------------
log_step "初始化数据库"

if [ "$INSTALL_STATUS_VENV" != "missing" ] && [ "$INSTALL_STATUS_PYTHON" = "installed" ]; then
    if [ -f "$PROJECT_DIR/inventory.db" ]; then
        log_warn "数据库已存在，跳过初始化"
        log_warn "如需重新初始化，请先删除 inventory.db"
    else
        log_info "初始化数据库..."
        python "$PROJECT_DIR/init_database.py"
        log_success "数据库初始化完成"
    fi
else
    log_warn "跳过数据库初始化（Python 或虚拟环境未就绪）"
fi

#-------------------------------------------------------------------------------
# 11. 设置目录权限
#-------------------------------------------------------------------------------
log_step "设置目录权限"

# 确定运行用户
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

log_info "设置权限: 用户=$WEB_USER, 组=$WEB_GROUP"

# 创建必要目录
for dir in logs backups static uploads; do
    mkdir -p "$PROJECT_DIR/$dir"
done

# 设置权限
chown -R "$WEB_USER:$WEB_GROUP" "$PROJECT_DIR" 2>/dev/null || {
    log_warn "无法修改目录所有者，使用当前用户权限"
}
chmod -R 755 "$PROJECT_DIR/logs" "$PROJECT_DIR/backups" 2>/dev/null
chmod 644 "$PROJECT_DIR/inventory.db" 2>/dev/null

log_success "目录权限设置完成"

#-------------------------------------------------------------------------------
# 12. 配置开机自启服务
#-------------------------------------------------------------------------------
log_step "配置开机自启服务"

if [ "$INSTALL_STATUS_SYSTEMD" = "installed" ] || [ "$INSTALL_STATUS_SUPERVISOR" = "installed" ]; then
    DEFAULT_PORT=5001
    echo -e "${CYAN}请输入服务端口 [默认 $DEFAULT_PORT]:${NC}"
    read -r
    SERVICE_PORT=${REPLY:-$DEFAULT_PORT}
    
    REAL_PROJECT_DIR=$(readlink -f "$PROJECT_DIR")
    
    # 优先使用 Systemd（更可靠）
    if [ "$INSTALL_STATUS_SYSTEMD" = "installed" ]; then
        log_info "配置 Systemd 服务..."
        
        SYSTEMD_CONF="/etc/systemd/system/inventory.service"
        cat > "$SYSTEMD_CONF" << EOF
[Unit]
Description=HONS 进销存管理系统
After=network.target

[Service]
User=$WEB_USER
Group=$WEB_GROUP
WorkingDirectory=$REAL_PROJECT_DIR
# --preload 必须保留：create_app() 只在主进程执行一次，worker 由 fork 产生，
# APScheduler 的后台线程不随 fork 复制，因此定时备份只注册一份。
# 去掉它则每个 worker 各注册一份任务，同一秒触发会算出相同的备份中间文件名
# 并互相覆盖、截断，产生残缺的 zip 和 "No such file or directory" 失败记录。
# 详见 deploy/jxc.service 的说明。
ExecStart=$REAL_PROJECT_DIR/venv/bin/gunicorn --preload -w 2 --threads 2 --worker-class gthread --max-requests 500 --timeout 60 -b 127.0.0.1:$SERVICE_PORT wsgi:application
Restart=always
RestartSec=5
Environment="PATH=$REAL_PROJECT_DIR/venv/bin"

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        systemctl enable inventory
        systemctl start inventory
        
        sleep 2
        STATUS=$(systemctl is-active inventory 2>/dev/null)
        if [ "$STATUS" = "active" ]; then
            log_success "Systemd 服务配置完成，运行正常"
            log_info "服务已启动，监听 127.0.0.1:$SERVICE_PORT"
            log_info "管理命令: systemctl start|stop|restart|status inventory"
        else
            log_warn "Systemd 服务状态: $STATUS，请检查日志"
            log_info "查看日志: journalctl -u inventory -f"
        fi
        
    elif [ "$INSTALL_STATUS_SUPERVISOR" = "installed" ]; then
        log_info "配置 Supervisor 服务..."
        
        if [ -n "$SUPERVISOR_CONF_DIR" ]; then
            SUPERVISOR_CONF="$SUPERVISOR_CONF_DIR/inventory.conf"
        else
            SUPERVISOR_CONF="/etc/supervisor/conf.d/inventory.conf"
        fi
        mkdir -p "$(dirname "$SUPERVISOR_CONF")"
        cat > "$SUPERVISOR_CONF" << EOF
[program:inventory]
; --preload 必须保留：create_app() 只在主进程执行一次，定时备份只注册一份。
; 去掉它则每个 worker 各注册一份任务，同一秒触发会产生残缺备份包。
command=$REAL_PROJECT_DIR/venv/bin/gunicorn --preload -w 2 --threads 2 --worker-class gthread --max-requests 500 --timeout 60 -b 127.0.0.1:$SERVICE_PORT wsgi:application
directory=$REAL_PROJECT_DIR
user=$WEB_USER
autostart=true
autorestart=true
startsecs=5
startretries=3
stderr_logfile=$REAL_PROJECT_DIR/logs/error.log
stdout_logfile=$REAL_PROJECT_DIR/logs/app.log
EOF
        
        $SUPERVISORCTL_CMD reread
        $SUPERVISORCTL_CMD update
        $SUPERVISORCTL_CMD start inventory
        
        sleep 2
        STATUS=$($SUPERVISORCTL_CMD status inventory 2>/dev/null | awk '{print $2}')
        if [ "$STATUS" = "RUNNING" ]; then
            log_success "Supervisor 服务配置完成，运行正常"
            log_info "服务已启动，监听 127.0.0.1:$SERVICE_PORT"
        else
            log_warn "Supervisor 服务状态: $STATUS，请检查日志"
        fi
    fi
else
    log_warn "未配置开机自启服务（缺少 Systemd 或 Supervisor）"
    MISSING_SUPERVISOR="Systemd 或 Supervisor"
fi

#-------------------------------------------------------------------------------
# 13. Nginx 反向代理配置
#-------------------------------------------------------------------------------
log_step "配置 Nginx 反向代理"

if [ "$INSTALL_STATUS_NGINX" = "installed" ]; then
    echo -e "${CYAN}请输入域名（如 your-domain.com，留空跳过）:${NC}"
    read -r
    DOMAIN=${REPLY:-}
    
    if [ -n "$DOMAIN" ]; then
        log_info "配置 Nginx 反向代理..."
        
        NGINX_CONF="/etc/nginx/sites-available/inventory"
        mkdir -p "$(dirname "$NGINX_CONF")"
        cat > "$NGINX_CONF" << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    access_log $REAL_PROJECT_DIR/logs/nginx_access.log;
    error_log $REAL_PROJECT_DIR/logs/nginx_error.log;
    
    client_max_body_size 50M;
    
    location /static/ {
        alias $REAL_PROJECT_DIR/static/;
        expires 30d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:$SERVICE_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
        
        # 创建软链接
        if [ -f "/etc/nginx/sites-enabled/inventory" ]; then
            rm "/etc/nginx/sites-enabled/inventory"
        fi
        ln -s "/etc/nginx/sites-available/inventory" "/etc/nginx/sites-enabled/inventory"
        
        # 测试并重启
        nginx -t && nginx -s reload
        
        log_success "Nginx 配置完成"
        log_info "访问地址: http://$DOMAIN"
    else
        log_warn "跳过 Nginx 配置"
    fi
else
    log_warn "跳过 Nginx 配置（Nginx 未安装）"
fi

#-------------------------------------------------------------------------------
# 14. 安装完成汇总
#-------------------------------------------------------------------------------
log_step "安装完成"

echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│                    安装完成！                              │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────────────────┘${NC}"
echo ""

# 输出安装状态
echo -e "${CYAN}安装状态汇总：${NC}"
printf "┌%-18s┬%-31s┐\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "项目目录" "$REAL_PROJECT_DIR"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Python" "$INSTALL_STATUS_PYTHON"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "虚拟环境" "$INSTALL_STATUS_VENV"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "数据库" "已初始化"
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
if [ "$INSTALL_STATUS_SYSTEMD" = "installed" ]; then
    printf "│ %-16s │ %-29s │\n" "开机自启" "Systemd"
elif [ "$INSTALL_STATUS_SUPERVISOR" = "installed" ]; then
    printf "│ %-16s │ %-29s │\n" "开机自启" "Supervisor"
else
    printf "│ %-16s │ %-29s │\n" "开机自启" "未配置"
fi
printf "├%-18s┼%-31s┤\n" "------------------" "-------------------------------"
printf "│ %-16s │ %-29s │\n" "Nginx" "$INSTALL_STATUS_NGINX"
printf "└%-18s┴%-31s┘\n" "------------------" "-------------------------------"

# 输出访问信息
echo ""
echo -e "${CYAN}访问信息：${NC}"
echo "  默认账号: admin"
echo "  默认密码: Admin@2026!"
echo "  本地访问: http://127.0.0.1:$SERVICE_PORT"
if [ -n "$DOMAIN" ]; then
    echo "  外网访问: http://$DOMAIN"
fi

# 输出未安装的环境
HAS_MISSING=0
[ -n "$MISSING_PYTHON" ] && HAS_MISSING=1
[ -n "$MISSING_GIT" ] && HAS_MISSING=1
[ -n "$MISSING_NGINX" ] && HAS_MISSING=1
[ -n "$MISSING_SUPERVISOR" ] && HAS_MISSING=1

if [ "$HAS_MISSING" = "1" ]; then
    echo ""
    echo -e "${YELLOW}未安装的环境（需要手动安装）：${NC}"
    [ -n "$MISSING_PYTHON" ] && echo "  - $MISSING_PYTHON"
    [ -n "$MISSING_GIT" ] && echo "  - $MISSING_GIT"
    [ -n "$MISSING_NGINX" ] && echo "  - $MISSING_NGINX"
    [ -n "$MISSING_SUPERVISOR" ] && echo "  - $MISSING_SUPERVISOR"
    echo ""
    echo -e "${YELLOW}安装命令参考：${NC}"
    if [ "$PKG_MANAGER" = "apt" ]; then
        echo "  apt install python3.12 python3.12-venv python3-pip git nginx supervisor"
    elif [ "$PKG_MANAGER" = "yum" ]; then
        echo "  yum install python312 python312-venv python3-pip git nginx supervisor"
    elif [ "$PKG_MANAGER" = "dnf" ]; then
        echo "  dnf install python3.12 python3.12-venv python3-pip git nginx supervisor"
    fi
fi

echo ""
echo -e "${CYAN}常用命令：${NC}"
if [ "$INSTALL_STATUS_SYSTEMD" = "installed" ]; then
    echo "  查看状态: systemctl status inventory"
    echo "  启动服务: systemctl start inventory"
    echo "  停止服务: systemctl stop inventory"
    echo "  重启服务: systemctl restart inventory"
    echo "  查看日志: journalctl -u inventory -f 或 tail -f $REAL_PROJECT_DIR/logs/app.log"
elif [ "$INSTALL_STATUS_SUPERVISOR" = "installed" ]; then
    echo "  查看状态: $SUPERVISORCTL_CMD status inventory"
    echo "  重启服务: $SUPERVISORCTL_CMD restart inventory"
    echo "  查看日志: tail -f $REAL_PROJECT_DIR/logs/app.log"
fi
echo ""

log_success "一键部署脚本执行完毕！"