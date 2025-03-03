import gpu
import numpy as np

def render_depth(context, width, height):
    """
    GPUオフスクリーンレンダリングを用いて、
    指定幅・高さで現在の3Dビューの深度バッファを取得する。
    """
    offscreen = gpu.types.GPUOffScreen(width, height)
    depth_data = None
    try:
        with offscreen.bind():
            # ビューポートの設定
            bgl.glViewport(0, 0, width, height)
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)

            # 3Dビューのregion_3dがあればその行列を利用
            region_3d = context.space_data.region_3d if hasattr(context.space_data, "region_3d") else None
            if region_3d:
                proj_matrix = region_3d.perspective_matrix
                view_matrix = region_3d.view_matrix

                bgl.glMatrixMode(bgl.GL_PROJECTION)
                bgl.glLoadMatrixf(proj_matrix.transposed())
                bgl.glMatrixMode(bgl.GL_MODELVIEW)
                bgl.glLoadMatrixf(view_matrix.transposed())
            else:
                # fallback: 単位行列
                bgl.glMatrixMode(bgl.GL_PROJECTION)
                bgl.glLoadIdentity()
                bgl.glMatrixMode(bgl.GL_MODELVIEW)
                bgl.glLoadIdentity()

            # 簡易的に、表示されているMeshオブジェクトのみを描画
            for obj in context.visible_objects:
                if obj.type == 'MESH':
                    bgl.glPushMatrix()
                    # オブジェクトのワールド変換を適用
                    bgl.glMultMatrixf(obj.matrix_world.transposed())
                    mesh = obj.to_mesh()
                    if mesh:
                        bgl.glBegin(bgl.GL_TRIANGLES)
                        for poly in mesh.polygons:
                            for loop_index in poly.loop_indices:
                                vert_index = mesh.loops[loop_index].vertex_index
                                vertex = mesh.vertices[vert_index].co
                                bgl.glVertex3f(*vertex)
                        bgl.glEnd()
                        obj.to_mesh_clear()
                    bgl.glPopMatrix()

            # 深度バッファの読み込み
            buffer = bgl.Buffer(bgl.GL_FLOAT, width * height)
            bgl.glReadPixels(0, 0, width, height, bgl.GL_DEPTH_COMPONENT, bgl.GL_FLOAT, buffer)
            depth_data = np.array(buffer, dtype=np.float32).reshape(height, width)
    except Exception as e:
        print("render_depthでエラーが発生しました:", e)
    finally:
        offscreen.free()

    return depth_data
