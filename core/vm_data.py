from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List
import json
from pathlib import Path

# 既定のデータファイルパス（プロジェクト相対）
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "vmlist.json"

@dataclass
class VM:
    vm_name:str
    host_ip: str
    mac: str
    method: str # "SSH" or "WinRM"
    user: str
    type: str = "virtual" # "virtual" or "physical"

    @staticmethod
    def from_dict(d: dict) -> "VM":
        return VM(
            vm_name = d.get("vm_name", ""),
            host_ip = d.get("host_ip", ""),
            mac = d.get("mac", ""),
            method = d.get("method", ""),
            user = d.get("user", ""),
            type = d.get("type", "virtual"),
        )
    
    def to_dict(self) -> dict:
        return asdict(self)
    
def ensure_data_file(path: Path = DATA_FILE) -> None:
    """data/ フォルダと JSON ファイルを初期化"""
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")

def load_vm_list(path: Path = DATA_FILE) -> List[VM]:
    """JSON から VM リストロード"""
    ensure_data_file(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        vms = [VM.from_dict(x) for x in raw]

        # typeが空のものは自動補完
        for vm in vms:
            if not getattr(vm, "type", None):
                vm.type = "virtual"
        return vms
    except Exception:
        # 壊れた場合はバックアップし、空配列で復旧
        bak = path.with_suffix(".json.bak")
        try:
            path.replace(bak)
        except Exception:
            pass
        path.write_text("[]", encoding="utf-8")
        return []
    
def save_vm_list(vms: List[VM], path: Path = DATA_FILE) -> None:
    """VM リストを JSON に保存（整形して書き出し）"""
    ensure_data_file(path)
    data = [vm.to_dict() for vm in vms]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")