from __future__ import annotations
import binascii
import socket
import paramiko
import winrm
from typing import Tuple, Optional
from .logger import get_logger

logger = get_logger("homevm")


# ---------- Wake on LAN ----------
def send_magic_packet(mac: str,
                      broadcast_ip: str = "255.255.255.255",
                      port: int = 9) -> None:
    """MACアドレスへマジックパケット送信"""
    mac_clean = mac.replace(":", "").replace("-", "").lower()
    if len(mac_clean) != 12 or not all(c in "0123456789abcdef" for c in mac_clean):
        raise ValueError(f"Invalid MAC: {mac}")

    data = b"FF" * 6 + (mac_clean.encode("ascii") * 16)
    packet = binascii.unhexlify(data)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(packet, (broadcast_ip, port))

    logger.info(f"WOL sent to MAC={mac}, dst={broadcast_ip}:{port}")


# ---------- 汎用 SSH クライアント ----------
class SshClient:
    """SSHで任意のコマンドを実行して電源制御などを行う"""
    def __init__(self, host: str, user: str, password: str,
                 port: int = 22, timeout: int = 10):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None

    def __enter__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.client:
            self.client.close()

    def run(self, cmd: str) -> Tuple[int, str, str]:
        """任意コマンド実行"""
        assert self.client
        logger.info(f"SSH {self.host} $ {cmd}")
        stdin, stdout, stderr = self.client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        rc = stdout.channel.recv_exit_status()
        if rc != 0:
            logger.error(f"SSH failed rc={rc}, err={err.strip()}")
        return rc, out.strip(), err.strip()

    def power_action(self, action: str) -> Tuple[bool, str]:
        """
        任意のLinux/UNIXに対して電源操作コマンドを実行。
        action: on / off / reboot / custom など
        """
        # ここで実際に送るコマンドを定義
        # ⚠️ 「on」はWake on LANで行うためSSH経由では通常不要
        cmd_map = {
            "off": "sudo shutdown -h now",
            "reboot": "sudo reboot",
            "reset": "sudo systemctl reboot",  # rebootと同義
        }

        cmd = cmd_map.get(action)
        if not cmd:
            msg = f"Unsupported action: {action}"
            logger.warning(msg)
            return False, msg

        rc, out, err = self.run(cmd)
        ok = (rc == 0)
        msg = out or err or ("OK" if ok else "NG")
        if ok:
            logger.info(f"Power {action} OK on {self.host}")
        else:
            logger.error(f"Power {action} NG on {self.host}: {msg}")
        return ok, msg

# ---------- WinRMクライアント (Windows) ----------
class WinRMClient:
    """WinRM経由でWindowsを制御"""
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    def run(self, ps_script: str) -> Tuple[int, str]:
        """PowerShellスクリプトを実行"""
        logger.info(f"[WinRM {self.host}] exec: {ps_script}")
        try:
            session = winrm.Session(
                self.host,
                auth=(self.user, self.password),
                transport='basic',
                server_cert_validation='ignore'
            )
            result = session.run_ps(ps_script)
            return result.status_code, result.std_out.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"WinRM error: {e}")
            return 1, str(e)

    def power_action(self, action: str) -> Tuple[bool, str]:
        cmd_map = {
            "off": "Stop-Computer -Force",
            "reboot": "Restart-Computer -Force",
        }
        ps_cmd = cmd_map.get(action)
        if not ps_cmd:
            return False, f"Unsupported action: {action}"
        rc, out = self.run(ps_cmd)
        ok = (rc == 0)
        msg = out or ("OK" if ok else "NG")
        logger.info(f"[WinRM {self.host}] {action} -> {msg}")
        return ok, msg
    
# ---------- Unified Controller ----------
def power_action_unified(method: str, host: str, user: str, password: str, action: str) -> Tuple[bool, str]:
    """methodに応じてSSH or WinRMを自動選択"""
    if method.upper() == "SSH":
        with SshClient(host, user, password) as cli:
            return cli.power_action(action)
    elif method.upper() in ("API", "WINRM"):  # API=WinRMとする
        client = WinRMClient(host, user, password)
        return client.power_action(action)
    else:
        msg = f"Unsupported method: {method}"
        logger.error(msg)
        return False, msg