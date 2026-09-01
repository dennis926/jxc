#!/bin/bash
#===============================================================================
# HONS 进销存管理系统 - 版本升级脚本 v1.0
# 适用于已部署环境的版本更新
# 
# 功能：
#   1. 自动备份数据库和配置文件
#   2. 拉取最新代码（支持 Git 或手动上传）
#   3. 更新 Python 依赖
#   4. 自动检测并创建新表/新字段
#   5. 重启服务
#   6. 验证升级是否成功
#   7. 失败自动回滚
# 
# 用法：
#   bash deploy/update.sh              # 从 Git 拉取更新
#   bash deploy/update.sh --manual     # 手动更新模式（已上传代码）
#   bash deploy/update.sh --rollback   # 回滚到上一个版本
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

cd "$PROJECT_DIR"

# 变量
BACKUP_DIR="$REAL_PROJECT_DIR/backups/update_$(date +%Y%m%d_%H%M%S)"
UPDATE_MODE="git"  # git 或 manual
ROLLBACK_MODE=0
SKIP_BACKUP=0

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --manual)
            UPDATE_MODE="manual"
            shift
            ;;
        --rollback)
            ROLLBACK_MODE=1
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=1
            shift
            ;;
        --help)
            echo "用法: bash deploy/update.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --manual        手动更新模式（代码已上传，只执行后续步骤）"
            echo "  --rollback      回滚到上一个版本"
            echo "  --skip-backup   跳过备份（不推荐）"
            echo "  --help          显示此帮助信息"
            exit 0
            ;;
        *)
            log_warn "未知参数: $1"
            shift
            ;;
    esac
done

