"""Analytic fixture, independent of product projection and rendering implementation."""
import math
import time

import bpy
import numpy as np

W, H = 320, 240


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def plane(name, center, half, slope=0.0, scale=(1, 1, 1)):
    hx, hy = half
    verts = [(x, y, slope*x) for x, y in [(-hx,-hy), (hx,-hy), (hx,hy), (-hx,hy)]]
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], [(0,1,2,3)])
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = center
    ob.scale = scale
    return ob


def fixture(context):
    # This process is a factory-startup sandbox; never run on a working .blend.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    plane('VP_front', (-.55,.35,-2), (.5,.35))
    plane('VP_back', (-.35,.35,-4), (.8,.7))
    plane('VP_tilt', (.95,-.35,-3), (.25,.28), slope=.4, scale=(1.3, .8, .7))
    hidden = plane('VP_hidden', (0,-.75,-1), (.15,.1))
    hidden.hide_set(True)
    context.view_layer.update()


def matrices(mode):
    view = np.eye(4, dtype=np.float64)
    n, f = .1, 20.
    aspect = W/H
    if mode == 'perspective':
        # vertical fov 90°, camera at origin looking down -Z
        proj = np.array([[1/aspect,0,0,0],[0,1,0,0],
                         [0,0,-(f+n)/(f-n),-2*f*n/(f-n)],[0,0,-1,0]], dtype=float)
    else:
        # vertical span 3 units
        proj = np.array([[1/(1.5*aspect),0,0,0],[0,1/1.5,0,0],
                         [0,0,-2/(f-n),-(f+n)/(f-n)],[0,0,0,1]], dtype=float)
    return view, proj


def pixel(point, projection):
    clip = projection @ np.array([*point,1.])
    x, y = clip[:2]/clip[3]
    col, row = int((x+1)*W/2), int((1-y)*H/2)
    check(0 <= row < H and 0 <= col < W, 'fixture sample outside image')
    return row,col


def snapshot(context):
    s = context.scene
    return (tuple(sorted((o.name, tuple(v for row in o.matrix_world for v in row), o.hide_get())
                         for o in s.objects)),
            tuple(sorted(o.name for o in context.selected_objects)),
            context.view_layer.objects.active.name if context.view_layer.objects.active else None,
            context.mode, s.frame_current, s.camera.name if s.camera else None,
            s.render.engine, s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage,
            tuple(sorted((b.name, len(b.nodes)) for b in bpy.data.node_groups)),
            tuple(sorted(m.name for m in bpy.data.materials)),
            tuple(sorted(i.name for i in bpy.data.images)),
            tuple(sorted(m.name for m in bpy.data.meshes)),
            tuple(sorted(c.name for c in bpy.data.cameras)))


def run_cases(context, capture):
    fixture(context)
    baseline = snapshot(context)
    results = []
    for mode in ('perspective','orthographic'):
        view, projection = matrices(mode)
        req = dict(width=W,height=H,view_matrix=view.tolist(),projection_matrix=projection.tolist(),
                   passes=['depth','normal','object_id','mask'])
        previous = None
        for trial in range(2):
            t0 = time.perf_counter()
            result = capture(context, req)
            seconds = time.perf_counter()-t0
            d,n,i,m = (np.asarray(result[k]) for k in ('depth','normal','object_id','mask'))
            for arr,shape,dtype in [(d,(H,W),np.float32),(n,(H,W,3),np.float32),
                                    (i,(H,W),np.uint32),(m,(H,W),np.bool_)]:
                check(arr.shape == shape and arr.dtype == dtype, f'{mode}: shape/dtype {arr.shape}/{arr.dtype}')
            check(m.any() and (~m).any(), 'must contain foreground and background')
            check(np.array_equal(m,i>0), 'ID/mask mismatch')
            check(np.array_equal(m,np.isfinite(d)), 'depth/mask mismatch')
            check(np.isnan(d[~m]).all() and (n[~m]==0).all(), 'background encoding')
            check((d[m]>0).all(), 'foreground depth must be positive')
            check(np.allclose(np.linalg.norm(n[m],axis=-1),1,atol=2e-3), 'normal lengths')
            names = result['id_map']
            check(all(int(k) in names for k in np.unique(i[m])), 'ID mapping incomplete')
            # Front sample is inside both planes in perspective (nearest must win).
            for name,point,expected in [('VP_front',(-.55,.35,-2),2.),('VP_back',(.2,.35,-4),4.),('VP_tilt',(.95,-.35,-3),3.)]:
                y,x = pixel(point,projection)
                check(m[y,x] and names.get(int(i[y,x]))==name, f'{mode}: wrong visible ID at {name}')
                check(abs(float(d[y,x])-expected)<.025, f'{mode}: depth {name} {d[y,x]} != {expected}')
                normal = np.array([-.4*.7/1.3,0,1]) if name=='VP_tilt' else np.array([0,0,1.])
                normal = normal/np.linalg.norm(normal)
                check(np.allclose(n[y,x],normal,atol=.005), f'{mode}: normal {name} {n[y,x]}')
            y,x=pixel((0,-.75,-1),projection)
            check(not m[y,x], 'hidden object leaked or background incorrect')
            check('VP_hidden' not in [names[int(k)] for k in np.unique(i[m])], 'hidden object visible')
            check(not m[5,5], 'corner background expected')
            check(snapshot(context)==baseline, 'scene/datablock state changed')
            if previous is not None:
                arrays, ids = previous
                for k,arr in zip(('depth','normal','object_id','mask'),(d,n,i,m)):
                    check(np.array_equal(arr,arrays[k],equal_nan=True), f'{mode}: nondeterministic {k}')
                check(ids==names, 'ID map changed on repeat')
                # Verify first capture still owns valid arrays (not mutated by second capture).
                for k in arrays:
                    check(np.array_equal(np.asarray(first_result[k]),arrays[k],equal_nan=True), f'first result mutated: {k}')
            else:
                first_result = result
                previous = ({k:np.array(result[k],copy=True) for k in ('depth','normal','object_id','mask')}, dict(names))
            results.append({'projection':mode,'trial':trial+1,'seconds':seconds,'checks':'analytic samples, alignment, background, visibility, state, repeat'})
    return results
