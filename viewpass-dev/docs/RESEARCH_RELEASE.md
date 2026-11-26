# 競合・名称・配布前調査

以下は調査開始点であって網羅済みの結論ではない。URL、確認日、版/更新日、ライセンス、対象OS/Blender版、価格（確認できる場合）、現在視点/カメラ/非破壊/プレビュー/パス/精度/出力/操作数を比較。READMEの主張と実動作を分け、未知は未知と記録する。

- Blender標準 Z/Mist/Compositor: https://docs.blender.org/manual/en/latest/render/layers/passes.html
- https://github.com/PLAN8VR/Depth_Map
- https://github.com/Limbicnation/Blender-Depth-Map-Generator
- https://github.com/x6ud/controlnet-render-blender-addon
- https://github.com/carson-katri/dream-textures
- https://superhivemarket.com/products/sdwebuitools
- Blender Extensions, Superhive, Gumroad, BOOTH, GitHub で viewport pass export / viewport depth / multi-pass / normal map / render passes / ControlNet 等を追加検索。特にカメラ不要方式の競合を探す。
- ViewPass / Viewport Pass Exporter / PassSnap 等の名称・extension IDを検索。商標はJ-PlatPat等の対象国公式DBを必要に応じて確認。検索は法的クリアランスではない。公開承認前に決定しない。

## 公式技術資料（2026-11-26確認）
- BGL削除: https://developer.blender.org/docs/release_notes/5.0/python_api/
- GPU API 4.5: https://docs.blender.org/api/4.5/gpu.types.html
- GPU API 5.2: https://docs.blender.org/api/5.2/gpu.types.html
- Extension manifest: https://developer.blender.org/docs/features/extensions/schema/1.0.0/
- 最新リリース/公開条件は実行時に公式で再確認: https://www.blender.org/download/ , https://extensions.blender.org/

## 比較実験
同じ自作シーン、同じ解像度と視点、同じパス意味で標準機能/競合と比較。インストールからの操作数と毎回の操作数を区別。cold/warm 各5回以上、median/p95（少数なら参考値）、GPU描画/readback/encode/save/全体時間、OS/GPU/driver/backend/Blender、頂点/三角形/オブジェクト数、解像度、試行数を保存。GPU非同期の測定誤差を記録。比較対象の方式が違う場合は無理に速度倍率を出さない。簡単なシーンと複雑なシーン（手続き生成、第三者素材不要）で行う。

## 公開前
- ライセンス候補GPL-3.0-or-later（公式Extensionsの現行規則を確認、ユーザー承認後に選択）。依存、コード由来、素材、画像、名称、特許リスクを棚卸し。正式法務確認ではない。
- `memo.txt` 等のローカルパス/個人情報、Git履歴、ログ、設定、画像、シークレット、外部通信をチェック。履歴の書換えが必要なら承認を得る。
- manifestのid/名前/maintainer/版/最小Blender/permissions（files用途を明記）を確認。ZIPはアドオンのみ。`blender --command extension build` / `validate` の引数は実版のhelpで確認し、結果を保存。
- 初回は無料OSSとしての需要検証を優先。販売の判断は利用者フィードバック、競合優位性、保守コストを見てから。正式公開、登録、宣伝、価格決定は依頼主の承認後。
