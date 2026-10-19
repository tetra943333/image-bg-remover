人物切り抜きツール Python GUI版

【対応環境】
・Windows 10/11
・macOS
・Python 3.11～3.13（Windowsでは3.12推奨）

【Windows 初回】
1. Python 3.12をインストール（Add python.exe to PATHを有効化）
   https://www.python.org/downloads/
2. setup_windows.bat をダブルクリック
3. 完了後、start_windows.bat をダブルクリック

【Mac 初回】
1. Python 3.11～3.13を用意
2. ターミナルで展開先へ移動
3. chmod +x setup_mac.command start_mac.command
4. ./setup_mac.command
5. 以降は ./start_mac.command

【操作】
1. 複数画像をドラッグ＆ドロップ、または「画像追加」
2. 出力先を確認
3. モデルを選択
   ・人物優先: 人物写真向け
   ・一般被写体: 人物以外も対象
   ・高速・軽量: 速度優先
4. 「背景除去を開始」

【仕様】
・元画像は変更しません
・出力名: 元ファイル名_transparent.png
・同名がある場合は _2、_3 を付加します
・1枚失敗しても残りを継続します
・処理は別スレッドで実行し、GUIを固めません
・初回はAIモデルを自動ダウンロードします
・画像処理自体はローカルで実行します

【注意】
・「人物優先」でも、人物の持ち物や近接物が残る場合があります
・境界精密化は品質が改善する場合がありますが、処理時間が増えます
・HEICは標準では対象外です。iPhone画像はJPEG/PNGへ変換してください
・初回モデル取得にはインターネット接続が必要です
