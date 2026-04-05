#!/usr/bin/env python3
"""
evo-skills-scheduler — 轻量级技能调度服务

纯 Python 标准库实现，无第三方依赖。
功能：读取 configs/*.yaml，按 cron 表达式调度 agent 命令执行。
"""

import sys
import os
import time
import json
import signal
import subprocess
import threading
import shutil
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ────────────────────────────────────────
# 路径常量（相对于脚本所在目录）
# ────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = BASE_DIR / "configs"
LOGS_DIR = BASE_DIR / "logs"
PID_FILE = LOGS_DIR / "scheduler.pid"
STATE_FILE = BASE_DIR / "state.json"
SCHEDULER_LOG = LOGS_DIR / "scheduler.log"

# ────────────────────────────────────────
# 全局状态
# ────────────────────────────────────────
shutdown_event = threading.Event()
running_agents: dict = {}          # agent_name -> {thread, command, start_time}
running_agents_lock = threading.Lock()
state_lock = threading.Lock()
http_server = None                 # HTTP server 实例
scheduler_start_time = None        # scheduler 启动时间


# ============================================================
# 1. HTTP API Server
# ============================================================

class SchedulerAPIHandler(BaseHTTPRequestHandler):
    """处理 scheduler HTTP API 请求"""

    def log_message(self, format, *args):
        """禁用默认的访问日志（避免污染 stderr）"""
        pass

    def send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        """处理 GET 请求"""
        path = urlparse(self.path).path

        if path == "/ping":
            # 健康检查
            uptime = 0
            if scheduler_start_time:
                uptime = (datetime.now() - scheduler_start_time).total_seconds()
            self.send_json({
                "status": "ok",
                "pid": os.getpid(),
                "uptime": uptime,
                "version": "1.0.0"
            })

        elif path == "/status":
            # 返回所有 agent 的实时状态
            with state_lock:
                state = load_state()
                agents = state.get("agents", {})

            # 增强实时信息：检查 running_agents
            with running_agents_lock:
                for agent_name, info in running_agents.items():
                    if agent_name in agents:
                        elapsed = (datetime.now() - info["start_time"]).total_seconds()
                        agents[agent_name]["running_elapsed"] = elapsed

            self.send_json({
                "scheduler": {
                    "pid": os.getpid(),
                    "started_at": state.get("started_at"),
                    "uptime": (datetime.now() - scheduler_start_time).total_seconds() if scheduler_start_time else 0
                },
                "agents": agents
            })

        else:
            self.send_json({"error": "Not Found"}, 404)


def start_http_server() -> int:
    """启动 HTTP server，返回端口号"""
    global http_server

    # 在随机端口启动（避免冲突）
    http_server = HTTPServer(("127.0.0.1", 0), SchedulerAPIHandler)
    port = http_server.server_address[1]

    # 在后台线程运行
    thread = threading.Thread(target=http_server.serve_forever, daemon=True, name="http-server")
    thread.start()

    return port


def stop_http_server():
    """停止 HTTP server"""
    global http_server
    if http_server:
        http_server.shutdown()
        http_server = None


# ============================================================
# 2. 简易 YAML 解析器（仅支持本项目所需的子集格式）
# ============================================================

def parse_simple_yaml(text: str) -> dict:
    """
    解析简单 YAML 格式。支持：
    - 顶级 key: value
    - 嵌套对象（通过缩进）
    - 列表项（- 开头）
    - 带引号的字符串值
    不依赖 PyYAML。
    """
    lines = text.splitlines()
    return _parse_yaml_lines(lines, 0, 0)[0]


def _get_indent(line: str) -> int:
    """返回行首空格数"""
    return len(line) - len(line.lstrip(" "))


def _strip_value(val: str) -> str:
    """去除值的前后空白和引号"""
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        return val[1:-1]
    return val


