"""
@author: 	Meenchow Yin
@date: 		2020.03.10
@version: 	0.2
@abstract: 	Hierarchy manager class is created based on the propogation algorithm.
	Largest repeating patterns are found and organized to form tree-like hierarchy.
	Besides, some special care shoud be taken of arrays.
	@add Hierarchy restore feature is added.
"""
import time

import klayout.db as db
from rtree import index

from layoutHier.utils.structures import T1, T2, T3, T4, T5, T6, T7, T8
from layoutHier.utils.pattern import *
from layoutHier.utils.helpers import box_tuple, indexes_to_string, box_expand, inst_enlarge

class HierarchyManager(object):
	"""For flatten layout hierarchy, hierarchy is extracted through propagation
	algorithm and can be restored back into the layout."""

	def __init__(self, layout, polygonLib=PolygonLib([],{},0), root= Pattern()):
		self.layout = layout
		self.polygonLib = polygonLib
		self.patternRoot = root

		self.__instList = []	# index => polygon instance
		self.__polygonTree = index.Index()	# for polygon interaction index
		self.__unitLib = PatternLib([], {}, 0)
		self.__globalLib = PatternLib([], {}, 0)
		self.__largestLib = PatternLib([], {}, 0)

	def layout_parse(self, layerIndex=0, merge=True, flatten=True):
		topCell = self.layout.top_cell()
		if flatten:
			topCell.flatten(-1, False)
		if merge:
			topRegion = db.Region(topCell.begin_shapes_rec(layerIndex))
			topRegion.merge(layerIndex)
			topRegion.merged_semantics=0
			iterator = topRegion.each_merged()
		else:
			iterator = topCell.each_shape(layerIndex)

		for i, shape in enumerate(iterator):
			box = shape.bbox()
			if merge:
				polygon = shape
			else:
				polygon = shape.polygon
			vertexes = [(point.x, point.y) for point in polygon.each_point_hull()]
			self.__instList.append(self.polygonLib.encode(box, vertexes))
			self.__polygonTree.insert(i, (box.left, box.bottom, box.right, box.top))

		# pattern root
		boxWorld = topCell.bbox()
		inst = Instance(boxWorld, -1, -1, self.patternRoot)
		self.patternRoot.instList.append(inst)


	def unit_patterns_propogate(self):
		""""Derive unit patterns from polygon patterns according to definitions.
		Than unit patterns are propogated."""

		for pattern in self.polygonLib.patternList:
			self.__unit_pattern_expand(self.__unitLib, pattern, self.__polygonTree, self.__instList)

		# patterns with less instances has topper priority
		temp = []
		for pattern in self.__unitLib.patternList:
			if len(pattern) > 1:
				temp.append(pattern)
		temp.sort(key = lambda x: len(x))
		self.__unitLib.patternList = temp

		# reset visited to False
		for inst in self.__instList:
			inst.visited = False

		for pattern in self.__unitLib.patternList:
			self.__propagate(self.__largestLib, self.__globalLib, pattern,
					self.patternRoot, self.__instList, self.__polygonTree)

	def visualize(self, split=True):
		regions = []
		if split:
			for pattern in self.__largestLib.patternList:
				regions.append([inst.bbox for inst in pattern.instList])
		else:
			for pattern in self.__largestLib.patternList:
				regions.extend([inst.bbox for inst in pattern.instList])

		return regions

	def visualize_childInst(self):
		regions = []
		patterns = [self.patternRoot]
		processed = {}
		for p in patterns:
			if p in processed:
				continue
			processed[p] = 0
			patterns.extend(p.childPatterns)
		for pattern in patterns:
			boxes = []
			for inst in pattern.instList:
				boxes.extend([ci.bbox for ci in inst.childInsts])
			if boxes:
				regions.append(boxes)
		return regions

	def overlap_resolve(self, flowUp=False, restore=True):
		"""Overlapping patterns within one level including the self_overlapping and
		the cross_overlapping are resolved to ensure proper hierarchy."""

		patternRoot, largestLib = self.patternRoot, self.__largestLib
		largestLib.pattern_rtree_construct()

		while True:
			keep, delete, queue = {}, {}, [patternRoot]
			# self-overlapping patterns resolve
			for p0 in largestLib.patternList:
				for inst in p0.instList:
					self_overlap = list(p0.rtree.intersection(box_tuple(inst.bbox)))
					if len(self_overlap) > 1:
						delete[p0] = 0
						break

			if flowUp:
				while queue:
					pattern = queue.pop(0)
					while True:
						less, more = [], []
						for p0 in pattern.childPatterns:
							if p0 in delete:
								less.append(p0)
								for pc in p0.childPatterns:
									if pc not in pattern.childPatterns:
										more.append(pc)
						for p0 in less:
							pattern.childPatterns.remove(p0)
						pattern.childPatterns.extend(more)
						if not more:
							break

			# partly_overlapping resolve
			queue = [patternRoot]
			while queue:
				pattern = queue.pop(0)
				if pattern in delete:
					continue

				childTree = index.Index()
				boxP = pattern.instList[0].bbox	# one instance for one box
				for i, p0 in enumerate(pattern.childPatterns):
					if p0 in delete:   # patterns might be processed before
						continue
					for inst in p0:
						if inst.bbox.inside(boxP):
							childTree.insert(i, box_tuple(inst.bbox))

				i, keepTemp = 0, []
				for p in pattern.childPatterns:
					if p in delete:
						i += 1
						continue

					interactions = set()
					for inst in p:
						if inst.bbox.inside(boxP):
							interactions.update(childTree.intersection(box_tuple(inst.bbox)))
					all = list(interactions)
					overlapping = []
					for x in all:	# filter deprecated patterns
						if pattern.childPatterns[x] not in delete:
							overlapping.append(x)

					if len(overlapping) > 1:
						# find the biggest
						max = overlapping[0]
						for idx in overlapping:
							cpMax = pattern.childPatterns[max]
							cpIdx = pattern.childPatterns[idx]
							if cpIdx in keep:
								max = idx
								break
							max = max if cpMax.area() >= cpIdx.area() else idx
						overlapping.remove(max)
						keep[pattern.childPatterns[max]] = 0    # keep the biggest
						if pattern.childPatterns[max] not in keepTemp:
							keepTemp.append(pattern.childPatterns[max])
						# delete the smaller and update child patterns
						for idx in overlapping:
							main, another = pattern.childPatterns[max], pattern.childPatterns[idx]
							if another in keep:
								continue
							self.__part_overlap_resolve(main, another, pattern,
														delete, childTree, boxP)
					else:
						keep[p] = 0
						if p not in keepTemp:
							keepTemp.append(p)
					i += 1
				pattern.childPatterns = keepTemp
				queue.extend(keepTemp)

			newChild = []
			for p0 in largestLib.patternList:
				if p0 not in delete:
					newChild.append(p0)
			largestLib.patternList = newChild

			if not delete:
				break

		self.__instances_resolve()
		if restore:
			return self.__hierarchy_restore()

	@staticmethod
	def __propagate(largestLib, globalLib, patternSeed, patternRoot, instList, rtree,
					reduction=False, threshold=200):
		""""propagate one seed pattern to several repeating patterns and filter
		Largest Repeating pattern out.Further, pattern relation are recorded for
		hierarchy reconstruction. Set @param reduction to induce expansion
		direction reduction."""

		stack = [patternSeed]
		localLib = PatternLib([], {}, 0)
		visitedFlag = True
		while(stack):
			print("Stack depth: %d" % len(stack))
			patternTop = stack.pop()
			n = len(patternTop)
			patternSet = PatternLib([], {}, 0) # interim pattern library for one pattern propagation process
			incremental = True if len(patternTop.code[0])>threshold else False
			for inst in patternTop.instList:
				stringList, boxList = inst_enlarge(inst.bbox, instList, rtree, incremental)
				for string,box in zip(stringList, boxList):
					patternSet.encode(string, box)

			patternL, count = [], 0
			for pattern in patternSet.patternList:
				if len(pattern) == n:
					patternL.append(pattern)
					count += 1
			if count == 0:	#patternTop is LR pattern
				largestFlag = True
				rootFlag = True   #could be the child of patternRoot or another one
				for pattern in patternSet.patternList:
					if len(pattern) > 1:
						pattern.childPatterns.append(patternTop)
						rootFlag = False
						if localLib.any_same(pattern) or \
								globalLib.any_same(pattern) or \
								largestLib.any_include(pattern):
							visitedFlag = False
						else:
							localLib.insert(pattern)
							globalLib.insert(pattern)
							stack.append(pattern)
			else:	#pattern inlarge
				largestFlag = False
				for pattern in patternSet.patternList:
					if pattern in patternL:
						if localLib.any_same(pattern) or \
								globalLib.any_same(pattern) or \
								largestLib.any_include(pattern):
							visitedFlag = False
						else:
							for x in patternTop.childPatterns:
								pattern.childPatterns.append(x)
							localLib.insert(pattern)
							globalLib.insert(pattern)
							stack.append(pattern)
					else:
						if len(pattern) > 1:
							if localLib.any_same(pattern) or \
									globalLib.any_same(pattern) or \
									largestLib.any_include(pattern):
								visitedFlag = False
							else:
								localLib.insert(pattern)
								globalLib.insert(pattern)
								if not reduction:
									for x in patternTop.childPatterns:
										pattern.childPatterns.append(x)
									stack.append(pattern)

			if largestFlag:
				largestLib.patternList.append(patternTop)
				if rootFlag:
					patternRoot.childPatterns.append(patternTop)
		if visitedFlag:
			for polyInst in patternSeed.polygonList:
				polyInst.visited = True

	@staticmethod
	def __unit_pattern_expand(UnitLib, polygonPattern, rtree, instList):
		""""Expand from polygon seed to complete region without cutting any polygons."""

		patternNum = UnitLib.patternCount
		visitedList = list()       		  	#waiting list to be marked as visited
		exclusive = dict()
		special = list()                    #instance of former pattern

		for inst in polygonPattern.instList:
			if not inst.visited:  			#inst not being included by unit pattern
				box = db.Box(inst.bbox)
				box1, regionList = box_expand(box, instList, rtree)
				inst1 = UnitLib.encode( indexes_to_string(regionList, instList), box)
				idx = inst1.pid - patternNum
				if idx < 0:
					special.extend(regionList)
				elif len(visitedList) > idx:
					visitedList[idx].extend(regionList)
				else:
					visitedList.append(regionList)

		total = UnitLib.patternCount - patternNum
		for i in range(total):
			if len(UnitLib.patternList[i+patternNum].instList) == 1:
				exclusive[i] = i

		# mark the instance as visited
		for i in range(total):
			if i not in exclusive:
				for idx in visitedList[i]:
					UnitLib.patternList[i+patternNum].polygonList.append(instList[idx])
					instList[idx].visited = True
		for idx in special:
			instList[idx].visited = True

	@staticmethod
	def __part_overlap_resolve(main, another, parent, delete, rtree, boxP):
		"""Resolve part overlapping patterns recursively."""

		delete[another] = 0
		grandsons = another.childPatterns
		for g in grandsons:
			si = g.overlap(main)
			if si == 0: # outside
				if g not in parent.childPatterns:
					for p in parent.childPatterns:
						if p is another or p in delete:
							continue
						if g in p.childPatterns:
							break
					idx = len(parent.childPatterns)
					for inst in g.instList:
						if inst.bbox.inside(boxP):
							rtree.insert(idx, box_tuple(inst.bbox))
					parent.childPatterns.append(g)
			elif si == 1: # inside
				if g not in main.childPatterns and g is not main:
					main.childPatterns.append(g)
			else: # part overlap
				if g.childPatterns:
					HierarchyManager.__part_overlap_resolve(main, g, parent, delete, rtree, boxP)
				else:
					delete[g] = 0

	def __instances_resolve(self):
		"""Build the instances tree and resolve possible overlaps between them."""
		largestLib, patternRoot = self.__largestLib, self.patternRoot

		queue = [p for p in patternRoot.childPatterns]
		processed = {}
		while queue:
			pattern = queue.pop(0)
			if pattern in processed:
				continue
			processed[pattern] = 0
			# match instances
			for inst in pattern:
				for p in pattern.childPatterns:
					children = list(p.rtree.intersection(box_tuple(inst.bbox)))
					p.instFlag_update(children)
					inst.childInsts.extend(p.someInst(children))

			queue.extend(pattern.childPatterns) # next level

		# match root pattern instances
		instRoot = patternRoot.instList[0]
		patterns = [patternRoot]
		for p in patterns:
			for cp in p.childPatterns:
				if cp not in patterns:
					patterns.append(cp)
		for pattern in patterns[1:]:
			instRoot.childInsts.extend([i for i in pattern.remainings()])
		# FIXME: strategy like pattern overlapping resolve can be adopted
		# possible overlaps resolve
		delete, rtree = {}, index.Index()
		for i, inst in enumerate(instRoot.childInsts):
			rtree.insert(i, box_tuple(inst.bbox))

		for i, inst in enumerate(instRoot.childInsts):
			if i in delete:
				continue

			touches = list(rtree.intersection(box_tuple(inst.bbox)))
			for d in delete.keys():
				if d in touches:
					touches.remove(d)
			if len(touches) == 1:
				continue

			max = touches[0]
			for t in touches[1:]:
				max = max if instRoot.childInsts[max].bbox.area() > \
						instRoot.childInsts[t].bbox.area() else t
			touches.remove(max)
			for t in touches:
				delete[t] = 0

		# add to top cell and delete their overlapping instance
		keepPart = [inst for i, inst in enumerate(instRoot.childInsts) if i not in delete]
		deletePart = [inst for i, inst in enumerate(instRoot.childInsts) if i in delete]
		instRoot.childInsts = keepPart
		for inst0 in deletePart:
			# delete recursively
			all = [inst0]
			for inst1 in all:
				all.extend([ci for ci in inst1.childInsts if ci not in all])
			for inst1 in all:
				pattern = inst1.pattern
				if inst1 in pattern.instList:
					pattern.instList.remove(inst1)

	def __hierarchy_restore(self, layerIndex=0):
		"""Restore hierarchy of flatten layout according to the instance tree
		build before. The cell tree wild be built from bottom to the top."""
		largestLib, patternRoot = self.__largestLib, self.patternRoot

		patternRoot.instList[0].tid = T1  # maintain the integrity
		patterns = [patternRoot]
		for p in patterns:
			patterns.extend(p.childPatterns)
		patterns.reverse()

		cellTop = self.layout.top_cell()
		shapesTop = cellTop.shapes(layerIndex)
		idx = 0
		for p in patterns:	# from bottom to top
			if p.cell_build:
				continue
			idx += 1
			# remove shapes from layout and build the cell(to T1 trans)
			cell = self.layout.create_cell('Pattern-' + str(idx))
			p.cell = cell
			shapesCell = cell.shapes(layerIndex)
			instT1 = p.instList[0]
			for inst in p:	# move the shapes from instance with tid T1
				if inst.tid == T1:
					instT1 = inst
					break
			transT1 = db.Trans()	# from some pattern with instT1 removed
			if instT1.tid == T1:
				pass
			elif instT1.tid == T2:
				trans.mirror = True
			elif instT1.tid == T3:
				trans.angle = 270
			elif instT1.tid == T4:
				trans.mirror = True
				trans.angle = 270
			elif instT1.tid == T5:
				trans.angle = 180
			elif instT1.tid == T6:
				trans.mirror = True
				trans.angle = 180
			elif instT1.tid == T7:
				trans.angle = 90
			elif instT1.tid == T8:
				trans.angle = 90
				trans.mirror = True
			else:
				raise('Instance transformation ID {} \
				is out of range[0-7].'.format(instT1.tid.value))

			for shape in shapesTop.each():
				for inst in p:
					if shape.bbox().inside(inst.bbox):
						if inst is instT1:
							shapesCell.insert(shape)
						shapesTop.erase(shape)
						break
			shapesCell.transform(transT1)

			trans = db.Trans()
			for ci in instT1.childInsts:
				if ci.tid == T1:
					pass
				elif ci.tid == T2:
					trans.mirror = True
				elif ci.tid == T3:
					trans.angle = 90
				elif ci.tid == T4:
					trans.mirror = True
					trans.angle = 90
				elif ci.tid == T5:
					trans.angle = 180
				elif ci.tid == T6:
					trans.mirror = True
					trans.angle = 180
				elif ci.tid == T7:
					trans.angle = 270
				elif ci.tid == T8:
					trans.angle = 270
					trans.mirror = True
				else:
					raise('Instance transformation ID {} \
					is out of range[0-7].'.format(ci.tid.value))

				instNew = db.CellInstArray(ci.pattern.cell.cell_index(), trans)
				boxO = instNew.bbox(self.layout)
				v0 = db.Vector(ci.bbox.left-boxO.left, ci.bbox.bottom-boxO.bottom)
				instNew.transform(db.Trans(v0))
				cell.insert(instNew)

			p.cell_build = True

		return patternRoot.cell
