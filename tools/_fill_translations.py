"""一次性脚本：给 lupdate 提取的 37 条新文案填 en_US / ja_JP 翻译。"""
import html
import re

TRANSLATIONS = {
    "警告": ("Warning", "警告"),
    "当前版本仍在测试中，可能包含错误或未完成的功能。欢迎到 <a href=\"%1\">GitHub</a> 上提交 Issue。": (
        "This version is still in testing and may contain bugs or unfinished features. "
        "Feel free to file an issue on <a href=\"%1\">GitHub</a>.",
        "現在のバージョンはまだテスト中のため、不具合や未実装の機能が含まれる可能性があります。"
        "<a href=\"%1\">GitHub</a> への Issue 報告を歓迎します。"),
    "GitHub": ("GitHub", "GitHub"),
    "反馈问题或功能建议": ("Report issues or suggest features", "問題の報告・機能の提案"),
    "检测到更新。": ("Update available.", "更新があります。"),
    "您已更新到最新版本。": ("You're up to date.", "最新バージョンです。"),
    "检查更新失败。": ("Failed to check for updates.", "更新の確認に失敗しました。"),
    "尚未检查更新。": ("No update check yet.", "まだ更新を確認していません。"),
    "稳定版": ("Stable", "安定版"),
    "正式发布的版本，经过完整测试。": (
        "Officially released builds with full testing.",
        "十分にテストされた、正式リリースのバージョンです。"),
    "预览版": ("Preview", "プレビュー版"),
    "包含最新的功能与修复，但可能不稳定。": (
        "Newest features and fixes, but may be unstable.",
        "最新の機能と修正を含みますが、不安定な場合があります。"),
    "未找到当前版本的更新日志。": (
        "No changelog found for the current version.",
        "現在のバージョンの更新履歴が見つかりません。"),
    "关闭": ("Close", "閉じる"),
    "发现新版本：%1": ("New version available: %1", "新しいバージョン：%1"),
    "上次检查更新时间：%1": ("Last checked: %1", "前回の更新確認：%1"),
    "从未": ("never", "なし"),
    "更新时发生错误，请检查您的网络连接并重试。": (
        "Something went wrong while checking for updates. "
        "Please check your network connection and try again.",
        "更新中にエラーが発生しました。ネットワーク接続を確認して、もう一度お試しください。"),
    "更新部署尚未实现": ("Update deployment not yet available", "更新の適用は未実装です"),
    "下载与安装更新的环节还没有接入，目前只能检查更新。可以前往 <a href=\"%1\">GitHub Releases</a> 手动下载新版本。": (
        "Downloading and installing updates is not wired up yet; for now the app can "
        "only check for updates. You can grab new versions manually from "
        "<a href=\"%1\">GitHub Releases</a>.",
        "更新のダウンロードとインストールはまだ実装されていないため、現在は更新の確認のみ可能です。"
        "新しいバージョンは <a href=\"%1\">GitHub Releases</a> から手動でダウンロードできます。"),
    "下载并安装": ("Download and install", "ダウンロードしてインストール"),
    "正在检查更新…": ("Checking for updates…", "更新を確認しています…"),
    "更新日志": ("Changelog", "更新履歴"),
    "更新设置": ("Update settings", "更新設定"),
    "检查没能完成，稍后再试一次吧。": (
        "The check didn't finish — please try again later.",
        "確認を完了できませんでした。しばらくしてからもう一度お試しください。"),
    "真棒，您已更新到最新版本！": (
        "Nice — you're on the latest version!",
        "すばらしい！最新バージョンです！"),
    "查看更新日志": ("View changelog", "更新履歴を見る"),
    "更新模式": ("Update mode", "更新モード"),
    "设置应用的更新模式。": (
        "Set how the app handles updates.", "アプリの更新方法を設定します。"),
    "从不自动更新": ("Never check automatically", "自動更新しない"),
    "自动检查更新并通知": ("Check automatically and notify", "自動で確認して通知"),
    "自动检查更新并下载": ("Check automatically and download", "自動で確認してダウンロード"),
    "自动检查更新并安装": ("Check automatically and install", "自動で確認してインストール"),
    "更新通道": ("Update channel", "更新チャネル"),
    "控制应用的更新目标版本。版本的发行节奏和稳定程度因更新通道而异，部分通道可能包含不稳定的功能，请谨慎使用。": (
        "Choose which builds the app updates to. Release cadence and stability vary by "
        "channel; some channels may include unstable features — use with care.",
        "アプリが更新先とするバージョンを選択します。チャネルによってリリースの頻度や安定性が異なり、"
        "不安定な機能が含まれる場合があります。注意してご使用ください。"),
    "强制检查更新": ("Force check for updates", "更新の強制確認"),
    "强制将应用更新到当前通道上的最新版本，即使此版本比应用当前版本更旧。": (
        "Update to the latest build on the current channel even if it is older than "
        "the running version.",
        "現在のバージョンより古い場合でも、現在のチャネルの最新バージョンへ強制的に更新します。"),
}


def xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\"", "&quot;"))


for lang in ("en_US", "ja_JP"):
    path = f"translations/luminalium_{lang}.ts"
    text = open(path, encoding="utf-8").read()
    missing = []

    def fill(match: re.Match) -> str:
        block = match.group(0)
        raw = re.search(r"<source>(.*?)</source>", block, re.S).group(1)
        source = html.unescape(raw)
        pair = TRANSLATIONS.get(source)
        if pair is None:
            missing.append(source)
            return block
        value = pair[0] if lang == "en_US" else pair[1]
        return re.sub(r"<translation type=\"unfinished\">.*?</translation>",
                      lambda _: "<translation>" + xml_escape(value) + "</translation>",
                      block, flags=re.S)

    text = re.sub(r"<message>.*?</message>", fill, text, flags=re.S)
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    print(lang, "剩余未翻译:", len(missing), missing[:5])