def _parse_yaml_lines(lines: list, start: int, base_indent: int) -> tuple:
    """
    递归解析 YAML 行。
    返回 (result_dict_or_list, 下一行索引)。
    """
    result = {}
    i = start

    while i < len(lines):
        raw = lines[i]

        # 跳过空行和注释
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = _get_indent(raw)

        # 缩进回退 → 返回上层
        if indent < base_indent:
            break

        # 如果是列表项
        if stripped.startswith("- "):
            lst, i = _parse_yaml_list(lines, i, indent)
            return lst, i

        # key: value 形式
        if ":" in stripped:
            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            after_colon = stripped[colon_pos + 1:].strip()

            if after_colon:
                # 同行有值
                result[key] = _strip_value(after_colon)
                i += 1
            else:
                # 值在下面的缩进块
                # 先看下一非空行的缩进来决定是 dict 还是 list
                j = i + 1
                while j < len(lines):
                    ns = lines[j].strip()
                    if ns and not ns.startswith("#"):
                        break
                    j += 1

                if j < len(lines):
                    next_indent = _get_indent(lines[j])
                    if next_indent > indent:
                        child, i = _parse_yaml_lines(lines, j, next_indent)
                        result[key] = child
                    else:
                        result[key] = ""
                        i += 1
                else:
                    result[key] = ""
                    i += 1
        else:
            i += 1

    return result, i


def _parse_yaml_list(lines: list, start: int, base_indent: int) -> tuple:
    """解析 YAML 列表（- 开头的项）"""
    result = []
    i = start

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = _get_indent(raw)
        if indent < base_indent:
            break

        if indent == base_indent and stripped.startswith("- "):
            # 提取 - 后面的内容
            item_content = stripped[2:].strip()

            # 引号包裹的值视为简单字符串（不解析内部冒号）
            is_quoted = (len(item_content) >= 2
                         and item_content[0] == item_content[-1]
                         and item_content[0] in ('"', "'"))

            if not is_quoted and ":" in item_content:
                # 这一项本身就是 key: value，可能还有后续缩进行
                # 构造一个临时块来解析
                item_lines = [" " * (base_indent + 2) + item_content]
                j = i + 1
                while j < len(lines):
                    ns = lines[j].strip()
                    nindent = _get_indent(lines[j])
                    if not ns or ns.startswith("#"):
                        j += 1
                        continue
                    if nindent > base_indent:
                        item_lines.append(lines[j])
                        j += 1
                    else:
                        break
                child, _ = _parse_yaml_lines(item_lines, 0, base_indent + 2)
                result.append(child)
                i = j
            else:
                result.append(_strip_value(item_content))
                i += 1
        else:
            break

    return result, i


# ============================================================
# 2. Cron 表达式解析与匹配
# ============================================================

def _parse_cron_field(field: str, min_val: int, max_val: int) -> set:
    """
    解析单个 cron 字段，返回匹配的值集合。
    支持：* / 具体数字 / 1-5 范围 / */5 间隔 / 逗号分隔
    """
    values = set()

    for part in field.split(","):
        part = part.strip()

        if part == "*":
            values.update(range(min_val, max_val + 1))

        elif part.startswith("*/"):
            # 间隔表达式，如 */5
            step = int(part[2:])
            values.update(range(min_val, max_val + 1, step))

        elif "-" in part and "/" in part:
            # 范围+步进，如 1-30/5
            range_part, step_str = part.split("/")
            lo, hi = range_part.split("-")
            step = int(step_str)
            values.update(range(int(lo), int(hi) + 1, step))

        elif "-" in part:
            # 范围，如 1-5
            lo, hi = part.split("-")
            values.update(range(int(lo), int(hi) + 1))

        else:
            # 具体数字
            values.add(int(part))

    return values


