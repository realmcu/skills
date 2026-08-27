#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""嵌入式实验台的配置检查、串口发现和 command backend 启动器。

本脚本刻意不内置任何芯片或烧写工具。它负责可移植的 bootstrap：

  * 合并可共享配置与本机覆盖；
  * 按 USB 稳定身份发现串口，而不是盲信 COM 号；
  * 检查路径、命令、端口角色与高风险配置；
  * 以 argv 数组渲染并执行 build/flash 等 command backend；
  * 保存完整输出、检查 marker，并在超时时清理进程树。

真正的 board-specific reset/capture/parser/store 状态机应在目标项目 harness 中实现；
本脚本不依赖任何特定应用、仓库目录或实验数据。
"""

import argparse
import copy
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


class ConfigError(RuntimeError):
    pass


KNOWN_TOKENS = {
    "root",
    "work_dir_abs",
    "build_dir_abs",
    "data_dir_abs",
    "flash_port",
    "log_port",
    "reset_port",
    "artifact",
    "build_id",
    "tag",
}
SENSITIVE_KEY = re.compile(r"(?:password|passwd|token|secret|api[_-]?key|private[_-]?key)", re.I)
PORT_RE = re.compile(r"\((COM\d+)\)", re.I)
VID_RE = re.compile(r"VID[_=]([0-9A-F]{4})", re.I)
PID_RE = re.compile(r"PID[_=]([0-9A-F]{4})", re.I)
FTDI_SERIAL_RE = re.compile(r"VID_[0-9A-F]{4}\+PID_[0-9A-F]{4}\+([^\\+]+)", re.I)


def deep_merge(base, overlay):
    """递归合并字典；list 和 scalar 由本机配置整体替换。"""
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def read_json(path):
    try:
        # Windows PowerShell 5.1 常生成带 BOM 的 UTF-8 JSON；utf-8-sig 同时兼容
        # 有 BOM 和无 BOM 文件，避免本机 override 因编辑器差异无法读取。
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ConfigError("配置文件不存在：{}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise ConfigError("配置 JSON 无效：{}:{}:{} {}".format(
            path, exc.lineno, exc.colno, exc.msg)) from exc


def load_config(path, local_path=None):
    path = Path(path).resolve()
    cfg = read_json(path)
    if local_path:
        cfg = deep_merge(cfg, read_json(Path(local_path).resolve()))
    cfg["_config_path"] = str(path)
    cfg["_config_dir"] = str(path.parent)
    return cfg


def expand_path(value, base):
    if value is None:
        return None
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    path = Path(expanded)
    if not path.is_absolute():
        path = Path(base) / path
    return path.resolve()


def project_paths(cfg):
    project = cfg.get("project") or {}
    config_dir = Path(cfg.get("_config_dir") or ".").resolve()
    root = expand_path(project.get("root", "."), config_dir)
    work_dir = expand_path(project.get("work_dir", "."), root)

    build_cfg = cfg.get("build") or {}
    build_dir = expand_path(build_cfg.get("build_dir", "build"), root)
    data_dir = expand_path(project.get("data_dir", "data"), root)
    return {
        "root": root,
        "work_dir_abs": work_dir,
        "build_dir_abs": build_dir,
        "data_dir_abs": data_dir,
    }


def normalize_hex(value):
    if value is None:
        return None
    # pyserial 的 vid/pid 是十进制 int；配置/CIM 通常给十六进制文本。
    if isinstance(value, int):
        return "{:04X}".format(value)
    text = str(value).strip().upper()
    if text.startswith("0X"):
        text = text[2:]
    return text.zfill(4)


def parse_pnp_identity(pnp_id):
    pnp_id = pnp_id or ""
    vid = VID_RE.search(pnp_id)
    pid = PID_RE.search(pnp_id)
    serial = None
    ftdi = FTDI_SERIAL_RE.search(pnp_id)
    if ftdi:
        serial = ftdi.group(1)
    elif "\\" in pnp_id:
        tail = pnp_id.rsplit("\\", 1)[-1]
        if tail and "&" not in tail:
            serial = tail
    return {
        "vid": normalize_hex(vid.group(1)) if vid else None,
        "pid": normalize_hex(pid.group(1)) if pid else None,
        "serial": serial,
    }


def discover_pyserial():
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    ports = []
    for item in list_ports.comports():
        ports.append({
            "device": item.device,
            "description": item.description,
            "manufacturer": item.manufacturer,
            "pnp_id": item.hwid,
            "vid": normalize_hex(item.vid) if item.vid is not None else None,
            "pid": normalize_hex(item.pid) if item.pid is not None else None,
            "serial": item.serial_number,
            "location": item.location,
            "source": "pyserial",
        })
    return ports


def discover_windows_cim():
    script = r"""
