import subprocess
import re
import platform
import ipaddress
from typing import Optional, Tuple
from .logger import get_logger

logger = get_logger("homevm")

def get_ip_from_mac(mac: str) -> Optional[str]:
    """
    ARPテーブルからMACに対応するIPを取得する
    Windows/Linux対応
    """
    mac = mac.lower()
    cmd = ["arp", "-a"]
    try:
        output = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"ARP取得失敗: {e}")
        return None

    pattern = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([\da-fA-F:-]{17})", re.I)
    for line in output.splitlines():
        m = pattern.search(line)
        if m:
            ip, found_mac = m.group(1), m.group(2).lower().replace("-", ":")
            if mac == found_mac:
                return ip
    return None


def is_host_alive(ip: str, timeout: int = 1) -> bool:
    """
    pingでホスト生存確認
    """
    system = platform.system().lower()
    cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip] if "windows" in system else \
          ["ping", "-c", "1", "-W", str(timeout), ip]
    try:
        subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        logger.error(f"ping失敗: {e}")
        return False


def resolve_status(mac: str, last_ip: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    MACをキーに現在のIPと稼働状態を取得する
    戻り値: (status, new_ip)
    """
    ip = get_ip_from_mac(mac) or last_ip
    if not ip:
        return ("不明", None)

    alive = is_host_alive(ip)
    if alive:
        return ("稼働中", ip)
    else:
        return ("停止中", ip)
