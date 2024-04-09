import numcodecs
import numpy as np


item = np.array([(1, 'dataset_1', {'source': '.', 'path': '/dataset_1', 'object_id': None, 'source_object_id': None}),
       (2, 'dataset_2', {'source': '.', 'path': '/dataset_2', 'object_id': None, 'source_object_id': None})],
      dtype=[('id', '<i4'), ('name', 'O'), ('reference', 'O')])
cs = numcodecs.JSON()

en = cs.encode(item)
out=cs.decode(en)
breakpoint()
