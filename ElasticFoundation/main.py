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

import csv
from os import path
from System.IO import FileStream, FileMode
from System.Runtime.Serialization.Formatters.Binary import BinaryFormatter

import ansys
from units import ConvertUnitToSolverConsistentUnit as solver_unit
from units import ConvertToSolverConsistentUnit as to_solve_unit
import Ansys.Core.Units as AnsUnits


def validexp(load, prop):
    x = 29
    y = 10
    z = 75
    try:
        value = float(eval(prop.Value))
        return True
    except:
        pass
    return False

def addunitsys(load, prop):
    prop.Options.Clear()
    rejects = ['DS_','EXD_','AD_', 'Custom']
    for unitname in AnsUnits.UnitsManager.GetUnitSystemNames():
        if not any([reject in unitname for reject in rejects]):
            prop.Options.Add(unitname)

def wrapper_gen_springs(load, solver_data, stream):
    '''
    Workaround to call pre commands from object class
    '''
    load.Controller.gen_springs(solver_data, stream)


def wrapper_get_reaction(result, stepInfo, collector):
    '''
    Workaround to call pre commands from object class
    '''
    ExtAPI.Log.WriteError("Wrapper")

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
        stream.WriteLine('(1i9,3e18.9e3)')
        factor = self.api.Application.InvokeUIThread(
            lambda: solver_unit(self.api, 1.0, mesh.Unit, 'Length', self.load.Analysis))

        post_data = SerializableDictionary[int, int]()

        for node_id, cnode_id in zip(node_ids, cnode_ids):
            post_data[node_id] = cnode_id
            pos = [
                x * factor
                for x in (
                    mesh.NodeById(node_id).X,
                    mesh.NodeById(node_id).Y,
                    mesh.NodeById(node_id).Z)]
            stream.WriteLine('{0:9d}{1:18.9e}{2:18.9e}{3:18.9e}'
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

        self.load.Properties['nodeFile'].Value = comp_ref_name + '.bin'
        with FileStream(self.load.Properties['nodeFile'].Value, FileMode.Create) as nstream:
            formatter = BinaryFormatter()
            formatter.Serialize(nstream, post_data)


class SelectElasticFoundation():
    # pylint: disable=no-self-use
    def __init__(self, api, entity, prop):
        self.api = api

    def get_elastic_foundations(self, obj):
        # pylint: disable=broad-except
        # pylint: disable=unused-variable
        # pylint: disable=bare-except
        results = []
        analysis = obj.Analysis
        for child in analysis.GetLoadObjects(self.api.ExtensionManager.CurrentExtension):
            results.append(child)
        return results

    def getvalue(self, obj, prop, val):
        if val is None:
            return None
        results = self.get_elastic_foundations(obj)
        for res in results:
            if res.Id == int(val):
                return res
        return None

    def onactivate(self, obj, prop):
        prop.Options.Clear()
        results = self.get_elastic_foundations(obj)
        for res in results:
            prop.Options.Add(str(res.Id))

    def value2string(self, obj, prop, val):
        result = None
        if val is not None:
            results = self.get_elastic_foundations(obj)
            for res in results:
                if res.Id == int(val):
                    result = res
                    break
        if result is None:
            return ''
        return result.Caption

    def isvalid(self, obj, prop):
        return prop.Value is not None


class ElasticFoundationReaction():
    '''
    Get Reaction
    '''
    # pylint: disable=missing-docstring
    def __init__(self, extApi, result):
        self.api = extApi
        self.result = None
        self.steps_completed = []

    def oninit(self, result):
        self.result = result
        self.steps_completed = []

    def oncleardata(self, result):
        self.steps_completed = []

    def evaluate(self, result, step_info, collector):
        inf = float("inf")
        load = self.result.Properties['ElasticFoundationObj'].Value
        comp_file = path.join(
            ExtAPI.Application.InvokeUIThread(lambda: self.result.Analysis.WorkingDir),
            load.Properties['nodeFile'].Value)

        with FileStream(comp_file, FileMode.Open) as nstream:
            formatter = BinaryFormatter()
            nodes = formatter.Deserialize(nstream)

        csv_outfile = path.join(
            ExtAPI.Application.InvokeUIThread(lambda: self.result.Analysis.WorkingDir),
            self.result.Caption.strip() + '.csv')
        with open(csv_outfile, 'wb' if step_info.Set == 1 else 'ab' ) as rfile:
            writer = csv.writer(rfile)
            if not self.steps_completed:
                writer.writerow(['Set', 'Fx', 'Fy', 'Fz', 'Total'])
            with ExtAPI.Application.InvokeUIThread(lambda: self.result.Analysis.GetResultsData()) as reader:
                reader.CurrentResultSet = step_info.Set
                forces = reader.GetResult('F')
                fx = fy = fz = 0.0
                for k in nodes.Keys:
                    node = nodes[k]
                    nfx, nfy, nfz = forces.GetNodeValues(node)
                    fx += nfx
                    fy += nfy
                    fz += nfz
                    collector.SetValues(k, (nfx, nfy, nfz))
                self.result.Properties['ReactSummary/x'].Value = fx
                self.result.Properties['ReactSummary/y'].Value = fy
                self.result.Properties['ReactSummary/z'].Value = fz
                total = sqrt(fx**2 + fy**2 + fz**2)
                self.result.Properties['ReactSummary/total'].Value = total
                if step_info.Set not in self.steps_completed:
                    writer.writerow([step_info.Set, fx, fy, fz, total])
                    self.steps_completed.append(step_info.Set)
