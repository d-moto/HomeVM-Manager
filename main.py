from __future__ import annotations
import sys
import re
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QTableWidgetItem, QInputDialog
)
from PyQt5.QtCore import QMetaObject, Qt, QTimer
from PyQt5.QtGui import QColor
from functools import partial

from core.vm_data import VM, load_vm_list, save_vm_list, DATA_FILE
from core.vm_control import send_magic_packet, SshClient, power_action_unified
from core.vm_info import resolve_status
from core.logger import get_logger

logger = get_logger("homevm")

IP_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
MAC_REGEX = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")


class AddVmDialog(QDialog):
    """VM登録ダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VM 追加")
        self.setMinimumWidth(360)

        self.ed_vm_name = QLineEdit(self)
        self.ed_mac = QLineEdit(self)
        self.ed_host_ip = QLineEdit(self)
        self.cb_method = QComboBox(self)
        self.cb_method.addItems(["SSH", "API"])
        self.ed_user = QLineEdit(self)

        form = QFormLayout(self)
        form.addRow("VM名", self.ed_vm_name)
        form.addRow("MACアドレス", self.ed_mac)
        form.addRow("ホストIP（任意）", self.ed_host_ip)
        form.addRow("方式", self.cb_method)
        form.addRow("ユーザー", self.ed_user)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        form.addRow(self.buttons)

        self.ed_host_ip.setPlaceholderText("例: 192.168.0.20（空でも可）")
        self.ed_mac.setPlaceholderText("例: 00:1A:2B:3C:4D:5E")
        self.ed_user.setPlaceholderText("例: root")

        self._vm: VM | None = None

    def _on_accept(self):
        vm_name = self.ed_vm_name.text().strip()
        mac = self.ed_mac.text().strip()
        host_ip = self.ed_host_ip.text().strip() or None
        method = self.cb_method.currentText().strip()
        user = self.ed_user.text().strip()

        if not vm_name:
            QMessageBox.warning(self, "入力エラー", "VM名は必須です。")
            return
        if not MAC_REGEX.match(mac):
            QMessageBox.warning(self, "入力エラー", "MACアドレスの形式が不正です。")
            return
        if host_ip and not IP_REGEX.match(host_ip):
            QMessageBox.warning(self, "入力エラー", "ホストIPの形式が不正です。")
            return
        if not user:
            QMessageBox.warning(self, "入力エラー", "ユーザーは必須です。")
            return

        self._vm = VM(vm_name=vm_name, host_ip=host_ip or "", mac=mac, method=method, user=user)
        self.accept()

    def get_vm(self) -> VM | None:
        return self._vm


class MainWindow(QMainWindow):
    """HomeVM Manager メインウィンドウ"""
    def __init__(self):
        super().__init__()
        ui_path = Path(__file__).resolve().parent / "ui" / "main_window.ui"
        uic.loadUi(str(ui_path), self)

        # --- UI要素取得 ---
        self.table = self.findChild(QtWidgets.QTableWidget, "tableVMs")
        self.btnAdd = self.findChild(QtWidgets.QPushButton, "btnAdd")
        self.btnDelete = self.findChild(QtWidgets.QPushButton, "btnDelete")
        self.btnSave = self.findChild(QtWidgets.QPushButton, "btnSave")
        self.btnReload = self.findChild(QtWidgets.QPushButton, "btnReload")
        self.btnPowerOn  = self.findChild(QtWidgets.QPushButton, "btnPowerOn")
        self.btnPowerOff = self.findChild(QtWidgets.QPushButton, "btnPowerOff")
        self.btnReboot   = self.findChild(QtWidgets.QPushButton, "btnReboot")
        self.btnWOL      = self.findChild(QtWidgets.QPushButton, "btnWOL")
        self.status = self.statusBar()

        # --- 内部状態 ---
        self.vms: List[VM] = []
        self._pass_cache: Dict[str, str] = {}

        # --- イベント接続 ---
        self.btnAdd.clicked.connect(self.on_add)
        self.btnDelete.clicked.connect(self.on_delete)
        self.btnSave.clicked.connect(self.on_save)
        self.btnReload.clicked.connect(self.on_reload)
        if self.btnPowerOn:
            self.btnPowerOn.clicked.connect(lambda: self._do_power("on"))
        if self.btnPowerOff:
            self.btnPowerOff.clicked.connect(lambda: self._do_power("off"))
        if self.btnReboot:
            self.btnReboot.clicked.connect(lambda: self._do_power("reboot"))
        if self.btnWOL:
            self.btnWOL.clicked.connect(self._do_wol)

        # --- 初期ロードとステータス監視 ---
        self.load_and_refresh()
        self.start_status_monitor()

    # ====== データI/O ======
    def load_and_refresh(self):
        self.vms = load_vm_list()
        self.refresh_table()
        self.status.showMessage(f"読み込み完了: {len(self.vms)} 件", 3000)

    def persist(self):
        save_vm_list(self.vms)
        self.status.showMessage(f"保存しました: {DATA_FILE}", 3000)

    # ====== GUI更新 ======
    def refresh_table(self):
        """テーブルを再描画"""
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(self.vms))
        headers = ["VM名", "ホストIP", "MAC", "方式", "ユーザー", "状態"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row, vm in enumerate(self.vms):
            values = [vm.vm_name, vm.host_ip or "-", vm.mac, vm.method, vm.user, "取得中..."]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags())
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    # ====== ボタンハンドラ ======
    def on_add(self):
        dlg = AddVmDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            new_vm = dlg.get_vm()
            if new_vm:
                if any(v.vm_name == new_vm.vm_name for v in self.vms):
                    QMessageBox.warning(self, "重複", f"VM名 '{new_vm.vm_name}' は既に存在します。")
                    return
                self.vms.append(new_vm)
                self.refresh_table()
                logger.info(f"VM added: {new_vm.vm_name}")
                self.status.showMessage(f"追加: {new_vm.vm_name}", 3000)

    def on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "削除", "削除するVMを選択してください。")
            return
        vm_name = self.table.item(row, 0).text() if self.table.item(row, 0) else "(不明)"
        ret = QMessageBox.question(self, "確認", f"選択中のVM '{vm_name}' を削除しますか？")
        if ret == QMessageBox.Yes:
            logger.info(f"VM removed: {vm_name}")
            del self.vms[row]
            self.refresh_table()
            self.status.showMessage(f"削除: {vm_name}", 3000)

    def on_save(self):
        self.persist()

    def on_reload(self):
        self.load_and_refresh()

    # ====== 電源操作 ======
    def _get_password(self, host_ip: str) -> str:
        """SSH接続パスワード取得（キャッシュ）"""
        if host_ip in self._pass_cache:
            return self._pass_cache[host_ip]
        pw, ok = QInputDialog.getText(self, "SSHパスワード入力",
                                      f"{host_ip} のパスワードを入力してください",
                                      echo=QLineEdit.Password)
        if not ok or not pw:
            raise RuntimeError("パスワード未入力")
        self._pass_cache[host_ip] = pw
        return pw

    def _selected_vm(self) -> Optional[VM]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "選択", "操作対象を選択してください。")
            return None
        return self.vms[row]

    def _do_power(self, action: str):
        vm = self._selected_vm()
        if not vm:
            return
        if not vm.host_ip:
            QMessageBox.warning(self, "エラー", "IP未取得のためSSH操作できません。")
            return
        try:
            password = self._get_password(vm.host_ip)
            ok, msg = power_action_unified(vm.method, vm.host_ip, vm.user, password, action)
            if ok:
                QMessageBox.information(self, "成功", f"{vm.vm_name}: {action} 完了\n{msg}")
            else:
                QMessageBox.warning(self, "失敗", f"{vm.vm_name}: {action} 失敗\n{msg}")
        except Exception as e:
            logger.exception("Power action error")
            QMessageBox.critical(self, "エラー", f"操作でエラーが発生しました。\n{e}")


        #     with SshClient(vm.host_ip, vm.user, password) as cli:
        #         ok, msg = cli.power_action(action)
        #     if ok:
        #         QMessageBox.information(self, "成功", f"{vm.vm_name}: {action} 完了\n{msg}")
        #     else:
        #         QMessageBox.warning(self, "失敗", f"{vm.vm_name}: {action} 失敗\n{msg}")
        # except Exception as e:
        #     logger.exception("Power action error")
        #     QMessageBox.critical(self, "エラー", f"SSH操作でエラーが発生しました。\n{e}")

    def _do_wol(self):
        vm = self._selected_vm()
        if not vm:
            return
        try:
            send_magic_packet(vm.mac)
            QMessageBox.information(self, "WOL", f"{vm.vm_name}（{vm.mac}）へ送信しました。")
        except Exception as e:
            logger.exception("WOL error")
            QMessageBox.critical(self, "エラー", f"WOL送信に失敗しました。\n{e}")

    # ====== ステータス監視 ======
    def start_status_monitor(self):
        """バックグラウンドで定期的にMAC→IP→ping確認"""
        def loop():
            while True:
                for i, vm in enumerate(self.vms):
                    try:
                        status, new_ip = resolve_status(vm.mac, getattr(vm, "host_ip", None))
                        vm.host_ip = new_ip or vm.host_ip
                        # Qtのメインスレッドで安全に関数を読み出し
                        # QMetaObject.invokeMethod(
                        #     self,
                        #     "_update_status_row_safe",
                        #     Qt.QueuedConnection,
                        #     # 引数を渡す
                        #     args=[i, status, new_ip or ""]
                        # )

                        # UIスレッドで安全に更新（partialで変数を確定キャプチャ）
                        QTimer.singleShot(
                            0,
                            partial(self._update_status_row, i, status, new_ip)
                        )

                    except Exception as e:
                        logger.error(f"Status check failed: {e}")
                time.sleep(10)  # 10秒間隔でチェック
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _update_status_row(self, row: int, status: str, ip: str):
        """GUI上のテーブル行を更新"""
        try:
            self.table.setItem(row, 1, QTableWidgetItem(ip or "-"))

            item = QTableWidgetItem(status)
            # 状態ごとに色分け
            if status == "稼働中":
                #pass
                item.setBackground(QColor(200, 255, 200))  # 緑
            elif status == "停止中":
                #pass
                item.setBackground(QColor(255, 200, 200))  # 赤
            else:
                #ass
                item.setBackground(QColor(255, 255, 200))  # 黄
            self.table.setItem(row, 5, item)

            logger.info(f"Status updated: {self.vms[row].vm_name} -> {status} ({ip})")
        except Exception as e:
            logger.error(f"UI update failed: {e}")



def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
