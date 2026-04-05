#!/bin/bash
# evo-skills-scheduler 安装脚本
# 支持 macOS (launchd) 和 Linux (systemd)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCHEDULER_PY="$SCRIPT_DIR/evo_skills_scheduler.py"
CLIENT_BIN="$SCRIPT_DIR/evo-skills-client"
CD_BIN="$SCRIPT_DIR/evo-skills-cd"
PYTHON3="$(which python3)"

echo "============================================"
echo "  evo-skills-scheduler 安装"
echo "============================================"
echo ""
echo "安装目录: $SCRIPT_DIR"
echo "Python:   $PYTHON3"
echo ""

if [ ! -f "$SCHEDULER_PY" ]; then
    echo "错误: 找不到 $SCHEDULER_PY"
    exit 1
fi

if [ ! -f "$CLIENT_BIN" ]; then
    echo "错误: 找不到 $CLIENT_BIN"
    exit 1
fi

if [ ! -f "$CD_BIN" ]; then
    echo "错误: 找不到 $CD_BIN"
    exit 1
fi

# 确保客户端可执行
chmod +x "$CLIENT_BIN"
chmod +x "$CD_BIN"

# ---- 安装客户端命令到 PATH ----
install_client() {
    local target_dir=""

    # 优先 ~/.local/bin（用户级，不需要 sudo）
    mkdir -p "$HOME/.local/bin"
    target_dir="$HOME/.local/bin"

    echo "[1/3] 安装客户端命令到 $target_dir/"
    ln -sf "$CLIENT_BIN" "$target_dir/evo-skills-client"
    ln -sf "$CD_BIN" "$target_dir/evo-skills-cd"

    # 检查是否在 PATH 中
    if ! echo "$PATH" | tr ':' '\n' | grep -q "^${target_dir}$"; then
        echo "  提示: $target_dir 不在 PATH 中，请添加到 shell 配置:"
        echo "    export PATH=\"$target_dir:\$PATH\""
    else
        echo "  已在 PATH 中，可直接使用 evo-skills-client / evo-skills-cd 命令"
    fi
}

# ---- macOS: launchd ----
install_launchd() {
    local plist_name="com.evo-skills.scheduler"
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="$plist_dir/$plist_name.plist"
    local log_stdout="$SCRIPT_DIR/logs/launchd-stdout.log"
    local log_stderr="$SCRIPT_DIR/logs/launchd-stderr.log"

    echo "[2/3] 安装 launchd 服务: $plist_file"

    mkdir -p "$plist_dir"
    mkdir -p "$SCRIPT_DIR/logs"

    # 如果已加载，先卸载
    launchctl list "$plist_name" &>/dev/null && launchctl unload "$plist_file" 2>/dev/null || true

    cat > "$plist_file" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>${SCHEDULER_PY}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${log_stdout}</string>
    <key>StandardErrorPath</key>
    <string>${log_stderr}</string>
</dict>
</plist>
PLIST

    echo "[3/3] 启动服务"
    launchctl load "$plist_file"

    sleep 2
    if launchctl list "$plist_name" &>/dev/null; then
        echo "  服务已启动"
    else
        echo "  警告: 服务可能未正常启动，请检查日志:"
        echo "    $log_stderr"
    fi
}

# ---- Linux: systemd ----
install_systemd() {
    local service_name="evo-skills-scheduler"
    local service_file="$HOME/.config/systemd/user/$service_name.service"

    echo "[2/3] 安装 systemd 用户服务: $service_file"

    mkdir -p "$HOME/.config/systemd/user"
    mkdir -p "$SCRIPT_DIR/logs"

    cat > "$service_file" << UNIT
[Unit]
Description=evo-skills-scheduler - 自我进化智能体调度服务
After=network.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON3} ${SCHEDULER_PY}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
UNIT

    echo "[3/3] 启动服务"
    systemctl --user daemon-reload
    systemctl --user enable "$service_name"
    systemctl --user start "$service_name"

    sleep 2
    if systemctl --user is-active "$service_name" &>/dev/null; then
        echo "  服务已启动"
    else
        echo "  警告: 服务可能未正常启动，请检查:"
        echo "    systemctl --user status $service_name"
    fi
}

# ---- 执行安装 ----
install_client

OS="$(uname -s)"
case "$OS" in
    Darwin)
        install_launchd
        ;;
    Linux)
        install_systemd
        ;;
    *)
        echo "[2/3] 不支持的操作系统: $OS"
        echo "  请手动启动: python3 $SCHEDULER_PY --daemon"
        echo "[3/3] 跳过"
        ;;
esac

echo ""
echo "============================================"
echo "  安装完成"
echo "============================================"
echo ""
echo "常用命令:"
echo "  evo-skills-client status              # 查看状态"
echo "  evo-skills-client history <agent>      # 唤醒历史"
echo "  evo-skills-client config <agent>       # 查看配置"
echo "  evo-skills-cd <role>                   # 跳转到角色目录"
echo ""
echo "启用 evo-skills-cd Tab 补全（添加到 ~/.zshrc 或 ~/.bashrc）:"
echo '  eval "$(evo-skills-cd --setup-shell)"'
echo ""
echo "服务管理 (macOS):"
echo "  launchctl list com.evo-skills.scheduler"
echo "  launchctl unload ~/Library/LaunchAgents/com.evo-skills.scheduler.plist"
echo ""
