# Blender Extensions 申請手順（オーナー用）

対象: ViewPrism **0.2.0**。extensions.blender.org での無料頒布です。
状態: **準備完了・未申請。** v0.2.0 は 2026-11-27 に GitHub でプレリリース済みです（公開 ZIP でのインストール〜アンインストール検証済み）。申請は、オーナーがこのページの確認を終えてから自分で行います。
掲載用の文章・画像・審査への回答案は [`EXTENSION_LISTING.md`](EXTENSION_LISTING.md) にまとめています（英語、そのまま貼り付け可）。

## 1. 使用する ZIP

- GitHub Releases の **v0.2.0** に添付された `viewprism-0.2.0.zip` を使います。
  https://github.com/marc2825/ViewPrism/releases/tag/v0.2.0
- 同じリリースの `viewprism-0.2.0.zip.sha256` と一致することを確認してください。
  - 公開時に確認した値: `c644f1cbbcb88f856e93ea3a95384a07b7ddf4fab910cea2d03c7c167c54738d`
  - Windows: `certutil -hashfile viewprism-0.2.0.zip SHA256`
- ZIP はタグ `v0.2.0` から CI（`.github/workflows/release.yml`）で作られています。作成時に次を通過済みです。
  - Blender 5.3 の `extension validate`
  - 同梱ファイル監査（アドオン本体と `LICENSE` のみ）
  - 個人情報・認証情報スキャン
- 手元で作り直した ZIP は使わないでください。審査対象とリリースの中身がずれるためです。

## 2. 申請前にオーナーが確認すること（約 20 分）

実際のプロジェクトで、Blender 4.5 LTS と 5.3 のどちらか（できれば両方）を使って確認します。
結果は issue #9 にチェックを付けて記録してください。

1. **インストール**: Edit › Preferences › Get Extensions › 右上 ⌄ › **Install from Disk…** で上記 ZIP を入れる。
   - 有効化・無効化・削除がエラーなくできること。
2. **書き出し**: 保存済みの .blend で N パネル › ViewPrism › **Export Passes**。
   - `//viewprism/` に PNG/EXR/JSON ができること。
   - 同じ操作をもう一度すると、上書きせずに番号が進むこと（Numbering が既定の Auto Number のとき）。
3. **Export As…**: ファイルブラウザで保存できること。キャンセルしても何も書かれないこと。
4. **プレビュー**: Depth / Normal / Object ID / Mask を切り替えて表示できること。
   - Auto Refresh を入れて重めのシーンで視点を回したとき、操作がカクつかず、止まってから更新されること。
5. **複数ビュー**: 2 つの 3D ビューで角度を変え、各ビューから書き出すと、それぞれの視点になること。
6. **外部アプリでの読み込み**: 普段使うツールで PNG と EXR が開けること。
   - 例: 画像ビューア、Krita/GIMP、Nuke、ComfyUI。
7. **シーンを変えないこと**: Edit › Undo History に ViewPrism の項目がないこと。
   - カメラ・マテリアル・選択・フレームも変わっていないこと。
8. **パネルの分かりやすさ**: 分かりにくい表示があればメモする。

問題があれば申請を止めて issue に記録してください。修正後は 0.2.1 として出し直します。

## 3. 申請手順

画面の文言は変わることがあります。表示に合わせて読み替えてください。

1. https://extensions.blender.org/ に **Blender ID** でログインする（初回は利用規約に同意）。
2. **Upload Extension**（拡張機能のアップロード）を開き、`viewprism-0.2.0.zip` をアップロードする。
   - ZIP 内の `blender_manifest.toml` が検証され、次の項目が自動で入ります: 名前、id `viewprism`、バージョン、タグライン、タグ、ライセンス、権限、Website。
   - id `viewprism` は、アップロードした時点で予約されます。
3. 作成された**ドラフト**の編集画面で、次を登録する。
   - **Description**: `EXTENSION_LISTING.md` の「Description」の Markdown をそのまま貼る。
   - **Icon**（必須）: `branding/viewprism-icon-256.png`
   - **Featured image**（必須）: `branding/viewprism-featured-1920x1080.png`
   - **Previews**: `docs/images/ui_preview_normal.png`、`docs/images/ui_panel.png`、`docs/images/passes_grid.png`（任意で `ui_preview_depth.png`）。
   - 画像の推奨サイズ・形式はアップロード画面の表示に従ってください。
     - 用意した画像: アイコン 256×256、featured 1920×1080、プレビュー約 16:9、いずれも PNG。
     - 一度アップロードした画像は、プラットフォーム上で再利用できません。
   - Support / Issue tracker の欄があれば `https://github.com/marc2825/ViewPrism/issues` を入れる。
4. プレビュー表示で内容を確認し、**審査に提出**（Submit for review / approval）する。
5. 審査はモデレーターによる手動確認です。コメントは審査キューのページとメールに届きます。
   - よく聞かれる点（権限の理由、通信の有無、同梱モジュール）への回答案は `EXTENSION_LISTING.md` の末尾にあります。
   - 修正を求められたら、文章を直すか新しいバージョンの ZIP を上げて再提出します。
6. 承認されると公開され、Blender の Get Extensions からも検索・インストールできるようになります。

### 公開後

- 新しいバージョンを出すとき:
  - `version` を上げて GitHub でタグを打ち、リリースの ZIP を同じ拡張ページの「新しいバージョンをアップロード」から上げる。
  - 手順は CONTRIBUTING.md の「Releasing」を参照。
- 不具合報告は GitHub の issue で受け付けます（リポジトリは公開済み）。

## 4. 未検証の環境（掲載文にも明記済み）

全環境の検証は公開の必須条件にしません（オーナー判断、2026-11-26）。掲載文には次のように書いています。

- 検証済み:
  - Blender 4.5 LTS / 5.0 / 5.1 / 5.2 / 5.3
  - Windows 11 + NVIDIA（Vulkan・OpenGL）
  - Linux + Mesa ソフトウェア OpenGL（CI）
  - Windows + Blender 4.5 / 5.3 のバックグラウンド検証（CI）
- **未検証**:
  - macOS（Metal）
  - AMD・Intel GPU
  - ハードウェア GPU ドライバの Linux
  - GPU 付き Windows での Blender 4.5
- 根拠と再現方法: [`QA_REPORT.md`](QA_REPORT.md)。追跡: issue #9。

## 5. 申請前チェックリスト

- [ ] §2 の確認を終え、issue #9 に記録した。
- [ ] `viewprism-0.2.0.zip` の SHA-256 が GitHub リリースの `.sha256` と一致する。
- [ ] 掲載文（`EXTENSION_LISTING.md`）を読み、内容に同意できる。
- [ ] アイコン・featured・プレビュー画像を確認した。
- [ ] 名称 ViewPrism の継続を確認した（`NAMING.md`。正式な商標クリアランスは未実施）。
