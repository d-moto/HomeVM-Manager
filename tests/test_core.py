import unittest
import sys
import os
from pathlib import Path
import json
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.vm_data import VM, load_vm_list, save_vm_list

class TestVMCore(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for data
        self.test_dir = tempfile.mkdtemp()
        self.data_file = Path(self.test_dir) / "vmlist.json"
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_vm_model(self):
        """VMモデルの生成と辞書変換テスト"""
        vm = VM(vm_name="TestVM", host_ip="192.168.1.1", mac="00:11:22:33:44:55", 
                method="SSH", user="root", type="virtual")
        
        d = vm.to_dict()
        self.assertEqual(d["vm_name"], "TestVM")
        self.assertEqual(d["type"], "virtual")
        
        vm2 = VM.from_dict(d)
        self.assertEqual(vm, vm2)

    def test_save_and_load(self):
        """データの保存と読み込みテスト"""
        vms = [
            VM("VM1", "1.1.1.1", "00:00:00:00:00:01", "SSH", "user1"),
            VM("VM2", "2.2.2.2", "00:00:00:00:00:02", "WinRM", "user2", "physical")
        ]
        
        save_vm_list(vms, self.data_file)
        
        self.assertTrue(self.data_file.exists())
        
        loaded = load_vm_list(self.data_file)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].vm_name, "VM1")
        self.assertEqual(loaded[1].method, "WinRM")
        self.assertEqual(loaded[1].type, "physical")

    def test_load_empty(self):
        """空ファイルからの読み込みテスト"""
        # ファイルがない場合
        loaded = load_vm_list(self.data_file)
        self.assertEqual(loaded, [])
        self.assertTrue(self.data_file.exists()) # 自動生成されるはず

if __name__ == "__main__":
    unittest.main()
