"""
@author: 	Meenchow Yin
@date: 		2019.10.18
@version: 	1.0
@abstract: 	Firstly, layout will be split into different bins w.r.t. polygon
			  patterns.
			Secondly, array region condidate are derived from x,y projective
			  features with strict criterion.
			Thirdly, in condidate array region, proper x,y scanline is drawn to
			  extract all primitives in layout which are touched, and the array
			  period is determined(or candidate is not an array).
			Finally, arrays found before are checked again with whole region
			  cropping and projecting.
"""

import math, time

import klayout.db as db
from bintrees import FastRBTree
from rtree import index

from layoutHier.utils.pattern import *
from layoutHier.utils.helpers import lcm
from layoutHier.utils.structures import Node, SortedLinkedList

__all__ = ["SArray", "SArrayManager"]

class SArray(object):
	"""Array here could be simple array or mosaic array."""

	def __init__(self, cell, template, leap, region, rbtree, dimension=None):
		"""A little different representation from split_project array is brought
		here.
		@params:
		anchorCell: Leftbottom cell that is just tuple(xa, ya, width, height node).
		template: template instance.
		leap: Periods of both array directions which format is like (lx, ly).
		region: Region indicates the whole array which could be rectangular or
				rectilinear.
		dimension: Cycles for both dimensions.
		rbtree: red black tree store all elements.
		__is_mosaic: Flag indicating if the array is mosaic array."""
		self.anchorCell = cell
		self.template = template
		self.leap = leap
		self.region = region	# FIXME: Expand region function to rectilinear region
		self.dimension = dimension
		self.rbtree = rbtree
		self.edgeProc = db.EdgeProcessor()
		self.__is_mosaic = False

	@classmethod
	def create(cls, template, anchorCell, leap, dim):
		# create rbtree
		xa, ya  = anchorCell.left, anchorCell.bottom
		width, height = anchorCell.width(), anchorCell.height()
		leapx, leapy = leap
		tree = FastRBTree()
		for i in range(dim[0]):
			tree[xa+i*leapx] = SortedLinkedList([ya+i*leapy for i in range(dim[1])])
		# region is the bounding box of the whole array
		box = db.Box(xa, ya, xa+leapx*(dim[0]-1)+width, ya+leapy*(dim[1]-1)+height)
		region = db.Polygon(box)
		return cls(anchorCell, template, leap, region, tree, dim)

	def move_next(self, pS):
		"""Move @param pS to next adjacent cell along the y axis and move to next
		next column when reaching end."""
		leapx, leapy = self.leap
		tail = self.rbtree[pS[0]].tail.value
		if pS[1] == tail:
			temp = pS[0]+leapx
			if temp in self.rbtree:
				return (temp, self.rbtree[temp].head.value)
			else:
				return None		# the end of the tree is reached
		else:
			return (pS[0], pS[1]+leapy)

	def cell_exist(self, point):
		"""Check is there exists a cell in given position"""
		x, y = point[0], point[1]
		_, leapy = self.leap

		if x in self.rbtree and self.rbtree[x].head:
			jumpy = (y-self.rbtree[x].head.value)/leapy
			if jumpy >= 0 and jumpy < self.rbtree[x].size:
				return True
			else:
				return False
		else:
			return False


	def reference_cell_find(self, crossPoint):
		"""Use anchorCell first, otherwise rbtree is searched"""
		xa, ya = self.anchorCell.left, self.anchorCell.bottom
		x0, y0 = crossPoint[0], crossPoint[1]
		leapx, leapy = self.leap
		x = x0 - (x0-xa)%leapx
		y = y0 - (y0-ya)%leapy
		if not self.cell_exist((x,y)):
			keyLast = x0
			for key in self.rbtree:
				if key >= x0:
					x = key
					for nodey in self.rbtree[x]:
						if nodey.value >= y0:
							y = nodey.value
				else:
					keyLast = key
			if not self.cell_exist((x,y)):
				# choose last row
				if keyLast in self.rbtree:
					x, y = keyLast, self.rbtree[keyLast].head.value
				else:
					return None

		return (x, y)

	def seed_find(self, pRef, dim):
		"""Find a subarray (actually locations) to form the anchor cell of
		merged mosaic array."""
		leapx, leapy = self.leap
		dimx, dimy = dim
		x0, y0 = pRef # origin
		seed = [(x0+i*leapx, y0+j*leapy) for i in range(dimx) for j in range(dimy)]
		return seed

	def subArray_bbox(self, seed):
		w, h = self.anchorCell.width(), self.anchorCell.height()
		l, b = seed[0][0], seed[0][1]
		box = db.Box(l, b, l+w, b+h)
		for p in seed:
			box0 = db.Box(p[0], p[1], p[0]+w, p[1]+h)
			box = box + box0
		return box

	def dimensions_determine(self, pr1, regionM, dimSub):
		"""Find the supported maximal dimension for merged array.
		@param regionM: db.Box object."""
		numX, numY = 0, 10e5
		x0, y0 = pr1
		xMax = x0 + regionM.width() + self.leap[0]
		x = x0
		while x < xMax:
			if x in self.rbtree and self.rbtree[x].tail:
				tail = self.rbtree[x].at(y0)
				if not tail:
					break
				while tail.next:
					tail = tail.next
				tempy = int((tail.value - y0)/self.leap[1]) + 1
				numY = min(numY, tempy)
				numX += 1
				x = x + self.leap[0]
			else:
				break

		dim1 = numX//dimSub[0]
		dim2 = numY//dimSub[1]
		return (dim1, dim2)

	def modify(self, pRef, dimSub, dimM):
		"""Exclude mosaic region and adjust rbtree and relevant elements."""
		numX = dimSub[0]*dimM[0]
		numY = dimSub[1]*dimM[1]

		# adjust rbtree
		for i in range(numX):
			x = pRef[0]+i*self.leap[0]
			if self.rbtree[x].size == numY:
				self.rbtree.pop(x)
			else:
				self.rbtree[x].pop_values([pRef[1]+i*self.leap[1] for i in range(numY)])
				# self.rbtree[x].pop_segment(pRef[1], pRef[1]+(numY-1)*self.leap[1])

		# adjust region
		if self.rbtree.is_empty():
			self.region = db.Polygon()
		else:
			left, bottom = pRef[0]-self.leap[0], pRef[1]-self.leap[1]
			right, top = left+self.leap[0]*(numX+1), bottom+self.leap[1]*(numY+1)
			w, h = self.anchorCell.width(), self.anchorCell.height()
			regionExcd = db.Polygon(db.Box(left+w, bottom+h, right, top))
			ep = self.edgeProc
			r = ep.boolean_p2p([self.region], [regionExcd], ep.ModeANotB, False, False)
			self.region = r[0] if r else db.Polygon()
			# adjust anchor cell
			# self.anchorCell = self.anchorCell.move(0, top-bottom)

	def noise_cells_remove(self, rtree, regionM):
		"""Remove noise cells within the overlapping region and insert them into rtree."""
		w, h = self.anchorCell.width(), self.anchorCell.height()
		left, bottom = regionM.left, regionM.bottom
		right, top = regionM.right, regionM.top
		leap = self.leap[1]
		keys = list(self.rbtree.keys())
		for key in keys:
			if key >= left and key <=right:
				begin = self.rbtree[key].head.value
				end = self.rbtree[key].tail.value
				v1, v2 = leap*int(math.ceil((max(begin, bottom)-begin)/leap))+begin, min(end, top)
				if v1 <= v2:
					try:
						for v in range(v1, v2+1, leap):
							self.rbtree[key].pop_values([v])
							rtree.insert(0, (key, v, key+w, v+h))
					except:
						import ipdb; ipdb.set_trace()
			if self.rbtree[key].size == 0:
				self.rbtree.pop(key)
		# FIXME: naive implementation
		if self.rbtree.is_empty():
			self.region = db.Polygon()
			return
		ep = self.edgeProc
		exclude = ep.boolean_p2p([self.region], [db.Polygon(regionM)], ep.ModeANotB, False, False)
		if exclude:
			self.region = exclude[0]
		else:
			self.region = db.Polygon()

	def decompose(self, rtree):
		"""Decompose rectilinear array into rectangular ones."""
		if self.region.is_box():
			return [self]

		polygons = self.region.decompose_trapezoids(self.region.TD_htrapezoids)
		arrays = []
		for polygon in polygons:
			box = polygon.bbox()
			if box.width() < 2*self.leap[0] or box.height() < 2*self.leap[1]:
				self.noise_cells_remove(rtree, box)
			else:
				dim1 = (box.right - box.left)//self.leap[0] + 1
				dim2 = (box.top - box.bottom)//self.leap[1]
				left = box.left
				bottom = box.bottom if (box.bottom - self.anchorCell.bottom)%self.leap[1]==0 \
					else box.bottom - self.anchorCell.height() + self.leap[1]
				anchorCell = db.Box(
					left, bottom, left+self.anchorCell.width(), bottom+self.anchorCell.height())
				arrays.append(SArray.create(self.template, anchorCell, self.leap, (dim1, dim2)))

			return arrays

