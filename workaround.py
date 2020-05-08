analysis_idx = 0


import csv
from os import path
from System.IO import FileStream, FileMode
from System.Runtime.Serialization.Formatters.Binary import BinaryFormatter

analysis = ExtAPI.DataModel.Project.Model.Analyses[analysis_idx]

esupports = analysis.GetLoadObjects("ElasticFoundation")

for support in esupports:
    comp_file = path.join(
        analysis.WorkingDir,
        support.Properties['nodeFile'].Value)

    with FileStream(comp_file, FileMode.Open) as nstream:
        formatter = BinaryFormatter()
        nodes = formatter.Deserialize(nstream)

    csv_outfile = path.join(
        analysis.WorkingDir,
        support.Caption.strip() + '.csv')
    
    with open(csv_outfile, 'wb') as rfile:
        writer = csv.writer(rfile)
        writer.writerow(['Set', 'Fx', 'Fy', 'Fz', 'Total'])
        with analysis.GetResultsData() as reader:
            for step, time in enumerate(reader.ListTimeFreq):
                reader.CurrentResultSet = step + 1
                forces = reader.GetResult('F')
                fx = fy = fz = 0.0
                for k in nodes.Keys:
                    node = nodes[k]
                    nfx, nfy, nfz = forces.GetNodeValues(node)
                    fx += nfx
                    fy += nfy
                    fz += nfz
                total = sqrt(fx**2 + fy**2 + fz**2)
                writer.writerow([step + 1, fx, fy, fz, total])
