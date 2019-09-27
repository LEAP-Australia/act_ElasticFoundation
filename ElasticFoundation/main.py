"""
main.py

Copyright 2019 LEAP Australia Pty Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Author:
    Nish Joseph

Discription:
    ACT to define 1-D springs with directionally varying stifness.
"""

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=import-error
# pylint: disable=too-many-locals
# pylint: disable=bare-except

from System.IO import StreamWriter

import ansys
from units import ConvertUnitToSolverConsistentUnit as solver_unit
from units import ConvertToSolverConsistentUnit as to_solve_unit

def wrapper_gen_springs(load, solver_data, stream):
    '''
    Workaround to call pre commands from object class
    '''
    load.Controller.gen_springs(solver_data, stream)


class ElasticFoundation():
    '''
    Elastic function load object
    '''
    # pylint: disable=missing-docstring
    def __init__(self, api, load):
        self.api = api
        self.load = None

    def oninit(self, load):
        self.load = load
        if load.Properties['id'].Value < 0:
            max_id = max([
                x.Properties['id'].Value
                for x in load.Analysis.GetLoadObjects(load.Extension.UniqueId)])
            load.Properties['id'].Value = max_id + 1

    def gen_springs(self, solver_data, stream):
        # pylint: disable=too-many-statements
        stream.WriteLine(
            "/com,*********** Elastic Foundation - {0} ***********"
            .format(self.load.Properties['id'].Value))
        et_x = solver_data.GetNewElementType()
        et_y = solver_data.GetNewElementType()
        et_z = solver_data.GetNewElementType()

        mesh = self.load.Analysis.MeshData

        # Get Node Ids
        node_ids = []
        for geo_id in self.load.Properties['Geometry'].Value.Ids:
            node_ids += mesh.MeshRegionById(geo_id).NodeIds

        node_ids = list(set(node_ids))

        #Gen Coincident nodes
        cnode_ids = [int(solver_data.GetNewNodeId()) for x in node_ids]
        node_count = len(cnode_ids)

        stream.WriteLine('nblock, 3, , {0}'.format(len(cnode_ids)))
        stream.WriteLine('(1i9,3e25.16e3)')
        factor = self.api.Application.InvokeUIThread(
            lambda: solver_unit(self.api, 1.0, mesh.Unit, 'Length', self.load.Analysis))

        for node_id, cnode_id in zip(node_ids, cnode_ids):
            pos = [
                x * factor
                for x in (
                    mesh.NodeById(node_id).X,
                    mesh.NodeById(node_id).Y,
                    mesh.NodeById(node_id).Z)]
            stream.WriteLine('{0:9d}{1:25.16e}{2:25.16e}{3:25.16e}'
                             .format(cnode_id, *pos))
        stream.WriteLine('-1')

        # Check to see if using Name Selection
        if self.load.Properties['Geometry/DefineBy'].Value == 'Named Selection':
            comp_mob_name = self.load.Properties['Geometry'].Value.Name
        else:
            comp_mob_name = 'elasfound_targ_{0}'.format(self.load.Properties['id'].Value)
            ansys.createNodeComponent(
                node_ids,
                comp_mob_name,
                mesh,
                stream,
                fromGeoIds=False)

        comp_ref_name = 'elasfound_ref_{0}'.format(self.load.Properties['id'].Value)
        ansys.createNodeComponent(
            cnode_ids,
            comp_ref_name,
            mesh,
            stream,
            fromGeoIds=False)

        factor = self.api.Application.InvokeUIThread(
            lambda: to_solve_unit(self.api, 1.0, 'Stiffness', self.load.Analysis))

        stream.WriteLine('ET, {0}, COMBIN14, 0, 1, 0'.format(et_x))
        stream.WriteLine(
            'R, {0},{1:25.16e},{2:25.16e}'
            .format(
                et_x,
                self.load.Properties['SpringDef/xStiff'].Value/node_count*factor,
                self.load.Properties['SpringDef/Damping/xDamp'].Value
                if self.load.Properties['SpringDef/Damping/xDamp'].Value
                else 0.0))
        stream.WriteLine()

        stream.WriteLine('ET, {0}, COMBIN14, 0, 2, 0'.format(et_y))
        stream.WriteLine(
            'R, {0},{1:25.16e},{2:25.16e}'
            .format(
                et_y,
                self.load.Properties['SpringDef/yStiff'].Value/node_count*factor,
                self.load.Properties['SpringDef/Damping/yDamp'].Value
                if self.load.Properties['SpringDef/Damping/yDamp'].Value
                else 0.0))
        stream.WriteLine()

        stream.WriteLine('ET, {0}, COMBIN14, 0, 3, 0'.format(et_z))
        stream.WriteLine(
            'R, {0},{1:25.16e},{2:25.16e}'
            .format(
                et_z,
                self.load.Properties['SpringDef/zStiff'].Value/node_count*factor,
                self.load.Properties['SpringDef/Damping/zDamp'].Value
                if self.load.Properties['SpringDef/Damping/zDamp'].Value
                else 0.0))
        stream.WriteLine()

        stream.WriteLine('CMSEL, S, {0}'.format(comp_mob_name))
        stream.WriteLine('CMSEL, A, {0}'.format(comp_ref_name))
        stream.WriteLine('CSYS, {0}'.format(
            self.api.Application.InvokeUIThread(
                lambda: self.load.Properties['SpringDef/cs'].Value.CoordinateSystemID)))
        stream.WriteLine('NROTAT, ALL')
        stream.WriteLine('ALLSELL, ALL')
        stream.WriteLine()

        stream.WriteLine('EBLOCK,19,SOLID')
        stream.WriteLine('(19i9)')
        line = '{0:9d}' * 4 + '{1:9d}' * 4 + '{2:9d}{3:9d}{4:9d}{5:9d}{6:9d}'
        for e_num in [et_x, et_y, et_z]:
            for node_id, cnode_id in zip(node_ids, cnode_ids):
                stream.WriteLine(line.format(
                    int(e_num),
                    0,
                    2,
                    0,
                    int(solver_data.GetNewElementId()),
                    cnode_id,
                    node_id))
        stream.WriteLine('-1')
        stream.WriteLine('D, {0}, ALL, 0.0'.format(comp_ref_name))

        self.load.Properties['nodeFile'].Value = comp_ref_name + '.dat'
        node_stream = StreamWriter(self.load.Properties['nodeFile'].Value)
        ansys.createNodeComponent(
            cnode_ids,
            comp_ref_name,
            mesh,
            node_stream,
            fromGeoIds=False)
        node_stream.Close()