class SArrayManager(object):
	"""ArrayManager managers all necessary pieces to derive regular arrays in layout."""

	def __init__(self, arrayList=[], polygonTrees={}):
		self.arrayList = arrayList
		self.polygonTrees = polygonTrees  # red black tree here
		self.noise_cells = index.Index() 	# used to qualify arrays

	@classmethod
	def rbtrees_build(cls, layout, layer=0, merge=True):
		"""Construct ArrayManager with polygon r-b trees object from a layout object."""
		assert isinstance(layout, db.Layout)

		polyTrees = {}
		polygonLib = PolygonLib([], {}, 0, type='polygon')
		# encode polygons of the layout
		end = time.time()
		try:
			topCell = layout.top_cell()
			topCell.flatten(-1, False)
			boxWhole = topCell.bbox()
			print("Flatten time is {}".format(time.time()-end))
			end = time.time()
		except:
			print('Layout has nultiple top cell.')
		if merge:
			topRegion = db.Region(topCell.begin_shapes_rec(layer))
			topRegion.merge(layer)
			topRegion.merged_semantics=0
			iterator = topRegion.each_merged()
			print("Merge time is {}".format(time.time()-end))
			end = time.time()
		else:
			iterator = topCell.each_shape(layer)
		for i, shape in enumerate(iterator):
			box = shape.bbox()
			if merge:
				polygon = shape
			else:
				polygon = shape.polygon
			vertexes = [(point.x, point.y) for point in polygon.each_point_hull()]
			polygonLib.encode(box, vertexes)

		print("Encode time is {}".format(time.time()-end))
		print("Polygon count is {}, Layout area is {}".format(i+1, boxWhole.area()))

		# produce red black trees from polygon patterns
		# rbtree's node--(linked list, corresponding dict)
		for pattern in polygonLib.patternList:
			rbtree = FastRBTree()
			inst0 = pattern.instList[0]
			sign = (inst0.bbox.width(), inst0.bbox.height(),
					0, 0, inst0.pid, inst0.tid, inst0.symmetryType)
			polyTrees[sign] = rbtree
			for inst in pattern.instList:
				if inst.bbox.left in rbtree:
					rbtree[inst.bbox.left][inst.bbox.bottom] = 0 # (inst.bbox.right, inst.tid)
				else:
					rbtree[inst.bbox.left] = {inst.bbox.bottom: 0}

			# the following is wrong due to the key changing bug of the FastRBTree
			keys = list(rbtree.keys())
			for key in keys:
				# ascending order
				values = rbtree[key]
				valueList = list(values.keys())
				valueList.sort()
				dlList = SortedLinkedList(valueList)
				rbtree[key] = (dlList, values)

		return cls([], polyTrees)

	@staticmethod
	def __leapx_find(tree, xa, ya, Threshold=10):
		prex, count = xa, 1
		first, jumpFirst = 0, 0
		for x in tree.keys():
			if x > xa and ya in tree[x][1]:
				first, jumpFirst = x, x - xa;
				break
		if jumpFirst == 0:
			return None

		prex = first
		for x in tree.keys():
			if x > first and ya in tree[x][1]:
				jump = x - prex
				p1, p2 = 2*prex-xa, 3*prex-2*xa
				if jump == jumpFirst and p1 in tree and p2 in tree:
					if ya in tree[p1][1] and ya in tree[p2][1]:
						return prex - xa
				prex = x
				count += 1
			# return when maximal finding range reached
			if count == Threshold:
				return None
		return None

	@staticmethod
	def __dimensions_determine_simple(tree, leap, anchorCell):
		"""Find a tentative anchor cell and return leap w.r.t. it."""
		dimx, dimy, dimyTemp = 0, 1e5, 1
		Xa, Ya = anchorCell.left, anchorCell.bottom
		nodex = tree[Xa][0].at(Ya)
		xTemp = Xa
		while(nodex is not None and dimyTemp != 0):
			nodey = nodex
			yTemp = Ya
			dimyTemp = 0
			dimx += 1
			while(nodey is not None):
				dimyTemp += 1
				yTemp += leap[1]
				nodey = nodey.to(yTemp)

			if dimy > dimyTemp:
				dimy = dimyTemp
			xTemp += leap[0]
			if xTemp in tree:
				nodex = tree[xTemp][0].at(Ya)
			else:
				nodex = None

		return (dimx, dimy)

	@staticmethod
	def __reference_cells_find(array1, array2, region, dimSub1, dimSub2):
		"""Find two reference cells that are closest to the leftbottom vertice of region.
		* Notice: Merge region here should be a box."""
		l, b = region.left, region.bottom
		p1 = array1.reference_cell_find((l, b))
		p2 = array2.reference_cell_find((l, b))
		if p1 is None or p2 is None:
			return None, None
		leap1, leap2 = array1.leap, array2.leap
		# move to bottom if possible
		for i in range(dimSub1[1], 0, -1):
			if array1.cell_exist((p1[0], p1[1]-i*leap1[1])):
				p1 = (p1[0], p1[1]-i*leap1[1])
				break
		for i in range(dimSub2[1], 0, -1):
			if array2.cell_exist((p2[0], p2[1]-i*leap2[1])):
				p2 = (p2[0], p2[1]-i*leap2[1])
				break
		# move to left if possible
		for i in range(dimSub1[0], 0, -1):
			if array1.cell_exist((p1[0]-i*leap1[0], p1[1])):
				p1 = (p1[0]-i*leap1[0], p1[1])
				break
		for i in range(dimSub2[0], 0, -1):
			if array2.cell_exist((p2[0]-i*leap2[0], p2[1])):
				p2 = (p2[0]-i*leap2[0], p2[1])
				break

		return p1, p2

	def __noise_simple_array_filter(self):
		"""Filter noise simple arrays which are formed by upper periodic elements"""
		# FIXME: replace the naive implementation
		arrays, N = {}, len(self.arrayList)
		for i,array in enumerate(self.arrayList):
			for j in range(N):
				arrayj = self.arrayList[j]
				if array.region.touches(arrayj.region) and j!=i:
					leapx, leapy = array.leap
					box = arrayj.region.bbox()
					if (leapx >= box.width() or leapy >= box.height()) and \
					max(array.leap)/min(array.leap) > max(arrayj.leap)/min(arrayj.leap):
						arrays[i] = i
						break

		self.arrayList = [arra for i, arra in enumerate(self.arrayList) if i not in arrays]

	def visualize(self):
		"""Output the bounding box of the mosaic arrays for visualization."""
		boxList, area = [], 0
		for array in self.arrayList:
			area += array.region.area()
			contour = array.region
			anchorCell = array.anchorCell
			boxList.extend([contour, anchorCell])

		print("Array area is {}, array count is {}.".format(area, len(self.arrayList)))
		return boxList

	@staticmethod
	def simple_arrays_join(array, cdids, joints):
		"""Join all touched simple arrays into complete rectilinear array."""
		touches = []
		for node in iter(cdids):
			array0 = node.value
			l, b = array.anchorCell.left, array.anchorCell.bottom
			l0, b0 = array0.anchorCell.left, array.anchorCell.bottom
			cond = array.leap==array0.leap and abs(l-l0)%array0.leap[0]==0 and \
				not array.region.bbox().overlaps(array0.region.bbox()) and \
				abs(b-b0)%array0.leap[1]==0 and array.region.touches(array0.region)
			if cond:
				touches.append(node)
		if touches:
			# join arrays
			for node in touches:
				cdids.pop(node)		# pop from the candidates
				array0 = node.value
				if array0.anchorCell < array.anchorCell:
					array.anchorCell = array0.anchorCell
				ep = array0.edgeProc
				rm = ep.boolean_p2p([array.region], [array0.region], ep.ModeOr, False, False)
				array.region = rm[0]
				# join rbtree
				for x in array0.rbtree.keys():
					if x in array.rbtree:
						vHead = array.rbtree[x].head.value
						vHead0 = array0.rbtree[x].head.value
						if vHead > vHead0:
							array.rbtree[x].join(array.rbtree[x], 'tail')
						else:
							array.rbtree[x].join(array.rbtree[x], 'head')
					else:
						array.rbtree[x] = array0.rbtree[x]
				# FIXME: if it is indispensable to update dimension
			# join futher for this array
			SArrayManager.simple_arrays_join(array, cdids, joints)
		else:
			joints.append(array)
			if cdids.size == 0:
				return
			else:
				node = cdids.head
				cdids.pop(node)
				SArrayManager.simple_arrays_join(node.value, cdids, joints)

	def simple_array_form(self):
		"""Derive simple arrays from polygon instances red blace tree."""
		for sign, tree in self.polygonTrees.items():
			# produce simple arrays from polygon trees
			arrays = []
			while not tree.is_empty():
				keys = list(tree.keys())  # decouple the effect of rbtree adjusment
				for x in keys:	# in-order traversal
					while tree[x][0].size != 0:
						anchorNode, leapy = tree[x][0].period_find(
										self.noise_cells, (x, sign[0],sign[1]))
						if leapy is None:
							tree[x][0].clear(self.noise_cells, (x, sign[0],sign[1]))
							continue
						xa, ya = x, anchorNode.value
						leapx = self.__leapx_find(tree, xa, ya)
						if leapx is None:
							# remove all periodic nodes with respect to leapy along "x"
							nodeRemove = anchorNode
							while nodeRemove:
								node0 = nodeRemove.to(nodeRemove.value + leapy)
								tree[xa][0].pop(nodeRemove)
								self.noise_cells.insert(
								0, (xa, nodeRemove.value, xa+sign[0], nodeRemove.value+sign[1]))
								nodeRemove = node0
							continue
						else:
							leap = (leapx, leapy)
							anchorCell = db.Box(xa, ya, xa+sign[0], ya+sign[1])
							# WARNING: there could be some cases for wrong dimension determination
							dim = self.__dimensions_determine_simple(tree, leap, anchorCell)
							if dim[0] > 3 and dim[1] > 3:
								template = Template([sign[2:]])
								array0 = SArray.create(template, anchorCell, leap, dim)
								arrays.append(array0)
								#remove cells from tree
								for i in range(dim[0]):
									xdel = xa + i*leapx
									tree[xdel][0].pop_values([ya+i*leapy for i in range(dim[1])])
							else:
								tree[x][0].pop(anchorNode)
								self.noise_cells.insert(
								0, (x, anchorNode.value, xa+sign[0], anchorNode.value+sign[1]))
					tree.pop(x)
			self.arrayList.extend(arrays)

		# ensure only the lowest level arrays are captured
		self.__noise_simple_array_filter()
		self.arrayList.sort(key=lambda x: (x.anchorCell.left, x.anchorCell.bottom))

	def mosaic_array_form(self, array1, array2, arrayList):
		"""Derive mosaic arrays from overlapping simple arrays. @Param array1 is
		treated as the main array"""

		ep = array1.edgeProc
		regionM = ep.boolean_p2p([array1.region], [array2.region], ep.ModeAnd, False, False)
		if len(regionM) == 1:
			mosaicArrayList = []
			regionsM = regionM[0].decompose_trapezoids(regionM[0].TD_htrapezoids)
			leap1, leap2 = array1.leap, array2.leap
			leapM = (lcm(leap1[0], leap2[0]), lcm(leap1[1], leap2[1]))
			dimSub1 = (leapM[0]//leap1[0], leapM[1]//leap1[1])
			dimSub2 = (leapM[0]//leap2[0], leapM[1]//leap2[1])
			for rg in regionsM:
				regionM = rg.bbox()
				pr1, pr2 = self.__reference_cells_find(array1, array2, regionM, dimSub1, dimSub2)
				if pr1 is None:
					array1.noise_cells_remove(self.noise_cells, regionM)
					array2.noise_cells_remove(self.noise_cells, regionM)
					continue
				# extract subarrays to form the anchor cell
				seed1 = array1.seed_find(pr1, dimSub1)
				seed2 = array2.seed_find(pr2, dimSub2)
				subBox1 = array1.subArray_bbox(seed1)
				subBox2 = array2.subArray_bbox(seed2)
				boxM = subBox1 + subBox2
				# create a tentative anchor cell (also a mosaic cell template).
				while True:
					if boxM.width() > leapM[0]:	# move along x direction
						if pr1[0] < pr2[0]:
							if array1.cell_exist((pr1[0]+leap1[0], pr1[1])):
								pr1 = (pr1[0]+leap1[0], pr1[1])
							else:
								pr1 = array1.move_next(pr1)
						else:
							if array2.cell_exist((pr2[0]+leap2[0], pr2[1])):
								pr2 = (pr2[0]+leap2[0], pr2[1])
							else:
								pr2 = array2.move_next(pr2)
					elif boxM.height() > leapM[1]:	# move along y direction
						if pr1[1] < pr2[1]:
							if array1.cell_exist((pr1[0], pr1[1]+leap1[1])):
								pr1 = (pr1[0], pr1[1]+leap1[1])
							else:
								pr1 = array1.move_next(pr1)
						else:
							if array2.cell_exist((pr2[0], pr2[1]+leap2[1])):
								pr2 = (pr2[0], pr2[1]+leap2[1])
							else:
								pr2 = array2.move_next(pr2)
					else:	# both are satisfying
						break

					if pr1 is None or pr2 is None:
						break
					seed2 = array2.seed_find(pr2, dimSub2)
					seed1 = array1.seed_find(pr1, dimSub1)
					subBox1 = array1.subArray_bbox(seed1)
					subBox2 = array2.subArray_bbox(seed2)
					boxM = subBox1 + subBox2

				if pr1 is None or pr2 is None:	# treat as noise cells
					array1.noise_cells_remove(self.noise_cells, regionM)
					array2.noise_cells_remove(self.noise_cells, regionM)
					continue
				else:
					# create merged mosaic array
					dim1 = array1.dimensions_determine(pr1, regionM, dimSub1)
					dim2 = array2.dimensions_determine(pr2, regionM, dimSub2)
					dim = (min(dim1[0], dim2[0]), min(dim1[1], dim2[1]))
					if dim[0] < 3 or dim[1] < 3:
						array1.noise_cells_remove(self.noise_cells, regionM)
						array2.noise_cells_remove(self.noise_cells, regionM)
						continue
					# subArray and template
					try:	# exclude region from the former arrays
						array1.modify(pr1, dimSub1, dim)
						array2.modify(pr2, dimSub2, dim)
						subBox1 = array1.subArray_bbox(seed1)
						subBox2 = array2.subArray_bbox(seed2)
						anchorCell = subBox1 + subBox2
						left, bott = anchorCell.left, anchorCell.bottom
						template = array1.template.merge(seed1, array2.template, seed2, (left, bott))
						mosaicArrayList.append(SArray.create(template, anchorCell, leapM, dim))
					except:
						array1.noise_cells_remove(self.noise_cells, regionM)
						array2.noise_cells_remove(self.noise_cells, regionM)

				# check remaining array
				if array2.region.is_box():
					box = array2.region.bbox()
					if box.width() < 2*array2.leap[0] or box.height() < 2*array2.leap[1]:
						array2.noise_cells_remove(self.noise_cells, box)
				else:
					polygons = array2.region.decompose_trapezoids(array2.region.TD_htrapezoids)
					for p in polygons:
						box = p.bbox()
						if box.width() < 2*array2.leap[0] or box.height() < 2*array2.leap[1]:
							array2.noise_cells_remove(self.noise_cells, box)
				if array1.region.is_box():
					box = array1.region.bbox()
					if box.width() < 2*array1.leap[0] or box.height() < 2*array1.leap[1]:
						array1.noise_cells_remove(self.noise_cells, box)
				else:
					polygons = array1.region.decompose_trapezoids(array1.region.TD_htrapezoids)
					for p in polygons:
						box = p.bbox()
						if box.width() < 2*array1.leap[0] or box.height() < 2*array1.leap[1]:
							array1.noise_cells_remove(self.noise_cells, box)
		else:
			mosaicArrayList = [array1]

		mosaicArrays = []
		if len(arrayList) > 0 and mosaicArrayList:
			array = arrayList.pop()
			for mosaicArray in mosaicArrayList:
				mosaicArrays.extend(self.mosaic_array_form(mosaicArray, array, arrayList))
		else:
			return mosaicArrayList

		return mosaicArrays

	def all_mosaic_arrays_detect(self):
		"""Intersect all simple arrays in array list to form all mosaic arrays."""
		N = len(self.arrayList)
		mosaicArrayList = []
		for i, array in enumerate(self.arrayList):
			box = array.region.bbox()
			# FIXME: we might need some filters
			if array.rbtree.is_empty():
				continue
			arrays = []
			for j in range(N):
				if array.region.touches(self.arrayList[j].region) and j != i:
					arrays.append(self.arrayList[j])
			if arrays:
				mosaicArrays = self.mosaic_array_form(array, arrays[0], arrays[1:])
				if mosaicArrays:
					mosaicArrayList.extend(mosaicArrays)
			elif array.region.area() > 0:
				mosaicArrayList.append(array)

		# qualify mosaic arrays
		finals = []
		for array in mosaicArrayList:
			box = array.region.bbox()
			regionA = (box.left, box.bottom, box.right, box.top)
			touches = [i.bbox for i in self.noise_cells.intersection(regionA, True)]
			noises = False
			for n in touches:
				boxn = db.Box(int(n[0]), int(n[1]), int(n[2]), int(n[3]))
				if boxn.width() >= box.width() or boxn.height() >= box.height():
					continue
				if boxn.overlaps(box):
					noises = True
					break
			if not noises:
				finals.extend(array.decompose(self.noise_cells))
		self.arrayList = finals
