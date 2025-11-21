# 🖥️ HomeVM Manager

[![Python](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](#)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-orange.svg)](#)
[![Web](https://img.shields.io/badge/Web-Flask-green.svg)](#)
[![Package](https://img.shields.io/badge/Package-uv-blue.svg)](https://github.com/astral-sh/uv)

> **LAN上の Windows / Linux マシンを一元管理する GUI / Web ツール**  
> 電源制御・Wake on LAN・状態監視をすべて Python で実現。
> モダンなデスクトップアプリと、GlassmorphismデザインのWeb UIを提供します。

---

## 📘 目次

- [🧩 概要](#-概要)
- [✨ 新機能](#-新機能)
- [🧠 前提条件](#-前提条件)
- [⚙️ セットアップ手順](#️-セットアップ手順)
- [🧰 実行方法（デスクトップ版）](#-実行方法デスクトップ版)
- [🌐 実行方法（Web UI版）](#-実行方法web-ui版)
- [📡 状態監視について](#-状態監視について)
- [📂 ディレクトリ構成](#-ディレクトリ構成)
- [🔧 uv を使った環境構築](#-uv-を使った環境構築)
- [📄 ライセンス / 作者](#-ライセンス--作者)

---

## 🧩 概要

**HomeVM Manager** は、家庭内LAN上に存在する  
**Linux / Windows 仮想マシンおよび物理マシン** を一括管理できるツールです。

| 項目 | 内容 |
|------|------|
| 対応OS | Windows 10/11, Ubuntu / RHEL系 |
| 機能 | 電源操作 / Wake on LAN / 稼働監視 / リモート接続 |
| 通信方式 | SSH（Linux） / WinRM（Windows） |
| GUI | PyQt6 (Cyber Dark Theme) |
| Web UI | Flask + Modern CSS (Glassmorphism) |
| 仮想環境管理 | [uv](https://github.com/astral-sh/uv) |
| 開発言語 | Python 3.14 |

---

## ✨ 新機能

### 1. 🌐 Web UI (Flask)
ブラウザから操作できるモダンなWebインターフェースを追加しました。
- **Glassmorphism**: すりガラス効果を取り入れたCyberpunk風デザイン。
- **Connectボタン**: ワンクリックでSSH接続（Linux）やRDP接続（Windows）を開始できます。
- **レスポンシブ**: スマホやタブレットからも操作可能。

### 2. 🎨 Cyber Dark Theme (Desktop)
デスクトップ版のUIを刷新しました。
- ダークネイビーを基調としたネオンカラーのアクセント。
- 視認性の高いパステルカラーのステータス表示。

### 3. 🔐 セキュアなパスワード保存
- `keyring` ライブラリを使用し、OSのセキュアな領域（Windows Credential Managerなど）にパスワードを保存します。
- 毎回パスワードを入力する手間が省けます。

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
flask = "*"          # Web UI
pyqt6 = "*"          # Desktop GUI
keyring = "*"        # Password Storage
paramiko = "*"       # SSH
pywinrm = "*"        # WinRM
requests-ntlm = "*"  # WinRM Auth
```

---

## 🧰 実行方法（デスクトップ版）

GUI起動：
```bash
uv run python main.py
```

初回起動時：
- `data/vmlist.json` が自動生成されます  
- GUI右上の [追加] ボタンからVMを追加  

| 項目 | 入力例 |
|------|--------|
| VM名 | Win11-ESXiVM |
| ホストIP | 192.168.0.20 |
| MAC | 00:11:22:33:44:55 |
| 接続方式 | SSH / WinRM |
| ユーザー名 | root / localadmin |

---

## 🌐 実行方法（Web UI版）

Webサーバー起動：
```bash
uv run python web/app.py
```

ブラウザでアクセス：
**http://localhost:5000**

機能：
- **Connect**: SSHクライアント起動 / RDPファイルダウンロード
- **Power**: 電源ON(WOL) / OFF / Reboot
- **Add/Delete**: VMの追加・削除

---

## 📡 状態監視について

| 更新周期 | 10秒ごと |
|-----------|-----------|
| 稼働判定 | ICMP (ping) or WinRM接続 |
| DHCP対応 | MACからIP再解決（ARPベース） |
| GUI色分け | 🟩 稼働中 / 🟥 停止中 / 🟨 不明 |

---

## 📂 ディレクトリ構成

```
homevm_manager/
├── main.py                # Desktop App Entry
├── web/                   # Web App
│   ├── app.py             # Flask Backend
│   ├── templates/         # HTML
│   └── static/            # CSS/JS
├── core/                  # Shared Logic
│   ├── vm_control.py      # SSH / WinRM / WOL制御
│   ├── vm_info.py         # 状態取得・MAC→IP解決
│   └── logger.py          # ログ管理
├── data/
│   └── vmlist.json        # VMリスト
├── ui/
│   ├── main_window.ui     # PyQtレイアウト
│   └── style_cyber.qss    # Cyber Theme
├── tests/                 # Unit Tests
└── logs/                  # Logs
```

---

## 🔧 uv を使った環境構築

```bash
uv venv
uv sync
uv run python main.py
```

💡 `uv sync` は `pyproject.toml` を自動的に解析して依存関係を正確にインストールします。

---

## 📄 ライセンス / 作者

| 項目 | 内容 |
|------|------|
| License | MIT License |
| Author | **本井 大智 (Daichi Motoi)** |
| Version | 1.1.0 |
| Created | 2025-11-07 |
| Updated | 2025-11-21 |
| Python | 3.14 (uv仮想環境推奨) |

---

> 🧩 HomeVM Manager — “Your LAN, under control.”  
> ローカルネットワークを、もっとスマートに。
