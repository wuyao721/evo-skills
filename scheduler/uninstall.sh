#!/bin/bash
# evo-skills-scheduler 卸载脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  evo-skills-scheduler 卸载"
echo "============================================"
echo ""

OS="$(uname -s)"

# 停止服务
case "$OS" in
    Darwin)
        PLIST="$HOME/Library/LaunchAgents/com.evo-skills.scheduler.plist"
        if [ -f "$PLIST" ]; then
            echo "[1/3] 停止 launchd 服务"
            launchctl unload "$PLIST" 2>/dev/null || true
            rm -f "$PLIST"
            echo "  已卸载"
        else
            echo "[1/3] 未找到 launchd 服务，跳过"
        fi
        ;;
    Linux)
        echo "[1/3] 停止 systemd 服务"
        systemctl --user stop evo-skills-scheduler 2>/dev/null || true
        systemctl --user disable evo-skills-scheduler 2>/dev/null || true
        rm -f "$HOME/.config/systemd/user/evo-skills-scheduler.service"
        systemctl --user daemon-reload
        echo "  已卸载"
        ;;
    *)
        echo "[1/3] 尝试停止进程"
        python3 "$SCRIPT_DIR/evo_skills_scheduler.py" --stop 2>/dev/null || true
        ;;
esac

# 移除客户端链接
echo "[2/3] 移除客户端命令"
rm -f "$HOME/.local/bin/evo-skills-client" 2>/dev/null || true
rm -f "/usr/local/bin/evo-skills-client" 2>/dev/null || true
echo "  已移除"

# 清理 PID 文件
echo "[3/3] 清理 PID 文件"
rm -f "$SCRIPT_DIR/logs/scheduler.pid" 2>/dev/null || true
echo "  已清理"

echo ""
echo "卸载完成。日志和配置文件保留在: $SCRIPT_DIR/logs/ 和 $SCRIPT_DIR/configs/"
echo ""
