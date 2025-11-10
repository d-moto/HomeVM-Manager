# 🖥️ HomeVM Manager

[![Python](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-PyQt5-orange.svg)](#)
[![Package](https://img.shields.io/badge/Package-uv-blue.svg)](https://github.com/astral-sh/uv)

> **LAN上の Windows / Linux マシンを一元管理する GUI ツール**  
> 電源制御・Wake on LAN・状態監視をすべて Python + PyQt5 で実現。

---

## 📘 目次

- [🧩 概要](#-概要)
- [🧠 前提条件](#-前提条件)
- [⚙️ セットアップ手順](#️-セットアップ手順)
- [🧰 実行方法](#-実行方法)
- [📡 状態監視について](#-状態監視について)
- [🧾 ログ出力](#-ログ出力)
- [📂 ディレクトリ構成](#-ディレクトリ構成)
- [🔧 uv を使った環境構築](#-uv-を使った環境構築)
- [🚀 今後の拡張予定](#-今後の拡張予定)
- [📄 ライセンス / 作者](#-ライセンス--作者)

---

## 🧩 概要

**HomeVM Manager** は、家庭内LAN上に存在する  
**Linux / Windows 仮想マシンおよび物理マシン** をGUIで一括管理できるツールです。

| 項目 | 内容 |
|------|------|
| 対応OS | Windows 10/11, Ubuntu / RHEL系 |
| 機能 | 電源操作 / Wake on LAN / 稼働監視 |
| 通信方式 | SSH（Linux） / WinRM（Windows） |
| GUI | PyQt5 |
| 仮想環境管理 | [uv](https://github.com/astral-sh/uv) |
| 開発言語 | Python 3.14 |

---

## 🧠 前提条件

### 🪟 Windows（管理対象）

<details>
<summary>WinRM 有効化手順</summary>

```powershell
Enable-PSRemoting -Force
Set-Item WSMan:\localhost\Service\Auth\Basic -Value $true
Set-Item WSMan:\localhost\Service\AllowUnencrypted -Value $true
Restart-Service WinRM
```

Ping 応答許可：
```powershell
netsh advfirewall firewall add rule name="ICMP Allow" protocol=icmpv4:8,any dir=in action=allow
```

推奨ユーザー作成：
```powershell
net user localadmin RootPass123! /add
net localgroup administrators localadmin /add
```

</details>

---

### 🐧 Linux（管理対象）

<details>
<summary>SSH 設定確認</summary>

```bash
sudo systemctl enable sshd --now
sudo ufw allow ssh
```

Wake on LAN を使用する場合：
- BIOSで「Wake on LAN」を有効化
- `ethtool eth0` で `Wake-on: g` を確認
</details>

---

### 💻 管理端末（ツール実行側）

| 必須項目 | バージョン / 条件 |
|-----------|------------------|
| Python | 3.14 |
| uv | 最新版 (`pip install uv`) |
| ネットワーク | 対象マシンと同一LAN内 |

---

## ⚙️ セットアップ手順

### 1️⃣ プロジェクト取得
```bash
git clone https://github.com/yourname/homevm-manager.git
cd homevm-manager
```

### 2️⃣ 仮想環境作成（uv）
```bash
uv venv
uv sync
```

### 3️⃣ 依存ライブラリ
`pyproject.toml` に以下を含みます：

```toml
[dependencies]
PyQt5 = "*"
paramiko = "*"
pywinrm = "*"
requests-ntlm = "*"    # WinRM (NTLM) 認証に必要
```

---

## 🧰 実行方法

GUI起動：
```bash
uv run python main.py
```

初回起動時：
- `data/vmlist.json` が自動生成されます  
- GUI右上の [登録] ボタンからVMを追加  

| 項目 | 入力例 |
|------|--------|
| VM名 | Win11-ESXiVM |
| ホストIP | 192.168.0.20 |
| MAC | 00:11:22:33:44:55 |
| 接続方式 | SSH / API |
| ユーザー名 | root / localadmin |

---

## 📡 状態監視について

| 更新周期 | 10秒ごと |
|-----------|-----------|
| 稼働判定 | ICMP (ping) or WinRM接続 |
| DHCP対応 | MACからIP再解決（ARPベース） |
| GUI色分け | 🟩 稼働中 / 🟥 停止中 / 🟨 不明 |

---

## 🧾 ログ出力

ログは `logs/YYYYMMDD.log` に出力されます。

```
[2025-11-07 11:38:03] [INFO] Status updated: RHEL9.4 -> 稼働中 (192.168.24.194)
[2025-11-07 20:05:02] [INFO] [WinRM 192.168.24.220] reboot -> OK
```

---

## 📂 ディレクトリ構成

```
homevm_manager/
├── main.py                # GUI起動スクリプト
├── core/
│   ├── vm_control.py      # SSH / WinRM / WOL制御
│   ├── vm_info.py         # 状態取得・MAC→IP解決
│   └── logger.py          # ログ管理
├── data/
│   └── vmlist.json        # VMリスト
├── ui/
│   └── main_window.ui     # PyQtレイアウト
└── logs/
    └── 20251107.log
```

---

## 🔧 uv を使った環境構築

```bash
uv venv
uv sync
uv run python main.py
```

💡 `uv sync` は `requirements.txt` / `pyproject.toml` を自動的に解析して  
依存関係を正確にインストールします。

---

## 🚀 今後の拡張予定

- 🕒 状態最終更新時刻のGUI表示  
- 🔐 SSH鍵認証 / WinRM資格情報暗号化保存  
- 📡 LANスキャンによる自動検出  
- 🌐 WebUI（Flask）版  
- 🧠 スマート通知（Slack / LINE Notify）

---

## 📄 ライセンス / 作者

| 項目 | 内容 |
|------|------|
| License | MIT License |
| Author | **本井 大智 (Daichi Motoi)** |
| Version | 1.0.0 |
| Created | 2025-11-07 |
| Python | 3.14 (uv仮想環境推奨) |

---

## 💬 Tips

```powershell
# WinRM通信確認（管理端末→Windows）
winrs -r:192.168.24.220 -u:localadmin -p:RootPass123! "hostname"

# SSH通信確認（管理端末→Linux）
ssh root@192.168.0.30 hostname
```

---

> 🧩 HomeVM Manager — “Your LAN, under control.”  
> ローカルネットワークを、もっとスマートに。
