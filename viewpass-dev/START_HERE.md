# ViewPass 開発スターター（Claude Code 用）

既存の `marc2825/Depth_Renderer` を発展させるための補助ファイル。これはアドオン本体ではなく、開発指示・検証契約・独立テストのセットです。既存ファイルを上書きしないよう、この `viewpass-dev/` ディレクトリをリポジトリ直下にコピーしてください。

## 使い方（Windows推奨）
1. 既存リポジトリを clone（既にローカルにあれば不要）。作業ツリーが clean か確認し、変更があれば勝手に破棄しない。
2. `viewpass-dev/` をコピー。`git status` を確認。
3. Windows の Claude Code をリポジトリルートで起動し、`PROMPT.md` の内容を渡すか、下の指示を送る。

```
Read viewpass-dev/PROMPT.md and every file it references. Implement the project in this existing repository. Follow the stage gates, preserve the independent harness, run actual tests where available, and report evidence and blockers in Japanese.
```

WSL でコード編集してもよいが、GPU検証はWindows上のBlenderで実行する。WSLからWindowsプロセスを呼ぶ場合は `wslpath -w` 等でパスを変換し、GUIセッション・GPUバックエンドを確認。Windows側にcloneしてPowerShellで実行するのが簡単。

## ハーネス（本体実装後）
Python 3.10+ と Blender 4.5 LTS / 5.x を用意。PowerShell例：

```powershell
python viewpass-dev/harness/run.py --blender 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe' --mode all
python viewpass-dev/harness/run.py --blender 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --mode all
```

インストール済みの実パスに変更。`--mode background` は登録だけ、`--mode gpu` は別の Blender GUI を起動するためデスクトップセッションが必要。`--timeout 180` などで変更可。GPUテストは起動時の一時シーンを使用し、作業中の .blend は開かない。テスト終了時にそのBlenderを閉じる。

成果物は既定で OS の一時フォルダ内 `viewpass-harness-*`。各実行の `background.log` / `gpu.log` と JSON 結果を確認。結果がない・timeout・skip は成功ではない。`--out` で新規出力ディレクトリ指定可。

本スターターでは Blender 本体がない環境のため、実GPU動作は未確認。実装前のテスト失敗は想定通り。ハーネスを製品に合わせる際、テストの意味・独立期待値を弱めないこと。