#-------------------------------------------------------------------------------
# 回滚模式
#-------------------------------------------------------------------------------
if [ "$ROLLBACK_MODE" = "1" ]; then
    log_step "回滚模式"
    
    # 查找最近的备份
    LATEST_BACKUP=$(ls -td "$REAL_PROJECT_DIR/backups/update_"* 2>/dev/null | head -n 1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "未找到可回滚的备份"
        exit 1
    fi
    
    log_info "找到备份: $LATEST_BACKUP"
    echo ""
    read -p "$(echo -e "${RED}确定要回滚到此版本吗？所有当前数据将丢失！[y/N]:${NC} ")" -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "取消回滚"
        exit 0
    fi
    
    # 停止服务
    log_info "停止服务..."
    if command -v systemctl &>/dev/null && sudo systemctl is-active inventory &>/dev/null; then
        sudo systemctl stop inventory
    elif command -v supervisorctl &>/dev/null && sudo supervisorctl status inventory &>/dev/null; then
        sudo supervisorctl stop inventory
    fi
    
    # 恢复数据库
    if [ -f "$LATEST_BACKUP/inventory.db" ]; then
        log_info "恢复数据库..."
        cp "$LATEST_BACKUP/inventory.db" "$REAL_PROJECT_DIR/inventory.db"
        log_success "数据库已恢复"
    fi
    
    # 恢复配置文件
    if [ -f "$LATEST_BACKUP/.secret_key" ]; then
        log_info "恢复密钥文件..."
        cp "$LATEST_BACKUP/.secret_key" "$REAL_PROJECT_DIR/.secret_key"
    fi
    
    # 恢复代码（如果备份了）
    if [ -d "$LATEST_BACKUP/code_backup" ]; then
        log_info "恢复代码..."
        rsync -av --delete "$LATEST_BACKUP/code_backup/" "$REAL_PROJECT_DIR/"
        log_success "代码已恢复"
    fi
    
    # 重启服务
    log_info "重启服务..."
    if command -v systemctl &>/dev/null; then
        sudo systemctl start inventory
    elif command -v supervisorctl &>/dev/null; then
        sudo supervisorctl start inventory
    fi
    
    log_success "回滚完成！"
    exit 0
fi

#-------------------------------------------------------------------------------
# 1. 欢迎信息
#-------------------------------------------------------------------------------
log_step "HONS 进销存管理系统 - 版本升级"
echo ""
echo -e "${YELLOW}注意：升级前请确保已备份重要数据${NC}"
echo -e "${YELLOW}升级模式: $UPDATE_MODE${NC}"
echo ""

# 检查是否为 root
if [ "$(id -u)" != "0" ]; then
    log_warn "当前用户不是 root，尝试使用 sudo..."
    if command -v sudo &>/dev/null; then
        sudo -p "请输入 sudo 密码：" echo "" || {
            log_error "sudo 验证失败，无法继续升级"
            exit 1
        }
    else
        log_error "未找到 sudo，需要以 root 用户运行"
        exit 1
    fi
fi

#-------------------------------------------------------------------------------
# 2. 检测运行环境
#-------------------------------------------------------------------------------
log_step "检测运行环境"

# 检测进程管理器
PROCESS_MANAGER="unknown"
if command -v systemctl &>/dev/null && sudo systemctl is-active inventory &>/dev/null; then
    PROCESS_MANAGER="systemd"
    log_success "检测到 Systemd 服务"
elif command -v supervisorctl &>/dev/null && sudo supervisorctl status inventory &>/dev/null; then
    PROCESS_MANAGER="supervisor"
    log_success "检测到 Supervisor 服务"
else
    log_warn "未检测到运行中的服务，尝试查找..."
    if pgrep -f "gunicorn" > /dev/null; then
        log_success "检测到 Gunicorn 进程"
    else
        log_warn "未检测到运行中的服务"
    fi
fi

# 检测虚拟环境
if [ -d "$REAL_PROJECT_DIR/venv" ]; then
    log_success "虚拟环境已存在"
    source "$REAL_PROJECT_DIR/venv/bin/activate"
else
    log_error "未找到虚拟环境，请先运行 deploy/install.sh 进行安装"
    exit 1
fi

#-------------------------------------------------------------------------------
# 3. 备份数据
#-------------------------------------------------------------------------------
if [ "$SKIP_BACKUP" = "0" ]; then
    log_step "备份数据"
    
    mkdir -p "$BACKUP_DIR"
    
    # 备份数据库
    if [ -f "$REAL_PROJECT_DIR/inventory.db" ]; then
        log_info "备份数据库..."
        cp "$REAL_PROJECT_DIR/inventory.db" "$BACKUP_DIR/inventory.db"
        log_success "数据库已备份到 $BACKUP_DIR/inventory.db"
    fi
    
    # 备份密钥文件
    if [ -f "$REAL_PROJECT_DIR/.secret_key" ]; then
        log_info "备份密钥文件..."
        cp "$REAL_PROJECT_DIR/.secret_key" "$BACKUP_DIR/.secret_key"
        log_success "密钥文件已备份"
    fi
    
    # 备份配置文件
    if [ -f "$REAL_PROJECT_DIR/config.py" ]; then
        log_info "备份配置文件..."
        cp "$REAL_PROJECT_DIR/config.py" "$BACKUP_DIR/config.py"
    fi
    
    # 备份代码（用于回滚）
    log_info "备份当前代码..."
    mkdir -p "$BACKUP_DIR/code_backup"
    rsync -av --exclude='venv' --exclude='logs' --exclude='backups' --exclude='__pycache__' \
        "$REAL_PROJECT_DIR/" "$BACKUP_DIR/code_backup/" 2>/dev/null || {
        log_warn "代码备份失败，继续升级..."
    }
    
    log_success "备份完成: $BACKUP_DIR"
else
    log_warn "跳过备份（不推荐）"
fi

#-------------------------------------------------------------------------------
# 4. 更新代码
#-------------------------------------------------------------------------------
log_step "更新代码"

if [ "$UPDATE_MODE" = "git" ]; then
    # 检测 Git
    if ! command -v git &>/dev/null; then
        log_error "未找到 Git，请使用 --manual 模式或安装 Git"
        exit 1
    fi
    
    # 保存当前版本信息
    CURRENT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    log_info "当前版本: $CURRENT_COMMIT"
    
    # 拉取最新代码
    log_info "拉取最新代码..."
    git fetch origin
    
    # 显示更新日志
    echo ""
    echo -e "${CYAN}即将更新的内容：${NC}"
    git log --oneline HEAD..origin/main 2>/dev/null || git log --oneline HEAD..origin/master 2>/dev/null || {
        log_warn "无法获取更新日志"
    }
    echo ""
    
    # 确认更新
    read -p "$(echo -e "${CYAN}确认要更新到最新版本吗？[Y/n]:${NC} ")" -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
        log_info "取消更新"
        exit 0
    fi
    
    # 执行更新
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || {
        log_error "拉取代码失败"
        log_info "尝试强制更新..."
        git fetch --all
        git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null
    }
    
    NEW_COMMIT=$(git rev-parse HEAD)
    log_success "代码已更新到: $NEW_COMMIT"
    
elif [ "$UPDATE_MODE" = "manual" ]; then
    log_info "手动更新模式"
    log_info "请确保已将最新代码上传到项目目录"
    
    read -p "$(echo -e "${CYAN}确认代码已更新，继续执行升级步骤？[Y/n]:${NC} ")" -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ -n $REPLY ]]; then
        log_info "取消更新"
        exit 0
    fi
fi

#-------------------------------------------------------------------------------
# 5. 更新依赖
#-------------------------------------------------------------------------------
log_step "更新 Python 依赖"

if [ -f "$REAL_PROJECT_DIR/requirements.txt" ]; then
    log_info "更新依赖..."
    pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install -r "$REAL_PROJECT_DIR/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    log_success "依赖更新完成"
else
    log_warn "未找到 requirements.txt"
fi

#-------------------------------------------------------------------------------
# 6. 数据库迁移
#-------------------------------------------------------------------------------
log_step "数据库迁移"

