from __future__ import annotations
import sys
import re
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable


import keyring
from functools import partial
from datetime import datetime

from core.vm_data import VM, load_vm_list, save_vm_list, DATA_FILE
from core.vm_control import send_magic_packet, SshClient, power_action_unified
from core.vm_info import resolve_status
from core.logger import get_logger

from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QTableWidgetItem, QInputDialog
)
from PyQt6.QtCore import QMetaObject, Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QIcon



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
        self.cb_method.addItems(["SSH", "WinRM"])
        self.cb_type = QComboBox(self)
        self.cb_type.addItems(["virtual", "physical"])  # ← 種別選択を追加
        self.ed_user = QLineEdit(self)

        form = QFormLayout(self)
        form.addRow("VM名", self.ed_vm_name)
        form.addRow("MACアドレス", self.ed_mac)
        form.addRow("ホストIP（任意）", self.ed_host_ip)
        form.addRow("方式", self.cb_method)
        form.addRow("ユーザー", self.ed_user)
        form.addRow("種別", self.cb_type)

        #self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.buttons = QDialogButtonBox(
    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
)
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

        vm_type = self.cb_type.currentText().strip()
        self._vm = VM(vm_name=vm_name, host_ip=host_ip or "", mac=mac, method=method, user=user, type=vm_type)
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

        # --- ツールバー作成 ---
        self.setup_toolbar()

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
        self.table.horizontalHeader().sectionClicked.connect(self.on_table_sort)
        self.start_status_monitor()

        # --- ウィンドウ設定 ---
        style_path = Path(__file__).resolve().parent / "ui" / "style_cyber.qss"
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

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
        headers = ["VM名", "ホストIP", "MAC", "方式", "ユーザー", "種別", "状態", "最終更新"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row, vm in enumerate(self.vms):
            # API -> WinRM 表記ゆれ吸収
            method_disp = "WinRM" if vm.method.upper() in ("API", "WINRM") else vm.method

            values = [vm.vm_name, vm.host_ip or "-", vm.mac, method_disp, vm.user, vm.type, "取得中...", "-"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags())
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    # ====== ボタンハンドラ ======
    def on_add(self):
        dlg = AddVmDialog(self)
        #if dlg.exec_() == QDialog.Accepted:
        if dlg.exec() == QDialog.DialogCode.Accepted:
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
        #if ret == QMessageBox.Yes:
        if ret == QMessageBox.StandardButton.Yes:
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
        """SSH/WinRM接続パスワード取得（keyring -> キャッシュ -> 入力）"""
        # 1. メモリキャッシュ確認
        if host_ip in self._pass_cache:
            return self._pass_cache[host_ip]
        
        # 2. keyring確認
        try:
            saved_pw = keyring.get_password("HomeVM-Manager", host_ip)
            if saved_pw:
                self._pass_cache[host_ip] = saved_pw
                return saved_pw
        except Exception as e:
            logger.warning(f"Keyring access failed: {e}")

        # 3. 入力ダイアログ
        pw, ok = QInputDialog.getText(
            self,
            "パスワード入力",
            f"{host_ip} のパスワードを入力してください\n(OSのセキュア領域に保存されます)",
            echo=QLineEdit.EchoMode.Password
            )
        if not ok or not pw:
            raise RuntimeError("パスワード未入力")
        
        # 保存
        self._pass_cache[host_ip] = pw
        try:
            keyring.set_password("HomeVM-Manager", host_ip, pw)
        except Exception as e:
            logger.error(f"Failed to save password to keyring: {e}")

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
        
        if vm.type != "physical":
            QMessageBox.information(self, "WOL無効", f"{vm.vm_name} は仮想マシンのためWOLをサポートしません。")
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
                item.setBackground(QColor(166, 227, 161))  # Pastel Green
                item.setForeground(QColor(30, 30, 46))     # Dark Text
            elif status == "停止中":
                #pass
                item.setBackground(QColor(243, 139, 168))  # Pastel Red
                item.setForeground(QColor(30, 30, 46))     # Dark Text
            else:
                #ass
                item.setBackground(QColor(249, 226, 175))  # Pastel Yellow
                item.setForeground(QColor(30, 30, 46))     # Dark Text
            self.table.setItem(row, 6, item)

            # 最終更新時刻
            now_str = datetime.now().strftime("%H:%M:%S")
            self.table.setItem(row, 7, QTableWidgetItem(now_str))

            logger.info(f"Status updated: {self.vms[row].vm_name} -> {status} ({ip})")
        except Exception as e:
            logger.error(f"UI update failed: {e}")

    def setup_toolbar(self):
        """上部ツールバーの作成と旧ボタンの非表示"""

        toolbar = QtWidgets.QToolBar("MainToolbar", self)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # --- アクション作成 ---
        act_reload = toolbar.addAction("更新")
        #act_power_on = toolbar.addAction("電源ON")
        act_power_off = toolbar.addAction("電源OFF")
        act_reboot = toolbar.addAction("再起動")
        act_wol = toolbar.addAction("WOL")
        toolbar.addSeparator()
        act_add = toolbar.addAction("追加")
        act_delete = toolbar.addAction("削除")
        act_save = toolbar.addAction("保存")

        # --- シグナル接続（既存のハンドラを使う） ---
        act_reload.triggered.connect(self.on_reload)
        #act_power_on.triggered.connect(lambda: self._do_power("on"))
        act_power_off.triggered.connect(lambda: self._do_power("off"))
        act_reboot.triggered.connect(lambda: self._do_power("reboot"))
        act_wol.triggered.connect(self._do_wol)
        act_add.triggered.connect(self.on_add)
        act_delete.triggered.connect(self.on_delete)
        act_save.triggered.connect(self.on_save)

        # --- 既存のボタンは非表示にする（レイアウト崩れ防止） ---
        for btn in (
            self.btnAdd, self.btnDelete, self.btnSave,
            self.btnReload, self.btnPowerOn, self.btnPowerOff,
            self.btnReboot, self.btnWOL
        ):
            if btn is not None:
                btn.hide()
    
    def on_table_sort(self, column_index):
        """テーブルのソート後に内部データを同期"""
        # 列インデックスとVM属性の対応
        COL_MAP = {
            0: "vm_name",
            1: "host_ip",
            2: "mac",
            3: "method",
            4: "user"
        }

        key_name = COL_MAP.get(column_index)
        if not key_name:
            return

        # ソート（昇順／降順はQTableWidgetの設定に合わせてもよい）
        self.vms.sort(key=lambda vm: getattr(vm, key_name) or "")
        self.refresh_table()






def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    #return app.exec_()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