$items = @(Get-CimInstance Win32_PnPEntity |
  Where-Object { $_.Name -match '\(COM\d+\)' } |
  ForEach-Object {
    [PSCustomObject]@{
      Name = $_.Name
      Manufacturer = $_.Manufacturer
      PNPDeviceID = $_.PNPDeviceID
    }
  })
$items | ConvertTo-Json -Compress
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, errors="replace", timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict):
        raw = [raw]

    ports = []
    for item in raw:
        name = item.get("Name") or ""
        found = PORT_RE.search(name)
        if not found:
            continue
        pnp_id = item.get("PNPDeviceID") or ""
        identity = parse_pnp_identity(pnp_id)
        ports.append({
            "device": found.group(1).upper(),
            "description": name,
            "manufacturer": item.get("Manufacturer"),
            "pnp_id": pnp_id,
            "vid": identity["vid"],
            "pid": identity["pid"],
            "serial": identity["serial"],
            "location": None,
            "source": "windows-cim",
        })
    return ports


def discover_fallback_devices():
    candidates = []
    for pattern in (
            "/dev/ttyUSB*", "/dev/ttyACM*", "/dev/tty.usbserial-*",
            "/dev/cu.usbserial-*", "/dev/cu.usbmodem*"):
        candidates.extend(glob.glob(pattern))
    return [{
        "device": value,
        "description": None,
        "manufacturer": None,
        "pnp_id": None,
        "vid": None,
        "pid": None,
        "serial": None,
        "location": None,
        "source": "device-glob",
    } for value in sorted(set(candidates))]


def discover_ports():
    ports = discover_pyserial()
    if ports is not None:
        return sorted(ports, key=lambda p: p.get("device") or "")
    if platform.system() == "Windows":
        return sorted(discover_windows_cim(), key=lambda p: p.get("device") or "")
    return discover_fallback_devices()


def port_spec(cfg, role):
    section = cfg.get(role) or {}
    value = section.get("port")
    if isinstance(value, str):
        return {"device": value}
    if isinstance(value, dict):
        return value
    if role == "flash" and (cfg.get("capture") or {}).get("shares_flash_port"):
        return port_spec(cfg, "capture")
    return {}


def same_value(actual, expected, hex_value=False):
    if expected in (None, ""):
        return True
    if actual is None:
        return False
    if hex_value:
        return normalize_hex(actual) == normalize_hex(expected)
    return str(actual).casefold() == str(expected).casefold()


def port_matches(port, spec, ignore_device=False):
    if not ignore_device and spec.get("device") and not same_value(
            port.get("device"), spec.get("device")):
        return False
    if not same_value(port.get("vid"), spec.get("vid"), hex_value=True):
        return False
    if not same_value(port.get("pid"), spec.get("pid"), hex_value=True):
        return False
    if not same_value(port.get("serial"), spec.get("serial")):
        return False
    if not same_value(port.get("location"), spec.get("location")):
        return False
    return True


