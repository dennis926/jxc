#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进销存备份 → 百度网盘上传

复用整站备份系统（BF.HONS.FUN / /opt/site-backup-manager）的 BaiduPCS-Go 方案：
  - 同一个命令行工具：/usr/local/bin/BaiduPCS-Go
  - 同一份登录状态目录（通过 HOME 环境变量指定），无需重复登录
  - 远端目录与整站备份分开，避免混在一起

设计要点：
  - 上传失败绝不影响备份本身（调用方捕获异常，备份与邮件照常）
  - 上传成功后自动清理超出保留份数的旧备份，避免网盘无限增长
  - 全部路径/份数可用环境变量覆盖，便于迁移到别的机器
"""
import os
import re
import subprocess

BAIDU_CLI = os.environ.get("JXC_BAIDU_CLI", "/usr/local/bin/BaiduPCS-Go")
# 与整站备份系统共用登录状态（含百度账号 cookie）
BAIDU_HOME = os.environ.get("JXC_BAIDU_HOME", "/var/lib/site-backup-manager/baidu")
REMOTE_DIR = os.environ.get("JXC_BAIDU_REMOTE_DIR", "/服务器备份/进销存")
KEEP_COUNT = int(os.environ.get("JXC_BAIDU_KEEP", "30"))
UPLOAD_TIMEOUT = int(os.environ.get("JXC_BAIDU_TIMEOUT", "600"))

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _env():
    env = os.environ.copy()
    env["HOME"] = BAIDU_HOME
    return env


def _run(args, timeout=60):
    """执行 BaiduPCS-Go 命令，返回 (退出码, 输出文本)"""
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, env=_env(), timeout=timeout
        )
        out = _ANSI.sub("", (proc.stdout or "") + (proc.stderr or "")).replace("\x1b", "")
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "执行超时"
    except FileNotFoundError:
        return 127, f"未找到命令行工具：{BAIDU_CLI}"
    except Exception as exc:  # noqa: BLE001
        return 1, f"执行异常：{exc}"


def check_login():
    """检查百度网盘登录状态是否有效，返回 (是否有效, 账号信息或错误)"""
    code, out = _run([BAIDU_CLI, "who"], timeout=30)
    text = out.strip()
    if code == 0 and "uid" in text:
        first = text.splitlines()[0] if text else "已登录"
        return True, first
    return False, text[:300] or "登录状态无效"


def _remote_names(remote_dir):
    """列出远端目录中本项目的备份文件名（升序）"""
    code, out = _run([BAIDU_CLI, "ls", remote_dir], timeout=90)
    if code != 0:
        return []
    names = re.findall(r"(inventory_backup_\d+_\d+\.zip)", out)
    return sorted(set(names))


def upload_backup(local_path, keep=None, remote_dir=None):
    """上传备份文件到百度网盘

    返回 (是否成功, 说明文本)。成功时说明文本为远端路径（可能附带清理信息）。
    """
    keep = KEEP_COUNT if keep is None else keep
    remote_dir = (remote_dir or REMOTE_DIR).rstrip("/")

    if not os.path.exists(local_path):
        return False, f"本地文件不存在：{local_path}"
    if not os.path.exists(BAIDU_CLI):
        return False, f"未安装命令行工具：{BAIDU_CLI}"

    ok, who = check_login()
    if not ok:
        return False, f"百度网盘登录状态失效：{who}"

    # 远端目录不存在时先创建（已存在会返回“目录已存在”，忽略其结果）
    _run([BAIDU_CLI, "mkdir", remote_dir], timeout=60)

    code, out = _run(
        [BAIDU_CLI, "upload", "--policy=overwrite", "--retry=3", local_path, remote_dir],
        timeout=UPLOAD_TIMEOUT,
    )
    if code != 0:
        return False, f"上传失败：{_ANSI.sub('', out).strip()[:300]}"

    remote_path = f"{remote_dir}/{os.path.basename(local_path)}"

    # 清理超出保留份数的旧备份（最新的保留，其余按文件名顺序删除）
    removed = 0
    try:
        names = _remote_names(remote_dir)
        if len(names) > keep:
            for name in names[:-keep]:
                del_code, _ = _run([BAIDU_CLI, "rm", f"{remote_dir}/{name}"], timeout=180)
                if del_code == 0:
                    removed += 1
    except Exception:  # noqa: BLE001
        pass

    msg = remote_path
    if removed:
        msg += f"（已清理 {removed} 份旧备份，保留最近 {keep} 份）"
    return True, msg


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        ok, info = check_login()
        print(("登录有效：" if ok else "登录无效：") + info)
        sys.exit(0 if ok else 1)
    if len(sys.argv) > 1:
        success, info = upload_backup(sys.argv[1])
        print(("上传成功：" if success else "上传失败：") + info)
        sys.exit(0 if success else 1)
    print("用法：python3 baidu_backup.py [--check | <本地备份文件路径>]")
