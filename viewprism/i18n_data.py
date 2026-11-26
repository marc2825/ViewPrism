# SPDX-FileCopyrightText: 2026 marc2825
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations (pure data, no bpy). English is the source language and the default.

NAMES: labels, buttons and messages, registered in the add-on's own context CONTEXT, so they never
change Blender's own UI strings that use the same English words ("Name", "Folder", ...).
TIPS: tooltips (property, enum item and operator descriptions). Blender looks these up in the
default context, so they are registered under both contexts.
Placeholders ({}) must appear in the same number and order in the translation
(tests/pure/test_i18n.py checks this and that every UI string has a translation).
Japanese follows the terms of Blender's own Japanese UI (深度, ノーマル, エクスポート, ...).
"""
CONTEXT = 'ViewPrism'
LOCALES = ('ja_JP', 'ja')

NAMES_JA = {
    # passes
    'Depth': '深度',
    'Normal': 'ノーマル',
    'Object ID': 'オブジェクトID',
    'Mask': 'マスク',
    'Passes': 'パス',
    'no file type': 'ファイル形式なし',
    # size
    'Size': 'サイズ',
    'View': 'ビュー',
    'Custom': 'カスタム',
    'Scale': 'スケール',
    'Width': '幅',
    'Height': '高さ',
    'Keep View Aspect': 'ビューの縦横比を維持',
    'Camera Frame': 'カメラフレーム',
    '{} × {} px': '{} × {} px',
    '(camera frame)': '（カメラフレーム）',
    # depth
    'Depth Settings': '深度の設定',
    'Range': '範囲',
    'Auto': '自動',
    'Fixed': '固定',
    'Near': '手前',
    'Far': '奥',
    'Near is White': '手前を白にする',
    'Background': '背景',
    'Far Colour': '奥の色',
    'Near Colour': '手前の色',
    'Grey Value': 'グレー値',
    'PNG': 'PNG',
    'Off': 'オフ',
    '8-bit': '8 ビット',
    '16-bit': '16 ビット',
    'EXR (exact values)': 'EXR（正確な値）',
    # normal
    'Normal Settings': 'ノーマルの設定',
    'Shading': 'シェーディング',
    'As Shaded': '表示どおり',
    'Flat': 'フラット',
    'Black': '黒',
    'Facing Viewer': '視点向き',
    'PNG Axes': 'PNG の軸',
    'Flip X': 'X を反転',
    'Flip Y': 'Y を反転',
    # object id
    'Object ID Settings': 'オブジェクトIDの設定',
    'One ID per': 'ID の単位',
    'Object': 'オブジェクト',
    'Instancer': 'インスタンス元',
    'Instance': 'インスタンス',
    'PNG (16-bit)': 'PNG（16 ビット）',
    'EXR (32-bit integer)': 'EXR（32 ビット整数）',
    # output
    'Output': '出力',
    'Folder': 'フォルダー',
    'Name': '名前',
    'Numbering': '番号',
    'Add Number': '番号を付ける',
    'Name Only': '名前のみ',
    'Overwrite': '上書き',
    '{} files to {}': '{} ファイル → {}',
    '{} files; Export will ask for a folder': '{} ファイル。保存先はエクスポート時に選びます',
    'replaces': '置き換え',
    'exists': '既存',
    'float': '浮動小数点',
    '32-bit': '32 ビット',
    'metadata': 'メタデータ',
    '{} files already exist. Choose "Add Number", turn on Overwrite or change the name.':
        '同じ名前のファイルが {} 個あります。「番号を付ける」を選ぶか、上書きをオンにするか、名前を変えてください。',
    # output details
    'Output Details': '出力の詳細',
    'EXR Compression': 'EXR 圧縮',
    'ZIP': 'ZIP',
    'None': 'なし',
    'Metadata': 'メタデータ',
    'Write JSON': 'JSON を書き出す',
    'Names': '名前',
    'Object Names': 'オブジェクト名',
    'Anonymized': '匿名化',
    # export buttons and results
    'Export': 'エクスポート',
    'Export 1 Pass': '1 パスをエクスポート',
    'Export {} Passes': '{} パスをエクスポート',
    'Export Passes': 'パスをエクスポート',
    'Export As…': '名前を付けてエクスポート…',
    'Open Output Folder': '出力フォルダーを開く',
    'Last export: {}': '前回のエクスポート: {}',
    '{} more in the Info editor': 'ほか {} 件は情報エディターに表示',
    'Saved {} files as {}_* ({} px, {:.0f} ms).': '{} ファイルを {}_* として保存しました（{} px、{:.0f} ms）。',
    '{} of {} files could not be written ({}).': '{} / {} ファイルを書き込めませんでした（{}）。',
    'ViewPrism: could not write {}: {}': 'ViewPrism: {} を書き込めませんでした: {}',
    '{} files with these names already exist ({}). Choose "Add Number", turn on Overwrite or change the name.':
        '同じ名前のファイルが {} 個あります（{}）。「番号を付ける」を選ぶか、上書きをオンにするか、名前を変えてください。',
    'No file type is selected for {}. Choose PNG or EXR in the settings of that pass.':
        '{} のファイル形式が選ばれていません。そのパスの設定で PNG か EXR を選んでください。',
    'Select at least one pass to export.': 'エクスポートするパスを 1 つ以上選んでください。',
    'Choose an output folder.': '出力フォルダーを選んでください。',
    'The .blend file is not saved, so "//" has no location. Save the file or choose a folder with Export As.':
        '.blend ファイルが未保存のため「//」の場所が決まりません。ファイルを保存するか、'
        '「名前を付けてエクスポート」でフォルダーを選んでください。',
    'Export As must be started from a 3D Viewport.': '「名前を付けてエクスポート」は 3D ビューポートから実行してください。',
    'The output folder does not exist yet. It is created by the first export.':
        '出力フォルダーはまだありません。最初のエクスポートで作られます。',
    # preview
    'Preview': 'プレビュー',
    'Refresh': '更新',
    'Start Preview': 'プレビューを開始',
    'Close': '閉じる',
    'Refresh Preview': 'プレビューを更新',
    'Show Pass': 'パスを表示',
    'Close Preview': 'プレビューを閉じる',
    'Auto Refresh': '自動更新',
    'Thumbnails': 'サムネイル',
    'Opacity': '不透明度',
    'Resolution': '解像度',
    '{} × {} px, {:.0f} ms': '{} × {} px、{:.0f} ms',
    'Preview updating…': 'プレビューを更新中…',
    'Preview outdated: click Refresh or turn on Auto Refresh': 'プレビューが古くなっています。更新するか、自動更新をオンにしてください',
    'Preview: {} (display only)': 'プレビュー: {}（表示のみ）',
    'Auto Refresh stopped: {}': '自動更新を停止しました: {}',
    # menu and defaults
    'ViewPrism': 'ViewPrism',
    'Documentation': '説明書',
    'Save Current Settings as Defaults': '現在の設定を既定値として保存',
    'Load Defaults': '既定値を読み込む',
    'ViewPrism: defaults saved to the preferences': 'ViewPrism: 既定値をプリファレンスに保存しました',
    'The add-on preferences are not available.': 'アドオンのプリファレンスを利用できません。',
    'New sessions start from saved defaults. Settings are never stored in .blend files.':
        '新しいセッションは保存した既定値から始まります。設定は .blend ファイルには保存されません。',
    'Defaults include every panel setting.': '既定値にはパネルのすべての設定が含まれます。',
}

TIPS_JA = {
    # pass enum items
    'Distance from the camera plane': 'カメラ平面からの距離',
    'Surface direction as seen from the camera': 'カメラから見た面の向き',
    'One integer per object': 'オブジェクトごとに 1 つの整数',
    'Foreground (white) and background (black)': '前景（白）と背景（黒）',
    # pass toggles
    'Export the depth pass (distance from the camera plane)': '深度パス（カメラ平面からの距離）を書き出します',
    'Export the normal pass (surface direction as seen from the camera)':
        'ノーマルパス（カメラから見た面の向き）を書き出します',
    'Export the object ID pass (one integer per object)': 'オブジェクトIDパス（オブジェクトごとの整数）を書き出します',
    'Export the foreground mask (white = something, black = nothing)':
        '前景マスク（白 = 物体あり、黒 = なし）を書き出します',
    # size
    'The size of this viewport (or the render resolution in camera view), scaled':
        'このビューポートの大きさ（カメラビューではレンダー解像度）に倍率を掛けたもの',
    'An exact size in pixels; a different aspect ratio crops the view (centred)':
        'ピクセル単位の指定サイズ。縦横比が違う場合はビューの中央を切り出します',
    'Scale applied to the view size': 'ビューの大きさに掛ける倍率',
    'Output width in pixels': '出力の幅（ピクセル）',
    'Output height in pixels': '出力の高さ（ピクセル）',
    'Derive the height from the view aspect ratio': '高さをビューの縦横比から決めます',
    'In camera view, export exactly the camera frame (camera projection, render aspect) instead of the whole '
    'viewport': 'カメラビューでは、ビューポート全体ではなくカメラフレーム（カメラの投影、レンダーの縦横比）を'
                'そのまま書き出します',
    # depth
    'From the nearest to the farthest visible surface': '見えている最も手前の面から最も奥の面まで',
    'Between two distances you enter': '入力した 2 つの距離の間',
    'Distance shown with the near colour': '手前の色で表す距離',
    'Distance shown with the far colour': '奥の色で表す距離',
    'Near surfaces are white (common for depth ControlNets); off: near is black. Applies to the PNG only':
        '手前を白にします（深度 ControlNet で一般的）。オフでは手前が黒になります。PNG のみに適用されます',
    'Empty areas get the far colour': '何もない部分を奥の色にします',
    'Empty areas get the near colour': '何もない部分を手前の色にします',
    'Empty areas get a grey value you choose': '何もない部分を指定したグレー値にします',
    'Grey value of empty areas in the PNG': 'PNG で何もない部分のグレー値',
    'No PNG file for this pass': 'このパスの PNG を書き出しません',
    '256 levels; small files, enough for most image tools': '256 段階。ファイルが小さく、多くの画像ツールで十分です',
    '65,536 levels; smoother gradients, larger files': '65,536 段階。階調が滑らかになり、ファイルは大きくなります',
    'Normalized depth image for image tools': '画像ツール向けに正規化した深度画像',
    'Depth in scene units as 32-bit float (OpenEXR)': 'シーン単位の深度を 32 ビット浮動小数点で保存（OpenEXR）',
    # normal
    'Normals as displayed: smooth/flat shading, auto smooth and custom normals':
        '表示どおりのノーマル（スムーズ／フラットシェーディング、自動スムーズ、カスタムノーマル）',
    'One normal per face': '面ごとに 1 つのノーマル',
    'RGB (0, 0, 0)': 'RGB (0, 0, 0)',
    'RGB (0.5, 0.5, 1.0): the colour of a normal pointing at the viewer':
        'RGB (0.5, 0.5, 1.0): 視点の方を向いたノーマルの色',
    'Store -X in the normal PNG (some tools expect a mirrored X axis). EXR stays canonical':
        'ノーマル PNG に -X を書き込みます（X 軸が反転した形式を求めるツール向け）。EXR は変わりません',
    'Store -Y in the normal PNG (DirectX-style green channel). EXR stays canonical':
        'ノーマル PNG に -Y を書き込みます（DirectX 形式の緑チャンネル）。EXR は変わりません',
    'Normal map image for image tools': '画像ツール向けのノーマルマップ画像',
    'Signed normals as 32-bit float (OpenEXR)': '符号付きのノーマルを 32 ビット浮動小数点で保存（OpenEXR）',
    # object id
    'One ID per source object (instances share it)': '元のオブジェクトごとに 1 つの ID（インスタンスは同じ ID）',
    'One ID per object in the view layer (a collection instance is one ID)':
        'ビューレイヤー内のオブジェクトごとに 1 つの ID（コレクションインスタンスは 1 つの ID）',
    'One ID per individual instance': 'インスタンスごとに 1 つの ID',
    '16-bit PNG, pixel value = ID (IDs up to 65,535)': '16 ビット PNG。画素値 = ID（65,535 まで）',
    '32-bit unsigned integer EXR channel (any number of IDs)': '32 ビット符号なし整数の EXR チャンネル（ID の数に制限なし）',
    # output
    'Lossless, smaller files': '可逆圧縮。ファイルが小さくなります',
    'Uncompressed, faster to write': '無圧縮。書き込みが速くなります',
    'Object and camera names in the ID map and warnings': 'ID 対応表と警告にオブジェクト名とカメラ名を書きます',
    'Neutral labels (object_1, ...) instead of object and camera names; IDs, images and camera matrices are '
    'unchanged': 'オブジェクト名とカメラ名の代わりに中立的なラベル（object_1 など）を書きます。'
                 'ID・画像・カメラ行列は変わりません',
    'Write <name>_meta.json (matrices, depth range, ID map, warnings)':
        '<名前>_meta.json（行列、深度の範囲、ID 対応表、警告）を書き出します',
    'Output folder ("//" means: next to the saved .blend file)': '出力フォルダー（「//」は保存済みの .blend ファイルと同じ場所）',
    'Start of every file name': 'すべてのファイル名の先頭',
    'Add the next free number (never overwrites)': '空いている次の番号を付けます（上書きしません）',
    'Use the name as is': '名前をそのまま使います',
    'With "Name Only": replace existing files of the same name': '「名前のみ」のとき、同じ名前の既存ファイルを置き換えます',
    # preview
    'Opacity of the large preview': '大きいプレビューの不透明度',
    'Preview resolution relative to the viewport': 'ビューポートに対するプレビューの解像度',
    'Capture the preview again once the view and the scene stop changing':
        'ビューとシーンの変化が止まったら、プレビューを取り直します',
    'Show small images of all four passes in the corner of the viewport':
        '4 つのパスすべての小さな画像をビューポートの隅に表示します',
    # operators
    'Capture the selected passes from this 3D viewport and save them to the output folder. Nothing in the '
    'scene is changed': 'この 3D ビューポートから選んだパスを取り込み、出力フォルダーに保存します。'
                        'シーンは一切変更しません',
    'Choose a folder and base name, then export the selected passes from this viewport':
        'フォルダーと名前を選んでから、このビューポートの選んだパスを書き出します',
    'Capture the preview again from this viewport (display only, nothing is saved)':
        'このビューポートからプレビューを取り直します（表示のみで、何も保存しません）',
    'Show this pass over the viewport (display only). Click again to hide it; the thumbnails stay':
        'このパスをビューポートに重ねて表示します（表示のみ）。もう一度押すと隠れます。サムネイルは残ります',
    'Remove the preview and the thumbnails from the viewport and free their memory':
        'プレビューとサムネイルをビューポートから消し、メモリを解放します',
    'Open the output folder in the file manager': '出力フォルダーをファイルマネージャーで開きます',
    'Store the current settings in the add-on preferences; new sessions start from them':
        '現在の設定をアドオンのプリファレンスに保存します。新しいセッションはこの設定から始まります',
    'Reset the current settings to the saved defaults': '現在の設定を保存済みの既定値に戻します',
}


def table():
    """Dictionary in the form bpy.app.translations.register() expects."""
    ja = {(CONTEXT, k): v for k, v in NAMES_JA.items()}
    for k, v in TIPS_JA.items():
        ja[('*', k)] = v
        ja[(CONTEXT, k)] = v
    return {locale: ja for locale in LOCALES}