if [ -f "$REAL_PROJECT_DIR/inventory.db" ]; then
    log_info "检测数据库结构变化..."
    
    # 创建迁移脚本
    MIGRATE_SCRIPT=$(cat << 'EOF'
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db

app = create_app()

with app.app_context():
    # 使用 SQLAlchemy 的 create_all 创建新表（不会删除已有表）
    db.create_all()
    print('[数据库迁移] 新表已创建')
    
    # 检查是否有新字段需要添加（SQLite 不支持 ALTER COLUMN，需要特殊处理）
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    
    # 获取所有表名
    tables = inspector.get_table_names()
    print(f'[数据库迁移] 现有表: {tables}')
    
    # 这里可以添加自定义迁移逻辑
    # 例如：添加新字段、修改字段类型等
    
    print('[数据库迁移] 完成')
EOF
)
    
    echo "$MIGRATE_SCRIPT" > /tmp/migrate_db.py
    python /tmp/migrate_db.py
    rm -f /tmp/migrate_db.py
    
    log_success "数据库迁移完成"
else
    log_info "未找到数据库，执行初始化..."
    python "$REAL_PROJECT_DIR/init_database.py"
fi

#-------------------------------------------------------------------------------
# 7. 设置权限
#-------------------------------------------------------------------------------
log_step "设置权限"

CURRENT_USER=$(whoami)
if [ "$CURRENT_USER" = "root" ]; then
    if id "www" &>/dev/null; then
        WEB_USER="www"
    else
        WEB_USER="root"
    fi
else
    WEB_USER="$CURRENT_USER"
fi

chown -R "$WEB_USER:$WEB_USER" "$REAL_PROJECT_DIR" 2>/dev/null || {
    log_warn "无法修改目录所有者"
}
chmod -R 755 "$REAL_PROJECT_DIR/logs" "$REAL_PROJECT_DIR/backups" 2>/dev/null
chmod 644 "$REAL_PROJECT_DIR/inventory.db" 2>/dev/null

log_success "权限设置完成"

#-------------------------------------------------------------------------------
# 8. 重启服务
#-------------------------------------------------------------------------------
log_step "重启服务"

if [ "$PROCESS_MANAGER" = "systemd" ]; then
    log_info "重启 Systemd 服务..."
    sudo systemctl daemon-reload
    sudo systemctl restart inventory
    sleep 2
    
    if sudo systemctl is-active inventory &>/dev/null; then
        log_success "服务重启成功"
    else
        log_error "服务启动失败"
        log_info "查看日志: sudo journalctl -u inventory -n 50"
        
        # 提供回滚选项
        echo ""
        read -p "$(echo -e "${RED}是否回滚到上一个版本？[y/N]:${NC} ")" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            bash "$SCRIPT_DIR/update.sh" --rollback
        fi
        exit 1
    fi
    
elif [ "$PROCESS_MANAGER" = "supervisor" ]; then
    log_info "重启 Supervisor 服务..."
    sudo supervisorctl reread
    sudo supervisorctl update
    sudo supervisorctl restart inventory
    sleep 2
    
    STATUS=$(sudo supervisorctl status inventory | awk '{print $2}')
    if [ "$STATUS" = "RUNNING" ]; then
        log_success "服务重启成功"
    else
        log_error "服务启动失败"
        log_info "查看日志: tail -f $REAL_PROJECT_DIR/logs/app.log"
        
        # 提供回滚选项
        echo ""
        read -p "$(echo -e "${RED}是否回滚到上一个版本？[y/N]:${NC} ")" -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            bash "$SCRIPT_DIR/update.sh" --rollback
        fi
        exit 1
    fi
else
    log_warn "未检测到进程管理器，尝试手动启动..."
    pkill -f "gunicorn" 2>/dev/null || true
    # --preload：保证定时备份只在主进程注册一份，避免多 worker 重复执行备份
    nohup "$REAL_PROJECT_DIR/venv/bin/gunicorn" --preload -w 2 -b 127.0.0.1:5001 wsgi:application > "$REAL_PROJECT_DIR/logs/app.log" 2>&1 &
    log_success "服务已启动"
fi

#-------------------------------------------------------------------------------
# 9. 验证升级
#-------------------------------------------------------------------------------
log_step "验证升级"

sleep 3

# 测试服务是否可用
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" = "200" ] || [ "$HEALTH_STATUS" = "302" ]; then
    log_success "服务验证通过 (HTTP $HEALTH_STATUS)"
else
    log_warn "服务响应异常 (HTTP $HEALTH_STATUS)"
    log_info "请检查日志确认服务状态"
fi

#-------------------------------------------------------------------------------
# 10. 升级完成
#-------------------------------------------------------------------------------
log_step "升级完成"

echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│                    版本升级完成！                          │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────────────────┘${NC}"
echo ""

if [ "$SKIP_BACKUP" = "0" ]; then
    echo -e "${CYAN}备份位置：${NC} $BACKUP_DIR"
    echo ""
fi

echo -e "${CYAN}如果需要回滚，请执行：${NC}"
echo "  bash deploy/update.sh --rollback"
echo ""

echo -e "${CYAN}查看日志：${NC}"
if [ "$PROCESS_MANAGER" = "systemd" ]; then
    echo "  sudo journalctl -u inventory -f"
elif [ "$PROCESS_MANAGER" = "supervisor" ]; then
    echo "  tail -f $REAL_PROJECT_DIR/logs/app.log"
fi

echo ""
log_success "升级脚本执行完毕！"