class CronExpr:
    """解析并匹配 5 段标准 cron 表达式：分 时 日 月 周几"""

    def __init__(self, expr: str):
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron 表达式必须有 5 段，实际: {expr!r}")

        self.minutes = _parse_cron_field(parts[0], 0, 59)
        self.hours = _parse_cron_field(parts[1], 0, 23)
        self.days = _parse_cron_field(parts[2], 1, 31)
        self.months = _parse_cron_field(parts[3], 1, 12)
        self.weekdays = _parse_cron_field(parts[4], 0, 6)  # 0=周日

    def matches(self, dt: datetime) -> bool:
        """检查给定时间是否匹配此 cron 表达式"""
        # isoweekday(): 1=周一…7=周日，转为 cron 的 0=周日
        weekday = dt.isoweekday() % 7
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.days
            and dt.month in self.months
            and weekday in self.weekdays
        )


# ============================================================
# 3. 日志工具
# ============================================================

def log_scheduler(level: str, agent_cmd: str, detail: str):
    """写入 scheduler.log，格式：[YYYY-MM-DD HH:MM:SS] LEVEL  agent/command | 详情"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level:<6} {agent_cmd} | {detail}\n"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULER_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def write_detail_log(agent_name: str, command: str, executor: str,
                     start_time: datetime, end_time: datetime,
                     returncode: int, stdout: str, stderr: str,
                     cmd_line: list = None):
    """写详细日志到 logs/<agent-name>/YYYY-MM-DD-HHMMSS.log"""
    agent_log_dir = LOGS_DIR / agent_name
    agent_log_dir.mkdir(parents=True, exist_ok=True)
    filename = start_time.strftime("%Y-%m-%d-%H%M%S") + ".log"
    filepath = agent_log_dir / filename

    duration = (end_time - start_time).total_seconds()
    cmd_str = " ".join(cmd_line) if cmd_line else "(unknown)"
    content = (
        f"Agent:     {agent_name}\n"
        f"Command:   {command}\n"
        f"Executor:  {executor}\n"
        f"CLI:       {cmd_str}\n"
        f"Started:   {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Ended:     {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Duration:  {duration:.1f}s\n"
        f"Exit Code: {returncode}\n"
        f"{'=' * 60}\n"
        f"STDOUT:\n{stdout}\n"
        f"{'=' * 60}\n"
        f"STDERR:\n{stderr}\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================
# 4. state.json 管理
# ============================================================

def load_state() -> dict:
    """加载已有的 state.json，不存在则返回空结构"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_state(state: dict):
    """原子写入 state.json"""
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(STATE_FILE)


def init_state(http_port: int = None) -> dict:
    """初始化 state.json 顶层结构"""
    state = load_state()
    state["pid"] = os.getpid()
    state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if http_port:
        state["http_port"] = http_port
    state.setdefault("agents", {})
    save_state(state)
    return state


def update_agent_state(agent_name: str, **kwargs):
    """线程安全地更新某个 agent 在 state.json 中的状态"""
    with state_lock:
        state = load_state()
        agents = state.setdefault("agents", {})
        agent = agents.setdefault(agent_name, {})
        agent.update(kwargs)
        save_state(state)


# ============================================================
# 5. 进程锁（PID 文件）
# ============================================================