def resolve_port(spec, ports):
    if not spec:
        return None, "未配置"

    device = spec.get("device")
    identity_keys = [key for key in ("vid", "pid", "serial", "location")
                     if spec.get(key)]
    stable = "serial" in identity_keys or "location" in identity_keys
    if stable:
        # serial/location 才足以作为稳定 identity。VID/PID 只用于进一步
        # 校验；单独 VID/PID 往往会同时匹配多个同型号 adapter。
        matches = [p for p in ports if port_matches(p, spec, ignore_device=True)]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "稳定身份匹配到多个串口：{}".format(
                ", ".join(p.get("device") or "?" for p in matches))
        if device:
            by_device = [p for p in ports if same_value(p.get("device"), device)]
            if by_device:
                return None, "{} 存在，但稳定身份与配置不符".format(device)
        return None, "没有匹配稳定身份的串口"

    if identity_keys and not device:
        matches = [p for p in ports if port_matches(p, spec, ignore_device=True)]
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "VID/PID 匹配到多个串口，需要 serial/location：{}".format(
                ", ".join(p.get("device") or "?" for p in matches))
        return None, "没有匹配 VID/PID 的串口"

    if identity_keys and device:
        by_device = [p for p in ports if same_value(p.get("device"), device)]
        if not by_device:
            return None, "设备 {} 不存在，且 VID/PID 不能安全解析漂移".format(device)
        if not port_matches(by_device[0], spec):
            return None, "{} 存在，但 VID/PID 与配置不符".format(device)
        return by_device[0], None

    if not device:
        return None, "既没有 device，也没有 stable identity"
    by_device = [p for p in ports if same_value(p.get("device"), device)]
    if not by_device:
        return None, "设备 {} 不存在".format(device)
    return by_device[0], None


def resolve_role_ports(cfg, ports):
    out = {}
    errors = {}
    for role in ("flash", "capture", "reset"):
        spec = port_spec(cfg, role)
        # J-Link、RTT、network capture 等 backend 不一定有 serial port。
        # 只有显式配置了 port（或 flash 声明与 capture 共口）才做串口解析。
        if not spec:
            continue
        match, error = resolve_port(spec, ports)
        out[role] = match
        if error:
            errors[role] = error
    return out, errors


