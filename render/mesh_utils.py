# -*- coding: utf-8 -*-

# Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V. (MPG) is
# holder of all proprietary rights on this computer program.
# You can only use this computer program if you have closed
# a license agreement with MPG or you get the right to use the computer
# program from someone who is authorized to grant you that right.
# Any use of the computer program without a valid license is prohibited and
# liable to prosecution.
#
# Copyright©2020 Max-Planck-Gesellschaft zur Förderung
# der Wissenschaften e.V. (MPG). acting on behalf of its Max Planck Institute
# for Intelligent Systems. All rights reserved.
#
# Contact: ps-license@tuebingen.mpg.de

import pyrender
import trimesh
import numpy as np
import sys
from render.utils import colors

def get_checkerboard_plane(plane_mins, center=True):
    minx, maxx, miny, maxy = plane_mins
    minz = 0
    gray = [189, 195, 199, 255]
    gray_l = [238, 238, 238, 150]

    verts = [
        [minx, miny, minz],
        [minx, maxy, minz],
        [maxx, maxy, minz],
        [maxx, miny, minz]
    ]
    meshes = []
    radius = max((maxx - minx), (maxy - miny))

    ground = trimesh.primitives.Box(
        # center=[(maxx-minx)/2, (maxy-miny)/2, 0.000001],
        extents=[ (maxx - minx), (maxy - miny),  0.000002]
    )

    # if center:
    #     c = c[0]+(pw/2)-(plane_width/2), c[1]+(pw/2)-(plane_width/2)

    # trans = trimesh.transformations.scale_and_translate(scale=1, translate=[c[0], c[1], 0])
    # ground.apply_translation([c[0], c[1], 0])
    # ground.apply_transform(trimesh.transformations.rotation_matrix(np.rad2deg(-120), direction=[1,0,0]))
    ground.visual.face_colors = gray
    meshes.append(ground)

    # G2
    ground2 = trimesh.primitives.Box(
        # center=[(maxx-minx)/2, (maxy-miny)/2, 0.000001],
        extents=[ 1.6 * (maxx - minx), 1.6 * (maxy - miny), 0.000002]
    )
    ground2.visual.face_colors = gray_l
    meshes.append(ground2)

    return meshes

class MeshViewer(object):

    def __init__(self, width=1200, height=800, add_ground_plane=False,
                 plane_mins=None, use_offscreen=True,
                 bg_color='white'):
        super().__init__()

        self.use_offscreen = use_offscreen
        self.render_wireframe = False
        assert add_ground_plane and plane_mins is not None
        self.mat_constructor = pyrender.MetallicRoughnessMaterial
        self.trimesh_to_pymesh = pyrender.Mesh.from_trimesh

        self.scene = pyrender.Scene(bg_color=colors[bg_color],)
                                    # ambient_light=(0.3, 0.3, 0.3))

        pc = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=float(width) / height)
        camera_pose = np.eye(4)

        rotate=trimesh.transformations.rotation_matrix(np.radians(-30.0),
                                                       [1,0,0])
        camera_pose[:3, 3] = np.array([0, 2, 2.5])

        camera_pose = np.dot(camera_pose, rotate)

        # scene.set_pose(,np.dot(scene.get_pose(nl), rotate))

        # camera_pose[:3, 3] = np.array([0, 0, 2.5])

        self.camera_node = self.scene.add(pc, pose=camera_pose, name='pc-camera')

        self.figsize = (width, height)

        if add_ground_plane:
            ground_mesh = pyrender.Mesh.from_trimesh(get_checkerboard_plane(plane_mins),
                                                     smooth=False)
            pose = trimesh.transformations.rotation_matrix(np.radians(90), [1, 0, 0])
            # pose[:3, 3] = [0, -1, 0]
            self.scene.add(ground_mesh, pose=pose, name='ground_plane')

        if self.use_offscreen:
            self.viewer = pyrender.OffscreenRenderer(*self.figsize)
            self.use_raymond_lighting(5.)
        else:
            self.viewer = pyrender.Viewer(self.scene, use_raymond_lighting=True, viewport_size=self.figsize, cull_faces=False, run_in_thread=True)

    def set_background_color(self, color=colors['white']):
        self.scene.bg_color = color

    def update_camera_pose(self, camera_pose):
        self.scene.set_pose(self.camera_node, pose=camera_pose)

    def close_viewer(self):
        if self.viewer.is_active:
            self.viewer.close_external()

    def set_cam_trans(self, trans= [0, 0, 3.0]):
        if isinstance(trans, list): trans = np.array(trans)
        # trans[2] += 2.8
        self.camera_node.matrix[3, 0 ] += trans[0]
        self.camera_node.matrix[3, 0 ] += trans[2]

        self.camera_node.translation[0] += trans[0]
        self.camera_node.translation[2] += trans[2]

        # camera_pose[:2, 3] += trans[:2] # translate the camera
        self.scene.set_pose(self.camera_node, pose=self.camera_node.matrix)

    def set_meshes(self, meshes, group_name='static', poses=[]):
        for node in self.scene.get_nodes():
            if node.name is not None and '%s-mesh'%group_name in node.name:
                self.scene.remove_node(node)

        if len(poses) < 1:
            for mid, mesh in enumerate(meshes):
                if isinstance(mesh, trimesh.Trimesh):
                    mesh = pyrender.Mesh.from_trimesh(mesh)
                self.scene.add(mesh, '%s-mesh-%2d'%(group_name, mid))
                body_trans = np.array(mesh.centroid)
                self.set_cam_trans()

        else:
            for mid, iter_value in enumerate(zip(meshes, poses)):
                mesh, pose = iter_value
                if isinstance(mesh, trimesh.Trimesh):
                    mesh = pyrender.Mesh.from_trimesh(mesh)
                self.scene.add(mesh, '%s-mesh-%2d'%(group_name, mid), pose)
                self.set_cam_trans()

    def set_static_meshes(self, meshes, poses=[]): self.set_meshes(meshes, group_name='static', poses=poses)
    def set_dynamic_meshes(self, meshes, poses=[]): self.set_meshes(meshes, group_name='dynamic', poses=poses)

    def _add_raymond_light(self):
        from pyrender.light import DirectionalLight
        from pyrender.node import Node

        thetas = np.pi * np.array([0, 2.0 / 6.0, 1.0 / 2.0])
        phis = np.pi * np.array([1.0 / 3.0, 2.0 / 3.0, 1.0 / 2.0])

        nodes = []

        for phi, theta in zip(phis, thetas):
            xp = np.sin(theta) * np.cos(phi)
            yp = np.sin(theta) * np.sin(phi)
            zp = np.cos(theta)

            z = np.array([xp, yp, zp])
            z = z / np.linalg.norm(z)
            x = np.array([-z[1], z[0], 0.0])
            if np.linalg.norm(x) == 0:
                x = np.array([1.0, 0.0, 0.0])
            x = x / np.linalg.norm(x)
            y = np.cross(z, x)

            matrix = np.eye(4)
            matrix[:3, :3] = np.c_[x, y, z]
            nodes.append(Node(
                light=DirectionalLight(color=np.ones(3), intensity=1.0),
                matrix=matrix
            ))
        return nodes

    def use_raymond_lighting(self, intensity = 1.0):
        if not self.use_offscreen:
            sys.stderr.write('Interactive viewer already uses raymond lighting!\n')
            return
        for n in self._add_raymond_light():
            n.light.intensity = intensity / 3.0
            if not self.scene.has_node(n):
                self.scene.add_node(n)#, parent_node=pc)

    def render(self, render_wireframe=None, RGBA=False):
        from pyrender.constants import RenderFlags

        flags = RenderFlags.SHADOWS_DIRECTIONAL
        if RGBA: flags |=  RenderFlags.RGBA
        if render_wireframe is not None and render_wireframe==True:
            flags |= RenderFlags.ALL_WIREFRAME
        elif self.render_wireframe:
            flags |= RenderFlags.ALL_WIREFRAME
        color_img, depth_img = self.viewer.render(self.scene, flags=flags)

        return color_img