def acquire_pid_lock() -> bool:
    """
    尝试获取进程锁。
    如果已有进程在运行，返回 False；否则写入当前 PID 并返回 True。
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            # 检查进程是否仍在运行
            os.kill(old_pid, 0)
            # 没有抛异常说明进程还在
            return False
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            # PID 无效或进程已不存在，清理旧文件
            PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))
    return True


def release_pid_lock():
    """删除 PID 文件"""
    PID_FILE.unlink(missing_ok=True)


# ============================================================
# 6. 配置加载
# ============================================================

# executor 常见安装路径（launchd/systemd 环境 PATH 受限时 fallback）
_EXECUTOR_SEARCH_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.npm-global/bin"),
    os.path.expanduser("~/.cargo/bin"),
]


def resolve_executor(name: str) -> str:
    """将 executor 名字解析为绝对路径。"""
    # 已经是绝对路径
    if os.path.isabs(name) and os.path.isfile(name):
        return name
    # 尝试 shutil.which（当前 PATH）
    found = shutil.which(name)
    if found:
        return found
    # 尝试常见路径
    for d in _EXECUTOR_SEARCH_PATHS:
        candidate = os.path.join(d, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    # 找不到就原样返回，运行时报错
    return name


def get_executor_kind(executor: str) -> str:
    """根据执行器路径或名称推断执行器类型。"""
    return Path(executor).stem.lower()


def build_agent_prompt(agent_name: str, command: str) -> str:
    """统一构造调度器传给执行器的 prompt。"""
    return f"/{agent_name} {command}"


def build_agent_command(agent_name: str, command: str, executor: str,
                        model: str = "", permissions: dict = None) -> list[str]:
    """根据执行器类型构造实际命令行。

    permissions 字典可包含：
      - permission_mode: str   (Claude: --permission-mode)
      - allowed_tools: list    (Claude: --allowedTools)
      - add_dirs: list         (Claude: --add-dir)
    """
    prompt = build_agent_prompt(agent_name, command)
    cmd = [executor]
    executor_kind = get_executor_kind(executor)
    perms = permissions or {}

    if executor_kind == "opencode":
        cmd.append("run")
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
        return cmd

    # Claude 执行器
    if model:
        cmd.extend(["--model", model])

    # 权限参数（仅 Claude 支持）
    perm_mode = perms.get("permission_mode", "")
    if perm_mode:
        cmd.extend(["--permission-mode", perm_mode])

    allowed_tools = perms.get("allowed_tools", [])
    if allowed_tools:
        cmd.extend(["--allowedTools"] + list(allowed_tools))

    add_dirs = perms.get("add_dirs", [])
    if add_dirs:
        cmd.extend(["--add-dir"] + list(add_dirs))

    cmd.extend(["-p", prompt, "--print"])
    return cmd

def _parse_permissions(raw) -> dict:
    """解析权限配置为标准化字典。

    返回:
      {
        'permission_mode': str,    # Claude --permission-mode
        'allowed_tools': list,     # Claude --allowedTools
        'add_dirs': list,          # Claude --add-dir
      }
    空值会被过滤，返回可能是空字典。
    """
    if not raw or not isinstance(raw, dict):
        return {}
    result = {}
    pm = raw.get("permission_mode", "")
    if pm:
        result["permission_mode"] = str(pm)
    at = raw.get("allowed_tools", [])
    if at:
        result["allowed_tools"] = list(at) if isinstance(at, list) else [str(at)]
    ad = raw.get("add_dirs", [])
    if ad:
        result["add_dirs"] = list(ad) if isinstance(ad, list) else [str(ad)]
    return result


def _merge_permissions(agent_perms: dict, sched_perms: dict) -> dict:
    """合并 agent 级和 schedule 级权限。

    规则：
    - permission_mode: schedule 级覆盖 agent 级
    - allowed_tools: 合并（去重）
    - add_dirs: 合并（去重）
    """
    if not agent_perms and not sched_perms:
        return {}
    if not sched_perms:
        return dict(agent_perms)
    if not agent_perms:
        return dict(sched_perms)

    merged = {}

    # permission_mode: schedule 级优先
    pm = sched_perms.get("permission_mode") or agent_perms.get("permission_mode", "")
    if pm:
        merged["permission_mode"] = pm

    # allowed_tools: 合并去重
    at = list(dict.fromkeys(
        agent_perms.get("allowed_tools", []) + sched_perms.get("allowed_tools", [])
    ))
    if at:
        merged["allowed_tools"] = at

    # add_dirs: 合并去重
    ad = list(dict.fromkeys(
        agent_perms.get("add_dirs", []) + sched_perms.get("add_dirs", [])
    ))
    if ad:
        merged["add_dirs"] = ad

    return merged


def load_configs() -> list:
    """
    扫描 configs/ 下所有 .yaml 文件，返回解析后的配置列表。
    每个元素: {
      'file': Path,
      'mtime': float,
      'agent_name': str,
      'executor': str,
      'model': str,
      'permissions': dict,
      'schedules': [{command, cron: CronExpr, description, executor, model, permissions}, ...]
    }
    """
    configs = []
    if not CONFIGS_DIR.exists():
        return configs

    for yaml_file in sorted(CONFIGS_DIR.glob("*.yaml")):
        try:
            text = yaml_file.read_text(encoding="utf-8")
            data = parse_simple_yaml(text)
            agent = data.get("agent", {})
            agent_name = agent.get("name", yaml_file.stem)
            executor = agent.get("executor", "claude")
            model = agent.get("model", "")
            # 解析 executor 的完整路径（launchd 环境 PATH 受限）
            executor = resolve_executor(executor)
            # agent 级权限
            agent_permissions = _parse_permissions(agent.get("permissions", {}))

            schedules = []
            for item in data.get("schedules", []):
                if isinstance(item, dict):
                    cron_str = item.get("cron", "")
                    try:
                        cron = CronExpr(cron_str)
                    except ValueError as e:
                        log_scheduler("ERROR", f"{agent_name}/-", f"无效 cron: {cron_str} ({e})")
                        continue
                    # 命令级路由：schedule 项可覆盖 agent 级的 executor/model
                    sched_executor = item.get("executor", "")
                    sched_model = item.get("model", "")
                    if sched_executor:
                        sched_executor = resolve_executor(sched_executor)
                    # 命令级权限
                    sched_permissions = _parse_permissions(item.get("permissions", {}))
                    schedules.append({
                        "command": item.get("command", ""),
                        "cron": cron,
                        "description": item.get("description", ""),
                        "executor": sched_executor,
                        "model": sched_model,
                        "permissions": sched_permissions,
                    })

            configs.append({
                "file": yaml_file,
                "mtime": yaml_file.stat().st_mtime,
                "agent_name": agent_name,
                "executor": executor,
                "model": model,
                "permissions": agent_permissions,
                "schedules": schedules,
            })
        except Exception as e:
            log_scheduler("ERROR", f"{yaml_file.name}/-", f"配置解析失败: {e}")

    return configs


# ============================================================
# 7. 任务执行线程
# ============================================================

def run_agent_task(agent_name: str, command: str, executor: str,
                   model: str, description: str, permissions: dict = None):
    """在独立线程中执行一个 agent 命令"""
    start_time = datetime.now()
    tag = f"{agent_name}/{command}"

    # 记总日志 START
    log_scheduler("START", tag, description)

    # 更新 state: running
    update_agent_state(agent_name,
                       status="running",
                       current_command=command,
                       started_at=start_time.strftime("%Y-%m-%d %H:%M:%S"))

    cmd = build_agent_command(agent_name, command, executor, model, permissions)

    stdout_text = ""
    stderr_text = ""
    returncode = -1

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 小时超时
        )
        stdout_text = result.stdout
        stderr_text = result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        stderr_text = "执行超时（3600 秒）"
        returncode = -1
        log_scheduler("ERROR", tag, "执行超时")
    except FileNotFoundError:
        stderr_text = f"执行器 '{executor}' 未找到"
        returncode = -1
        log_scheduler("ERROR", tag, f"执行器 '{executor}' 未找到")
    except Exception as e:
        stderr_text = str(e)
        returncode = -1
        log_scheduler("ERROR", tag, f"异常: {e}")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # 写详细日志
    write_detail_log(agent_name, command, executor,
                     start_time, end_time, returncode,
                     stdout_text, stderr_text, cmd)

    # 记总日志 END/ERROR
    if returncode == 0:
        log_scheduler("END", tag, f"耗时 {duration:.1f}s, 退出码 {returncode}")
    else:
        log_scheduler("ERROR", tag, f"耗时 {duration:.1f}s, 退出码 {returncode}")

    # 更新 state: sleeping，累计运行次数
    with state_lock:
        state = load_state()
        agents = state.setdefault("agents", {})
        agent = agents.setdefault(agent_name, {})
        total = agent.get("total_runs", 0) + 1
        agent.update({
            "status": "sleeping",
            "current_command": None,
            "started_at": None,
            "last_run": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_command": command,
            "total_runs": total,
        })
        save_state(state)

    # 从 running_agents 移除
    with running_agents_lock:
        running_agents.pop(agent_name, None)


# ============================================================
# 8. 主循环
# ============================================================

def main_loop():
    """调度器主循环：每 30 秒检查一次，执行匹配的任务"""

    configs = load_configs()
    config_mtimes = {c["file"]: c["mtime"] for c in configs}
    last_config_check = time.time()
    config_check_interval = 300  # 每 5 分钟检查配置变更

    log_scheduler("START", "scheduler/-", f"调度器启动, PID={os.getpid()}, 加载 {len(configs)} 个配置")

    # 初始化 state.json 中的 agent 状态
    for cfg in configs:
        update_agent_state(cfg["agent_name"], status="sleeping")

    while not shutdown_event.is_set():
        now = datetime.now()

        # ---- 配置热加载检查 ----
        if time.time() - last_config_check >= config_check_interval:
            last_config_check = time.time()
            need_reload = False

            # 检查现有文件的 mtime 变更
            for f, old_mt in list(config_mtimes.items()):
                if f.exists():
                    if f.stat().st_mtime != old_mt:
                        need_reload = True
                        break
                else:
                    # 文件被删除
                    need_reload = True
                    break

            # 检查是否有新文件
            if not need_reload and CONFIGS_DIR.exists():
                current_files = set(CONFIGS_DIR.glob("*.yaml"))
                if current_files != set(config_mtimes.keys()):
                    need_reload = True

            if need_reload:
                log_scheduler("START", "scheduler/reload", "检测到配置变更, 重新加载")
                configs = load_configs()
                config_mtimes = {c["file"]: c["mtime"] for c in configs}
                log_scheduler("END", "scheduler/reload", f"加载 {len(configs)} 个配置")

        # ---- 遍历所有 schedule，检查是否需要执行 ----
        for cfg in configs:
            agent_name = cfg["agent_name"]
            default_executor = cfg["executor"]
            default_model = cfg.get("model", "")
            default_permissions = cfg.get("permissions", {})

            for sched in cfg["schedules"]:
                command = sched["command"]
                cron = sched["cron"]
                description = sched["description"]
                # 命令级路由：优先使用 schedule 项的 executor/model，否则回退到 agent 级默认
                effective_executor = sched.get("executor") or default_executor
                effective_model = sched.get("model") or default_model
                # 权限合并：agent 级 + schedule 级
                effective_permissions = _merge_permissions(
                    default_permissions, sched.get("permissions", {}))
                tag = f"{agent_name}/{command}"

                if not cron.matches(now):
                    continue

                # cron 匹配，检查是否已在运行
                with running_agents_lock:
                    if agent_name in running_agents:
                        info = running_agents[agent_name]
                        elapsed = (datetime.now() - info["start_time"]).total_seconds()
                        log_scheduler("SKIP", tag,
                                      f"跳过: agent '{agent_name}' 正在执行 "
                                      f"'{info['command']}' (已运行 {elapsed:.0f}s)")
                        continue

                    # 启动新线程执行
                    t = threading.Thread(
                        target=run_agent_task,
                        args=(agent_name, command, effective_executor,
                              effective_model, description, effective_permissions),
                        daemon=True,
                        name=f"agent-{agent_name}",
                    )
                    running_agents[agent_name] = {
                        "thread": t,
                        "command": command,
                        "start_time": datetime.now(),
                    }
                    t.start()

        # 等待 30 秒，但可被 shutdown 信号提前唤醒
        shutdown_event.wait(timeout=30)

    # ---- 优雅关闭：等待所有运行中的线程完成 ----
    log_scheduler("END", "scheduler/-", "收到关闭信号, 等待运行中的任务完成...")

    with running_agents_lock:
        threads = [(name, info["thread"]) for name, info in running_agents.items()]

    for name, t in threads:
        log_scheduler("END", f"scheduler/{name}", f"等待 agent '{name}' 完成...")
        t.join(timeout=300)  # 最多等 5 分钟
        if t.is_alive():
            log_scheduler("ERROR", f"scheduler/{name}", f"agent '{name}' 等待超时, 强制退出")

    log_scheduler("END", "scheduler/-", "调度器已停止")


# ============================================================
# 9. 信号处理
# ============================================================

def handle_signal(signum, frame):
    """SIGTERM / SIGINT 信号处理：设置 shutdown 标志"""
    sig_name = signal.Signals(signum).name
    log_scheduler("END", "scheduler/-", f"收到信号 {sig_name}, 准备关闭")
    shutdown_event.set()


# ============================================================
# 10. 命令行入口
# ============================================================

def cmd_stop():
    """停止运行中的调度服务"""
    if not PID_FILE.exists():
        print("调度器未在运行 (PID 文件不存在)")
        sys.exit(1)

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, IOError):
        print("PID 文件内容无效")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)

    try:
        os.kill(pid, 0)  # 检查进程是否存在
    except ProcessLookupError:
        print(f"进程 {pid} 不存在, 清理 PID 文件")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(1)

    print(f"向进程 {pid} 发送 SIGTERM...")
    os.kill(pid, signal.SIGTERM)

    # 等待进程退出
    for _ in range(30):
        time.sleep(1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print("调度器已停止")
            return
    print("警告: 进程仍在运行, 可能需要手动终止")


def cmd_daemon():
    """以守护进程方式启动"""
    pid = os.fork()
    if pid > 0:
        # 父进程退出
        print(f"调度器已在后台启动, PID={pid}")
        sys.exit(0)

    # 子进程：脱离控制终端
    os.setsid()

    # 二次 fork，确保不会获取控制终端
    pid2 = os.fork()
    if pid2 > 0:
        sys.exit(0)

    # 重定向标准流
    sys.stdin = open(os.devnull, "r")
    sys.stdout = open(LOGS_DIR / "daemon_stdout.log", "a")
    sys.stderr = open(LOGS_DIR / "daemon_stderr.log", "a")

    # 以守护进程身份运行
    run_scheduler()


def run_scheduler():
    """启动调度器的核心流程"""
    global scheduler_start_time

    # 确保目录存在
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

    # 进程锁
    if not acquire_pid_lock():
        old_pid = PID_FILE.read_text().strip() if PID_FILE.exists() else "?"
        print(f"错误: 调度器已在运行 (PID={old_pid})")
        sys.exit(1)

    # 注册信号处理
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # 启动 HTTP server
    scheduler_start_time = datetime.now()
    http_port = start_http_server()
    log_scheduler("START", "scheduler/http", f"HTTP API 已启动在端口 {http_port}")

    # 初始化 state.json（包含 http_port）
    init_state(http_port)

    try:
        main_loop()
    finally:
        # 停止 HTTP server
        stop_http_server()

        # 清理 state.json 中的 pid
        try:
            state = load_state()
            state["pid"] = None
            state["http_port"] = None
            state["stopped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_state(state)
        except Exception:
            pass
        release_pid_lock()


def main():
    args = sys.argv[1:]

    if "--stop" in args:
        cmd_stop()
    elif "--daemon" in args:
        cmd_daemon()
    else:
        # 前台运行
        run_scheduler()


if __name__ == "__main__":
    main()