def sensitive_paths(value, prefix=""):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = "{}.{}".format(prefix, key) if prefix else key
            if SENSITIVE_KEY.search(str(key)) and child not in (None, "", "${ENV}"):
                found.append(path)
            found.extend(sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(sensitive_paths(child, "{}[{}]".format(prefix, index)))
    return found


def find_tokens(text):
    return set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", str(text)))


def command_tokens(command):
    tokens = set()
    for item in command:
        tokens.update(find_tokens(item))
    return tokens


def command_section(cfg, dotted):
    value = cfg
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ConfigError("配置中没有 section：{}".format(dotted))
        value = value[part]
    if not isinstance(value, dict):
        raise ConfigError("section 不是对象：{}".format(dotted))
    return value


def format_values(cfg, resolved_ports=None, args=None):
    paths = project_paths(cfg)
    resolved_ports = resolved_ports or {}
    args = args or argparse.Namespace()

    def role_device(role):
        port = resolved_ports.get(role)
        if port:
            return port.get("device") or ""
        # 配置包含任何 identity 约束时，端口必须来自 resolve_port 的验证结果；
        # 不允许在解析失败后静默回退到陈旧 device。
        spec = port_spec(cfg, role)
        if any(spec.get(key) for key in ("vid", "pid", "serial", "location")):
            return ""
        return spec.get("device") or ""

    return {
        "root": str(paths["root"]),
        "work_dir_abs": str(paths["work_dir_abs"]),
        "build_dir_abs": str(paths["build_dir_abs"]),
        "data_dir_abs": str(paths["data_dir_abs"]),
        "flash_port": role_device("flash"),
        "log_port": role_device("capture"),
        "reset_port": role_device("reset"),
        "artifact": getattr(args, "artifact", None) or "",
        "build_id": getattr(args, "build_id", None) or "",
        "tag": getattr(args, "tag", None) or "",
    }


def render_command(section, values):
    command = section.get("command")
    if not isinstance(command, list) or not command or not all(
            isinstance(item, str) for item in command):
        raise ConfigError("section.command 必须是非空字符串数组")
    unknown = command_tokens(command) - KNOWN_TOKENS
    if unknown:
        raise ConfigError("command 包含未知 token：{}".format(
            ", ".join(sorted(unknown))))
    try:
        return [os.path.expandvars(item.format(**values)) for item in command]
    except KeyError as exc:
        raise ConfigError("command token 缺少值：{}".format(exc)) from exc


def executable_exists(executable, cwd):
    expanded = os.path.expandvars(os.path.expanduser(executable))
    if any(sep in expanded for sep in ("/", "\\")):
        path = Path(expanded)
        if not path.is_absolute():
            path = Path(cwd) / path
        return path.is_file(), str(path.resolve())
    found = shutil.which(expanded)
    return found is not None, found or expanded


def print_ports(ports, as_json=False):
    if as_json:
        print(json.dumps(ports, ensure_ascii=False, indent=2))
        return
    if not ports:
        print("未发现串口。")
        return
    print("{:<10} {:<9} {:<9} {:<18} {}".format(
        "device", "VID", "PID", "serial", "description"))
    print("-" * 90)
    for item in ports:
        print("{:<10} {:<9} {:<9} {:<18} {}".format(
            item.get("device") or "-",
            item.get("vid") or "-",
            item.get("pid") or "-",
            item.get("serial") or "-",
            item.get("description") or "-"))
        if item.get("pnp_id"):
            print("  PNP: {}".format(item["pnp_id"]))


def cmd_discover(args):
    ports = discover_ports()
    unresolved_count = 0
    if args.config:
        cfg = load_config(args.config, args.local)
        resolved, errors = resolve_role_ports(cfg, ports)
        roles = {}
        for role in ("flash", "capture", "reset"):
            item = resolved.get(role)
            spec = port_spec(cfg, role)
            if item:
                configured = spec.get("device")
                roles[role] = {
                    "status": "resolved",
                    "device": item.get("device"),
                    "serial": item.get("serial"),
                    "configured_device": configured,
                    "device_drift": bool(
                        configured and not same_value(configured, item.get("device"))),
                }
            elif role in errors:
                unresolved_count += 1
                roles[role] = {"status": "unresolved", "error": errors[role]}

        if args.json:
            print(json.dumps({"ports": ports, "roles": roles},
                             ensure_ascii=False, indent=2))
        else:
            print_ports(ports)
            print("\n角色解析：")
            for role, result in roles.items():
                if result["status"] == "resolved":
                    drift = "（configured device 已漂移）" if result["device_drift"] else ""
                    print("  {:<8} -> {} serial={} {}".format(
                        role, result["device"], result.get("serial") or "-", drift))
                else:
                    print("  {:<8} -> UNRESOLVED: {}".format(
                        role, result["error"]))
    else:
        print_ports(ports, args.json)

    if discover_pyserial() is None and not args.json:
        print("提示：当前使用系统级串口枚举；安装 pyserial 可在更多平台获得 "
              "VID/PID/serial/location，并支持后续 serial reset/capture backend。",
              file=sys.stderr)
    return 1 if unresolved_count else 0


def probe_serial_port(device):
    """尝试独占打开串口；不发送 payload，但 open 仍可能改变控制线。"""
    try:
        import serial
    except ImportError:
        return None, "未安装 pyserial，跳过占用检查"

    ser = serial.Serial()
    ser.port = device
    ser.timeout = 0
    ser.write_timeout = 0
    ser.rtscts = False
    ser.dsrdtr = False
    # 在 open 前设置，避免某些 adapter 的 control line 瞬态。
    ser.rts = False
    ser.dtr = False
    try:
        ser.open()
        ser.close()
        return True, None
    except serial.SerialException as exc:
        return False, str(exc)


def cmd_doctor(args):
    cfg = load_config(args.config, args.local)
    paths = project_paths(cfg)
    ports = discover_ports()
    resolved, port_errors = resolve_role_ports(cfg, ports)
    errors = []
    warnings = []
    placeholder_pattern = re.compile(r"(?:REPLACE_|DISCOVER_)")

    def find_placeholders(value, prefix=""):
        found = []
        if isinstance(value, dict):
            for key, child in value.items():
                path = "{}.{}".format(prefix, key) if prefix else key
                found.extend(find_placeholders(child, path))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                found.extend(find_placeholders(child, "{}[{}]".format(prefix, index)))
        elif isinstance(value, str) and placeholder_pattern.search(value):
            found.append(prefix)
        return found

    print("项目：{}".format((cfg.get("project") or {}).get("name", "未命名")))
    for name, path in paths.items():
        exists = path.exists()
        print("  {:<15} {} [{}]".format(name, path, "OK" if exists else "MISSING"))
        if name in ("root", "work_dir_abs") and not exists:
            errors.append("{} 不存在：{}".format(name, path))

    public_cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    sensitive = sensitive_paths(public_cfg)
    if sensitive:
        errors.append("配置疑似包含敏感值，请改用环境变量：{}".format(
            ", ".join(sensitive)))
    placeholders = find_placeholders(public_cfg)
    if placeholders:
        errors.append("配置仍含模板占位符：{}".format(
            ", ".join(placeholders)))

    for role in ("flash", "capture", "reset"):
        if not port_spec(cfg, role):
            continue
        if role in port_errors:
            print("  port {:<8} FAIL  {}".format(role, port_errors[role]))
            errors.append("{} port：{}".format(role, port_errors[role]))
        else:
            item = resolved.get(role)
            configured_device = port_spec(cfg, role).get("device")
            drift = (configured_device and
                     not same_value(configured_device, item.get("device")))
            suffix = "；端口已从 {} 漂移".format(configured_device) if drift else ""
            print("  port {:<8} OK    {} serial={} ({}){}".format(
                role, item.get("device"), item.get("serial") or "-",
                item.get("description") or "-", suffix))
            if drift:
                warnings.append(
                    "{} 使用稳定硬件身份解析为 {}，无需因 COM/tty 漂移失败".format(
                        role, item.get("device")))

    if args.probe_ports:
        requested_roles = set(args.probe_ports)
        probed = set()
        for role in ("flash", "capture", "reset"):
            if role not in requested_roles:
                continue
            item = resolved.get(role)
            device = (item or {}).get("device")
            if not device or device.casefold() in probed:
                continue
            probed.add(device.casefold())
            ok, detail = probe_serial_port(device)
            if ok is True:
                print("  probe {:<8} OK    {} 可独占打开".format(role, device))
            elif ok is False:
                errors.append("{} port {} 无法打开：{}".format(role, device, detail))
            else:
                warnings.append("{} port {}：{}".format(role, device, detail))

    flash_device = (resolved.get("flash") or {}).get("device")
    log_device = (resolved.get("capture") or {}).get("device")
    reset_device = (resolved.get("reset") or {}).get("device")
    shares = bool((cfg.get("capture") or {}).get("shares_flash_port"))
    if flash_device and log_device and same_value(flash_device, log_device) != shares:
        errors.append("flash/log 实际共口状态与 capture.shares_flash_port 不一致")
    reset_backend = (cfg.get("reset") or {}).get("backend")
    if reset_backend == "serial-rts" and reset_device and flash_device and same_value(
            reset_device, flash_device):
        errors.append("serial-rts reset 与 flash 使用同一串口，会发生独占冲突")

    values = format_values(cfg, resolved)
    for section_name in ("build", "flash"):
        section = cfg.get(section_name)
        if not isinstance(section, dict) or "command" not in section:
            continue
        try:
            command = render_command(section, values)
        except ConfigError as exc:
            errors.append("{}：{}".format(section_name, exc))
            continue
        cwd = expand_path(section.get("cwd") or paths["work_dir_abs"], paths["root"])
        ok, location = executable_exists(command[0], cwd)
        print("  cmd  {:<8} {} [{}]".format(
            section_name, " ".join(command), "OK" if ok else "MISSING"))
        if not ok:
            errors.append("{} executable 不可用：{}".format(section_name, location))
        if not cwd.is_dir():
            errors.append("{} cwd 不存在：{}".format(section_name, cwd))

    if (cfg.get("reset") or {}).get("backend") == "serial-rts":
        reset_cfg = cfg["reset"]
        if reset_cfg.get("polarity_verified") is not True:
            errors.append("serial-rts 必须在实测后显式设置 polarity_verified=true")
        if reset_cfg.get("deassert_before_open") is not True:
            errors.append("serial-rts 必须显式设置 deassert_before_open=true")
        if reset_cfg.get("hold_open_through_capture") is not True:
            warnings.append("reset port 未声明全程持有；飞线 nRESET 可能在 close 后悬空")

    if (cfg.get("capture") or {}).get("backend") == "serial":
        capture_cfg = cfg["capture"]
        if capture_cfg.get("rts") is not False or capture_cfg.get("dtr") is not False:
            warnings.append("serial capture 未明确 rts=false/dtr=false；某些板会在 open 时复位")

    print()
    for warning in warnings:
        print("WARNING: {}".format(warning))
    if errors:
        for error in errors:
            print("ERROR: {}".format(error), file=sys.stderr)
        print("doctor: FAIL（{} errors, {} warnings）".format(
            len(errors), len(warnings)), file=sys.stderr)
        return 1
    print("doctor: PASS（0 errors, {} warnings）".format(len(warnings)))
    return 0


def kill_process_tree(proc, process_names=None):
    running = proc.poll() is None
    if os.name == "nt":
        if running:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        # 按进程名清理会影响机器上其他任务，只在显式启用
        # kill_process_names_on_timeout 时使用；即使 parent 已退出，也能回收
        # 已知会脱离进程树的 vendor CLI child。
        for name in process_names or []:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
    elif running:
        try:
            os.killpg(proc.pid, 15)
        except (OSError, AttributeError):
            proc.terminate()
    if not running:
        return
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_streaming(command, cwd, timeout_s, log_path=None, process_names=None):
    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        start_new_session = True

    log_file = None
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        log_file = path.open("w", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    lines = []

    def reader():
        for line in proc.stdout:
            lines.append(line)
            sys.stdout.write(line)
            sys.stdout.flush()
            if log_file:
                log_file.write(line)
                log_file.flush()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_process_tree(proc, process_names)
    finally:
        thread.join(timeout=5)
        if log_file:
            log_file.close()
    return proc.returncode, "".join(lines), timed_out


def marker_verdict(section, output, returncode):
    errors = []
    if returncode != 0:
        errors.append("exit code {}".format(returncode))
    for marker in section.get("failure_markers") or []:
        if marker.casefold() in output.casefold():
            errors.append("命中 failure marker：{}".format(marker))

    success = section.get("success_markers") or []
    mode = section.get("success_mode", "all")
    output_folded = output.casefold()
    matched = [marker for marker in success if marker.casefold() in output_folded]
    if success:
        if mode == "any" and not matched:
            errors.append("未命中任何 success marker")
        elif mode == "all" and len(matched) != len(success):
            missing = [marker for marker in success
                       if marker.casefold() not in output_folded]
            errors.append("缺少 success marker：{}".format(", ".join(missing)))
        elif mode not in ("any", "all"):
            errors.append("success_mode 必须是 any 或 all")
    return errors


def cmd_command(args):
    cfg = load_config(args.config, args.local)
    section = command_section(cfg, args.section)
    ports = discover_ports()
    resolved, port_errors = resolve_role_ports(cfg, ports)
    needed_roles = {
        "flash_port": "flash",
        "log_port": "capture",
        "reset_port": "reset",
    }
    tokens = command_tokens(section.get("command") or [])
    for token, role in needed_roles.items():
        if token in tokens and role in port_errors:
            raise ConfigError("无法解析 {}：{}".format(token, port_errors[role]))

    values = format_values(cfg, resolved, args)
    command = render_command(section, values)
    paths = project_paths(cfg)
    cwd = expand_path(section.get("cwd") or paths["work_dir_abs"], paths["root"])
    print("cwd: {}".format(cwd))
    print("argv: {}".format(json.dumps(command, ensure_ascii=False)))
    if not args.execute:
        print("dry-run：增加 --execute 才会运行命令。")
        return 0

    executable_name = os.path.basename(command[0]).casefold()
    executable_stem = Path(executable_name).stem
    shell_launchers = {"cmd", "powershell", "pwsh", "sh", "bash"}
    if executable_stem in shell_launchers:
        raise ConfigError(
            "command backend 不接受通用 shell 入口；请把逻辑写入工作区内受审查的脚本，"
            "再将脚本及固定参数作为 argv 调用")

    timeout_s = args.timeout or section.get("timeout_s", 300)
    try:
        timeout_s = float(timeout_s)
    except (TypeError, ValueError) as exc:
        raise ConfigError("timeout 必须是正数") from exc
    if timeout_s <= 0:
        raise ConfigError("timeout 必须是正数")

    if args.log:
        log_path = Path(os.path.expandvars(os.path.expanduser(args.log)))
        if not log_path.is_absolute():
            log_path = paths["root"] / log_path
        data_root = paths["data_dir_abs"]
        try:
            log_path.resolve().relative_to(data_root.resolve())
        except ValueError as exc:
            raise ConfigError(
                "--log 必须位于 project.data_dir 内：{}".format(data_root)) from exc
        args.log = str(log_path.resolve())

    ok, location = executable_exists(command[0], cwd)
    if not ok:
        raise ConfigError("executable 不可用：{}".format(location))
    process_names = []
    if section.get("kill_process_names_on_timeout") is True:
        process_names = section.get("process_names") or []
    returncode, output, timed_out = run_streaming(
        command, cwd, timeout_s, args.log, process_names)
    if timed_out:
        print("ERROR: command timeout（{} s），已清理进程树".format(timeout_s),
              file=sys.stderr)
        return 124
    # marker 必须在本次 invocation 的完整输出中重新出现；旧 log/artifact
    # 不能参与本轮判定。run_streaming 默认以 "w" 创建独立 log，避免复用污染。
    errors = marker_verdict(section, output, returncode)
    if errors:
        for error in errors:
            print("ERROR: {}".format(error), file=sys.stderr)
        return returncode or 1
    print("command: PASS")
    return 0


def cmd_selftest(_args):
    failures = []

    def check(name, condition):
        print("[{}] {}".format("PASS" if condition else "FAIL", name))
        if not condition:
            failures.append(name)

    merged = deep_merge(
        {"a": {"x": 1, "y": 2}, "list": [1]},
        {"a": {"y": 3}, "list": [2]},
    )
    check("deep merge", merged == {"a": {"x": 1, "y": 3}, "list": [2]})

    identity = parse_pnp_identity(
        r"FTDIBUS\VID_0403+PID_6001+SAMPLE123A\0000")
    check("FTDI identity", identity == {
        "vid": "0403", "pid": "6001", "serial": "SAMPLE123A"})
    check("integer USB IDs use hex", normalize_hex(0x0403) == "0403")

    ports = [{
        "device": "COM17", "vid": "0403", "pid": "6001",
        "serial": "ABC", "location": None,
    }]
    match, error = resolve_port({"vid": "0403", "pid": "6001", "serial": "ABC"}, ports)
    check("stable port match", error is None and match["device"] == "COM17")
    match, error = resolve_port({
        "device": "COM9", "vid": "0403", "pid": "6001", "serial": "ABC",
    }, ports)
    check("device drift uses stable identity",
          error is None and match["device"] == "COM17")
    _, error = resolve_port({"device": "COM9"}, ports)
    check("missing device-only port rejected", error is not None)
    _, error = resolve_port({
        "device": "COM17", "vid": "0403", "pid": "6001", "serial": "WRONG",
    }, ports)
    check("identity mismatch rejected", error is not None)

    duplicate_ports = ports + [{
        "device": "COM18", "vid": "0403", "pid": "6001",
        "serial": "ABC", "location": None,
    }]
    _, error = resolve_port({"serial": "ABC"}, duplicate_ports)
    check("ambiguous stable identity rejected", error is not None)
    _, error = resolve_port({"vid": "0403", "pid": "6001"}, duplicate_ports)
    check("ambiguous VID/PID rejected", error is not None)
    match, error = resolve_port(
        {"device": "COM17", "vid": "0403", "pid": "6001"}, duplicate_ports)
    check("device plus VID/PID accepted",
          error is None and match["device"] == "COM17")

    resolved, errors = resolve_role_ports(
        {"flash": {"backend": "jlink", "command": ["west", "flash"]}}, ports)
    check("non-serial backend needs no port", not resolved and not errors)

    unresolved_cfg = {
        "_config_dir": ".",
        "project": {},
        "flash": {"port": {"device": "COM9", "serial": "MISSING"}},
    }
    unresolved, _ = resolve_role_ports(unresolved_cfg, ports)
    check("unresolved stable identity has no stale fallback",
          format_values(unresolved_cfg, unresolved)["flash_port"] == "")

    section = {"command": ["tool", "--port", "{flash_port}", "{artifact}"]}
    rendered = render_command(section, {
        "flash_port": "COM17", "artifact": "a b.bin",
        **{key: "" for key in KNOWN_TOKENS - {"flash_port", "artifact"}},
    })
    check("argv preserves spaces", rendered[-1] == "a b.bin" and len(rendered) == 4)

    try:
        render_command({"command": ["tool", "{unknown}"]}, {})
        unknown_rejected = False
    except ConfigError:
        unknown_rejected = True
    check("unknown token rejected", unknown_rejected)

    all_ok = not marker_verdict(
        {"success_markers": ["one", "two"], "success_mode": "all"},
        "ONE\nTWO\n", 0)
    check("all success markers", all_ok)
    missing_case = marker_verdict(
        {"success_markers": ["MiXeD", "absent"], "success_mode": "all"},
        "mixed\n", 0)
    check("missing marker report is case-insensitive",
          bool(missing_case) and "absent" in missing_case[0])
    any_fail = marker_verdict(
        {"success_markers": ["one", "two"], "success_mode": "any"},
        "absent\n", 0)
    check("missing any marker rejected", bool(any_fail))

    with tempfile.TemporaryDirectory() as temp_dir:
        bom_path = Path(temp_dir) / "bom.json"
        bom_path.write_text('{"ok": true}', encoding="utf-8-sig")
        check("UTF-8 BOM config", read_json(bom_path) == {"ok": True})

    print()
    if failures:
        print("selftest: FAIL（{}）".format(", ".join(failures)))
        return 1
    print("selftest: PASS")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="嵌入式实验台配置 discovery/doctor/command bootstrap")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    discover = sub.add_parser("discover", help="枚举串口及稳定硬件身份")
    discover.add_argument("--config", help="可选：同时解析配置中的逻辑角色")
    discover.add_argument("--local")
    discover.add_argument("--json", action="store_true", help="输出 JSON")
    discover.set_defaults(func=cmd_discover)

    doctor = sub.add_parser("doctor", help="检查配置、路径、工具和串口角色")
    doctor.add_argument("--config", required=True)
    doctor.add_argument("--local")
    doctor.add_argument(
        "--probe-port", dest="probe_ports", action="append",
        choices=("flash", "capture", "reset"), default=[],
        help="可重复：尝试独占打开指定角色串口；open 可能影响控制线，仅用于已确认安全的端口")
    doctor.set_defaults(func=cmd_doctor)

    command = sub.add_parser("command", help="渲染或执行 command backend")
    command.add_argument("--config", required=True)
    command.add_argument("--local")
    command.add_argument("--section", required=True,
                         help="配置 section，例如 build 或 flash")
    command.add_argument("--artifact")
    command.add_argument("--build-id")
    command.add_argument("--tag")
    command.add_argument("--timeout", type=float)
    command.add_argument("--log")
    command.add_argument("--execute", action="store_true",
                         help="真正执行；默认只打印 argv")
    command.set_defaults(func=cmd_command)

    selftest = sub.add_parser("selftest", help="运行无硬件自测")
    selftest.set_defaults(func=cmd_selftest)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