class Mesh(trimesh.Trimesh):

    def __init__(self,
                 filename=None,
                 vertices=None,
                 faces=None,
                 vc=None,
                 fc=None,
                 vscale=None,
                 process = False,
                 visual = None,
                 wireframe=False,
                 smooth = False,
                 **kwargs):

        self.wireframe = wireframe
        self.smooth = smooth

        if filename is not None:
            mesh = trimesh.load(filename, process = process)
            vertices = mesh.vertices
            faces= mesh.faces
            visual = mesh.visual
        if vscale is not None:
            vertices = vertices*vscale

        if faces is None:
            mesh = points2sphere(vertices)
            vertices = mesh.vertices
            faces = mesh.faces
            visual = mesh.visual

        super(Mesh, self).__init__(vertices=vertices, faces=faces, process=process, visual=visual)

        if vc is not None:
            self.set_vertex_colors(vc)
        if fc is not None:
            self.set_face_colors(fc)

    def rot_verts(self, vertices, rxyz):
        return np.array(vertices * rxyz.T)

    def colors_like(self,color, array, ids):

        color = np.array(color)

        if color.max() <= 1.:
            color = color * 255
        color = color.astype(np.int8)

        n_color = color.shape[0]
        n_ids = ids.shape[0]

        new_color = np.array(array)
        if n_color <= 4:
            new_color[ids, :n_color] = np.repeat(color[np.newaxis], n_ids, axis=0)
        else:
            new_color[ids, :] = color

        return new_color

    def set_vertex_colors(self,vc, vertex_ids = None):

        all_ids = np.arange(self.vertices.shape[0])
        if vertex_ids is None:
            vertex_ids = all_ids

        vertex_ids = all_ids[vertex_ids]
        new_vc = self.colors_like(vc, self.visual.vertex_colors, vertex_ids)
        self.visual.vertex_colors[:] = new_vc

    def set_face_colors(self,fc, face_ids = None):

        if face_ids is None:
            face_ids = np.arange(self.faces.shape[0])

        new_fc = self.colors_like(fc, self.visual.face_colors, face_ids)
        self.visual.face_colors[:] = new_fc

    @staticmethod
    def concatenate_meshes(meshes):
        return trimesh.util.concatenate(meshes)

def points2sphere(points, radius = .001, vc = [0., 0., 1.], count = [5,5]):

    points = points.reshape(-1,3)
    n_points = points.shape[0]

    spheres = []
    for p in range(n_points):
        sphs = trimesh.creation.uv_sphere(radius=radius, count = count)
        sphs.apply_translation(points[p])
        sphs = Mesh(vertices=sphs.vertices, faces=sphs.faces, vc=vc)

        spheres.append(sphs)

    spheres = Mesh.concatenate_meshes(spheres)
    return spheres