# 独立検証ハーネスの契約

製品モジュールは repo root `viewpass/`。`viewpass.register()` / `unregister()` があること。`viewpass.capture.capture(context, request: dict) -> dict` を実装する。内部設計は自由だがこの薄い公開テスト境界と製品UIで同じコアを通すこと。request は次を含む：

- `width`, `height`: int
- `view_matrix`, `projection_matrix`: 4x4 の row-major ネストlist（mathutils Matrixに変換可）。明示行列を受け取る（UI側は当該ビューポートから導出）。標準OpenGL風の NDC z -1..1 を契約の入力とし、必要なら backend に変換する。
- `passes`: `['depth', 'normal', 'object_id', 'mask']`
- `context`: Blenderの有効な VIEW_3D / WINDOW region override を持つ。可視性はこの context に従う。

戻り値：`depth` float32 (H,W) 前景正の -view_z、背景NaN; `normal` float32 (H,W,3) 前景符号付きカメラ空間単位法線、背景0; `object_id` uint32 (H,W) 背景0; `mask` bool (H,W); `id_map` dict[int,str]（オブジェクト名、MVPでは同名インスタンス同ID可）。配列はすべて top-left row order。返却後も独立して参照可能であること。

ハーネスは factory startup で生成する自作メッシュを描画。期待値は解析的な位置・距離・法線に基づき、製品関数の出力から導かない。正投影/透視投影、背景、隠れ、遮蔽、面向き、非一様スケール、複数回実行、基本的な非破壊性を検査。テストの適応を行う場合、期待値の独立性とテスト対象の意味を維持。

追加必須テスト（Claudeが実装）：
- pure math: 深度正規化（空/一定/NaN/範囲/反転）、投影、ID encode/decode、ファイル名検証/衝突、metadata。CPU referenceを使う場合は小さな解析ケースと突合。
- GPU: empty scene, local view, collection exclusion, evaluated modifier（位置変化）, collection/geometry instances, negative scale, orthographic/透視実viewport由来行列, camera view, repeated capture, GPU失敗後の再実行, 解像度変更/ワイド/縦長, multi-area。UIと同じ入口を検証する。
- IO: 8/16bit PNG実ビット深度、EXR float精度、ID roundtrip、色管理、背景/上下、衝突、書込権限エラー、複数ファイル失敗。
- packaging: ZIPのインストール/登録解除/再有効化。GUIハーネスが起動できない環境では明示FAIL/未検証。GPUテストをモックに置換しない。

`run.py` は子プロセスが JSON を作り `status=pass` かつ終了コード0の場合のみ合格。BlenderログとJSONを保存。登録テストとGPUテストは別プロセス。ハーネスそのもののテストは `python -m unittest discover -s viewpass-dev/harness -p 'test_*.py'`。
