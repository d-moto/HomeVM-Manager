import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

# Mock keyring before importing main
sys.modules["keyring"] = MagicMock()

from main import MainWindow, AddVmDialog

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication instance (needed for QWidgets)
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_mainwindow_init(self):
        """メインウィンドウが正常に初期化されるか"""
        # Mocking file I/O to avoid reading real config
        with patch("main.load_vm_list", return_value=[]):
            window = MainWindow()
            self.assertIsNotNone(window)
            self.assertEqual(window.table.rowCount(), 0)
            
            # Check if style is loaded (Cyber theme)
            # Note: We can't easily check the actual visual style, but we can check no error occurred
            
    def test_add_dialog(self):
        """追加ダイアログの初期化とバリデーション"""
        dlg = AddVmDialog()
        self.assertIsNotNone(dlg)
        
        # Check default items
        self.assertEqual(dlg.cb_method.count(), 2)
        self.assertEqual(dlg.cb_method.itemText(1), "WinRM") # Changed from API
        
    def test_password_logic(self):
        """パスワード取得ロジックのテスト (Mock Keyring)"""
        import keyring
        
        with patch("main.load_vm_list", return_value=[]):
            window = MainWindow()
            
            # Case 1: Keyring has password
            keyring.get_password.return_value = "secret123"
            pw = window._get_password("192.168.1.100")
            self.assertEqual(pw, "secret123")
            keyring.get_password.assert_called_with("HomeVM-Manager", "192.168.1.100")
            
            # Case 2: Keyring empty, ask user (Mock InputDialog)
            keyring.get_password.return_value = None
            with patch("PyQt6.QtWidgets.QInputDialog.getText", return_value=("newpass", True)):
                pw = window._get_password("192.168.1.101")
                self.assertEqual(pw, "newpass")
                # Should save to keyring
                keyring.set_password.assert_called_with("HomeVM-Manager", "192.168.1.101", "newpass")

if __name__ == "__main__":
    unittest.main()
