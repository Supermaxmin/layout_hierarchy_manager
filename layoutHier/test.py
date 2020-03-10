import os
import time
import unittest
import klayout.db as db

from layoutHier import  SArrayManager, PArrayManager, HierarchyManager
from layoutHier.utils.helpers import shapes_save


class ArrayManagerTest(unittest.TestCase):

	def setUp(self):
		filename="testcase2.gds"
		readFile = os.path.join('.', 'layout', 'gds', 'array', filename)
		self.writeDir = os.path.join('.', 'layout', 'out', 'array')
		layout = db.Layout()
		layout.read(readFile)
		self.cell = layout.top_cell()
		self.layout = layout
		self.name = filename.split('.')[0]

	def test_SArrayManager(self):
		layer = self.layout.layer_indexes()[0]
		manager = SArrayManager.rbtrees_build(self.layout, layer)
		manager.simple_array_form()
		regions = manager.visualize()
		shapes_save(regions, self.layout, self.cell, (1,1))
		manager.all_mosaic_arrays_detect()
		regions = manager.visualize()
		shapes_save(regions, self.layout, self.cell, (0,0))

		self.layout.write(os.path.join(self.writeDir, self.name+'_mosaic.gds'))

	def test_PArrayManager(self):
		layer = self.layout.layer_indexes()[0]
		arrayManager = PArrayManager.layout_to_array_proposals(self.layout)
		arrayManager.overlapping_resolve()
		arrayManager.proposals_to_arrays_sharing()
		arrayManager.element_determine()
		arrayManager.array_check_linear()
		regions = arrayManager.visualize()
		shapes_save(regions, self.layout, self.cell, (0,0))

		self.layout.write(os.path.join(self.writeDir, self.name+'_project.gds'))


class HierManagerTest(unittest.TestCase):

	def setUp(self):
		filename="testcase4.gds"
		readFile = os.path.join('.', 'layout', 'gds', 'normal', filename)
		self.writeDir = os.path.join('.', 'layout', 'out', 'normal')
		layout = db.Layout()
		layout.read(readFile)
		self.cell = layout.top_cell()
		self.layout = layout
		self.name = filename.split('.')[0]

	def test_PArrayManager(self):

		hierManager = HierarchyManager(self.layout)
		hierManager.layout_parse(self.layout.layer_indexes()[0])
		hierManager.unit_patterns_propogate()
		cell = hierManager.overlap_resolve(restore=True)
		regions = hierManager.visualize_childInst()
		# regions = hierManager.visualize(True)
		# for i, boxes in enumerate(regions):
		# 	shapes_save(boxes, self.layout, self.cell, (i,i))
		#
		# self.layout.write(os.path.join(self.writeDir, self.name+'_child_1.gds'))
		cell.write(os.path.join(self.writeDir, self.name+'_restore.gds'))

if __name__ == '__main__':
	unittest.main()
