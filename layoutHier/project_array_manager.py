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

import math
import time

from rtree import index
import klayout.db as db

from layoutHier.utils.pattern import *
from layoutHier.utils.helpers import box_merge

__all__ = ["PArray", "PArrayManager"]

class PArray(object):
	"""Array is the class describing the regular element pattern in layout."""

	def __init__(self, box, periodX, periodY, element=None):
		assert isinstance(box, db.Box), 'Box param should be an db.Box object.'

		self.bbox = box
		self.periodX = periodX
		self.periodY = periodY
		self.element = element   #basic element consisting into array

	@classmethod
	def segment_to_array(cls, segmentx, segmenty, element=None):
		"""@param segment: x/y periodic segments which look like (start, end, \
		leap, number)"""

		assert len(segmentx)==3, 'Segment must be tuple of length 3.'
		assert len(segmenty)==3, 'Segment must be tuple of length 3.'

		box = db.Box(segmentx[0], segmenty[0], segmentx[1], segmenty[1])
		return cls(box, segmentx[2], segmenty[2], element)

	@property
	def shape(self):
		numX = (self.bbox.right - self.bbox.left)/self.periodX
		numY = (self.bbox.top - self.bbox.bottom)/self.periodY
		return (int(numX), int(numY))

	@property
	def periods(self):
		return(self.periodX, self.periodY)

	@property
	def coord_tuple(self):
		"""Print the coordinate (left, bottom, right, top)."""
		left, bottom = self.bbox.left, self.bbox.bottom
		right, top = self.bbox.right, self.bbox.top
		return (left, bottom, right, top)

	def update(self, segment, axis='x'):
		if axis == 'x':
			self.bbox.left, self.bbox.right = segment[0], segment[1]
			self.periodX = segment[2]
		if axis == 'y':
			self.bbox.bottom, self.bbox.top = segment[0], segment[1]
			self.periodY = segment[2]


class PArrayManager(object):
	"""ArrayManager managers all necessary pieces to derive regular arrays in
	layout. Normally, array proposals derived from ProjectiveFeature. """

	def __init__(self, arrayList=[], arrayProposals=[], polygonList=None,
				polygonTree=None, box=None):
		self.arrayList = arrayList
		self.arrayProposals = arrayProposals
		self.polygonList = polygonList
		self.polygonTree = polygonTree
		self.bbox = box

	@classmethod
	def layout_to_array_proposals(cls, layout, layer=0, merge=True):
		"""Construct ArrayManager object from a layout object."""
		assert isinstance(layout, db.Layout)

		polygonLib = PolygonLib([], {}, 0, type='polygon')
		arrayProposals = []
		arrayList = []
		polygonList = []
		polygonTree = index.Index()

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
			polygonList.append(polygonLib.encode(box, vertexes))
			polygonTree.insert(i, (box.left, box.bottom, box.right, box.top))

		print("Encode time is {}".format(time.time()-end))
		print("Polygon count is {}, area is {}".format(i, boxWhole.area()))

		# produce array proposals from polygon pattern
		for pattern in polygonLib.patternList:
			pattern.project()
			feature = pattern.feature
			arrays = [PArray.segment_to_array(segmentx, segmenty) for segmentx in
					  feature.segmentsX for segmenty in feature.segmentsY]
			arrayProposals.append(arrays)
			arrayList.extend(arrays)

		arrayProposals.sort(key= lambda x: len(x), reverse=True)
		return cls(arrayList, arrayProposals, polygonList, polygonTree, boxWhole)

	def untouching(self, proposal):
		"""Assert array proposals are valid or not according to touching principle."""

		px, py = proposal.periodX, proposal.periodY
		l, b = proposal.bbox.left, proposal.bbox.bottom
		touches = list(self.polygonTree.intersection((l, b, l+2*px, b)))
		if not touches:
			return True
		touches = list(self.polygonTree.intersection((l, b, l, b+2*py)))
		if not touches:
			return True
		r, t = proposal.bbox.right, proposal.bbox.top
		touches = list(self.polygonTree.intersection((r-2*px, t, r, t)))
		if not touches:
			return True
		touches = list(self.polygonTree.intersection((r, t-2*py, r, t)))
		if not touches:
			return True
		return False

	def proposals_to_arrays(self):
		"""Begin with array proposals, scan regions of interest to determine the
		exact bounding box and periods for corresponding regions."""

		realArrays, realIndex = [], index.Index()
		for proposals in self.arrayProposals:
			for proposal in proposals:
				# remove untouching proposals
				if self.untouching(proposal):
					continue
				overlappings = list(realIndex.intersection(proposal.coord_tuple))
				if overlappings:	# remove any proposals overlapping with real arrays
					continue

				# draw scanline, than project to obtain feature
				left, bottom, right, top = proposal.coord_tuple
				periodx, periody = proposal.periodX, proposal.periodY
				# project to x/y axis
				sidex = PArrayManager._period_of_region(self, left, right, periodx, \
					(bottom+top)/2, periody, axis='x')
				sidey = PArrayManager._period_of_region(self, bottom, top, periody, \
					(right+left)/2, periodx, axis='y')
				if sidex is None or sidey is None:
					continue

				# updata array
				proposal.bbox = db.Box(sidex[0], sidey[0], sidex[1], sidey[1])
				proposal.periodX = sidex[2]
				proposal.periodY = sidey[2]
				realArrays.append(proposal)
				realIndex.insert(len(realArrays), proposal.coord_tuple)

		self.arrayList = realArrays

	def array_check_linear(self):
		"""Check elements in array one by one to make sure they are the
		same. Attentionally, boundary elements are treated different."""
		keep = []
		for array in self.arrayList:
			sizex, sizey = array.shape
			patternLib = PatternLib([], {}, 0)
			area = array.periodX* array.periodY
			# elements inside
			elesInside = [(x,y) for x in range(1,sizex-1) for y in range(1,sizey-1)]
			for x0, y0 in elesInside:
				l = array.bbox.left + array.periodX*x0
				b = array.bbox.bottom + array.periodY*y0
				r, t = l+array.periodX, b + array.periodY
				idx = list(self.polygonTree.intersection((l, b, r, t)))
				instString, ov = [], []
				box = db.Box()
				for id in idx:
					inst = self.polygonList[id]
					if inst.bbox.area() > area:
						ov.append(id)
				for id in ov:
					idx.remove(id)
				for i, id in enumerate(idx):
					inst = self.polygonList[id]
					if i == 0:
						box = inst.bbox
					else:
						box = box + inst.bbox
					c = inst.bbox.center()
					instString.append((c.x, c.y, inst.pid, inst.tid, inst.symmetryType))
				patternLib.encode(instString, box)

			if patternLib.patternCount != 1:
				continue

			# boundary elements
			patternLib = PatternLib([], {}, 0)
			boundsX, boundsY = [], []
			# leftBound = [(0, y) for y in range(sizey)]
			rightBound = [(sizex-1, y) for y in range(sizey)]
			# bottomBound = [(x, 0) for x in range(sizex)]
			topBound = [(x, sizey-1) for x in range(sizex)]
			elesBound = [(1,1)] + rightBound +topBound
			i, s1 = 0, len(rightBound)
			for x0, y0 in elesBound:
				l = array.bbox.left + array.periodX*x0
				b = array.bbox.bottom + array.periodY*y0
				r, t = l+array.periodX, b + array.periodY
				idx = list(self.polygonTree.intersection((l, b, r, t)))
				instString, ov = [], []
				box = db.Box()
				for id in idx:
					box0 = self.polygonList[id].bbox
					if box0.area() > area or box0.left < l or box0.left >= r or \
						box0.bottom < b or box0.top >= t:
						ov.append(id)
				for id in ov:
					idx.remove(id)
				for i, id in enumerate(idx):
					inst = self.polygonList[id]
					box0 = inst.bbox
					if i == 0:
						box = box0
					else:
						box = box + box0
					c = box0.center()
					instString.append((c.x, c.y, inst.pid, inst.tid, inst.symmetryType))
				inst = patternLib.encode(instString, box)
				if inst.pattern != patternLib.patternList[0]:
					if i > s1:
						boundsX.append(x0)
					else:
						boundsY.append(y0)
				i += 1
			if len(boundsX) > 1:
				sizey -= 1
			if len(boundsY) > 1:
				sizex -= 1
			array.bbox.right = array.bbox.left + array.periodX*sizex
			array.bbox.top = array.bbox.bottom + array.periodY*sizey
			keep.append(array)

		self.arrayList = keep

	def array_check_exp(self):
		"""Check elements in array group by group to make sure they are the
		same. Attentionally, boundary elements are treated different."""
		keep = []
		for array in self.arrayList:
			sizex, sizey = array.shape
			edgex, edgey = sizex-2, sizey-2
			x1, y1 = 0, 0
			# elements inside
			while edgex>1 or edgey>1:
				patternLib = PatternLib([], {}, 0)
				if edgey > 1: 	# divide along y-axis first
					if edgey%2 == 0:
						edgey = edgey/2
						x1, y1 = 1, edgey + 1
					else:
						edgey = (edgey+1)/2
						x1, y1 = 1, edgey
				else:
					if edgex%2 == 0:
						edgex = edgex/2
						x1, y1 = edgex + 1, 1
					else:
						edgex = (edgex+1)/2
						x1, y1 = edgex, 1
				box0 = (array.bbox.left + array.periodX,
						array.bbox.bottom + array.periodY,
						array.bbox.right + (edgex+1)*array.periodX,
						array.bbox.top + (edgey+1)*array.periodY)
				box1 = (array.bbox.left + x1*array.periodX,
						array.bbox.bottom + y1*array.periodY,
						array.bbox.right + (x1+edgex)*array.periodX,
						array.bbox.top + (y1+edgey)*array.periodY)
				for b0 in [box0, box1]:
					idx = self.polygonTree.intersection(b0)
					instString = []
					box = db.Box()
					for i in idx:
						inst = self.polygonList[i]
						if i == 0:
							box = inst.bbox
						else:
							box = box + inst.bbox
						c = inst.bbox.center()
						instString.append((c.x, c.y, inst.pid, inst.tid, inst.symmetryType))
					patternLib.encode(instString, box)
				if patternLib.patternCount != 1:
					continue

			# boundary elements
			patternLib = PatternLib([], {}, 0)
			leftBound = [(0, y) for y in range(sizey)]
			rightBound = [(sizex-1, y) for y in range(sizey)]
			bottomBound = [(x, 0) for x in range(sizex)]
			topBound = [(x, sizey-1) for x in range(sizex)]
			elesBound = leftBound + rightBound + bottomBound + topBound + [(1,1)]
			for x0, y0 in elesBound:
				l = array.bbox.left + array.periodX*x0
				b = array.bbox.bottom + array.periodY*y0
				r, t = l+array.periodX-1, b + array.periodY-1
				idx = self.polygonTree.intersection((l, b, r, t))
				instString = []
				box = db.Box()
				for i in idx:
					inst = self.polygonList[i]
					box0 = inst.bbox
					if box0.left>=l and box0.left<=r and box0.bottom>=b and box0.top<=t:
						if i == 0:
							box = box0
						else:
							box = box + box0
						c = box0.center()
						instString.append((c.x, c.y, inst.pid, inst.tid, inst.symmetryType))
				patternLib.encode(instString, box)
			if patternLib.patternCount == 1:
				keep.append(array)

		self.arrayList = keep

	def element_determine(self):
		"""Element directly derived from projective feature periods might not be
		the repetitive element. Therefore the elements with size of multiple
		periods are checked and determined."""
		candidates = [(1,1), (1,2), (2,1), (2,2), (1,3), (3,1), (2,3), (3,2), (3,3)]
		keep = []
		for array in self.arrayList:
			px, py = array.periodX, array.periodY
			for mx, my in candidates:
				wx, wy = px*mx, py*my
				area = wx*wy
				l, b = array.bbox.left + wx, array.bbox.bottom + wy  # origin
				idx1 = list(self.polygonTree.intersection((l, b, l+wx, b+wy)))
				idx2 = list(self.polygonTree.intersection((l, b+wy, l+wx, b+2*wy)))
				idx3 = list(self.polygonTree.intersection((l+wx, b, l+2*wx, b+wy)))
				patternLib = PatternLib([], {}, 0)
				for idx in [idx1, idx2, idx3]:
					instString, ov = [], []
					box = db.Box()
					for id in idx:
						inst = self.polygonList[id]
						if inst.bbox.area() > area:
							ov.append(id)
					for id in ov:
						idx.remove(id)

					for i, id in enumerate(idx):
						inst = self.polygonList[id]
						if i == 0:
							box = db.Box(inst.bbox)
						else:
							box = box + inst.bbox
						center = inst.bbox.center()
						instString.append((center.x, center.y, inst.pid, inst.tid, inst.symmetryType))
					patternLib.encode(instString, box)

				if patternLib.patternCount == 1:
					array.periodX, array.periodY = wx, wy
					array.bbox.right = l + math.floor(array.bbox.width()/wx)*wx
					array.bbox.top = b + math.floor(array.bbox.height()/wy)*wy
					keep.append(array)
					break
		self.arrayList = keep

	@staticmethod
	def _period_of_region(manager, start1, end1, p1, middle2, p2, axis='x'):
		"""Project all polygons of certain region to @param axis direction,
		than use feature obtained to find exact period.
		@param p1:the period along the projective axis.
		@param p2:the period along the orthogonal axis."""
		EXPAND = 10
		length = EXPAND*(end1 - start1)
		if axis == 'x':
			left, right = start1 - length, end1 + length
			bottom, top = middle2 - 2*p2, middle2 + 2*p2
		elif axis == 'y':
			bottom, top = start1 - length, end1 + length
			left, right = middle2 - 2*p2, middle2 + 2*p2
		else:
			raise ValueError("Axis sets wrong!")

		indexList = list(manager.polygonTree.intersection((left, bottom, right, top)))
		polygons = [manager.polygonList[i] for i in indexList]
		if len(polygons) == 0:
			return None

		# project the polygon instances
		feature = ProjectiveFeature()
		feature.project(polygons, mode='multiple', axis=axis)
		feature.period_proposals(mode='multiple')

		# return proper segment for the array
		if axis == 'x':
			if len(feature.segmentsX) == 0:
				return None
			else:
				for seg in feature.segmentsX:
					# choose the one containing proposals
					condition0 = start1 <= seg[0] and seg[1] <= end1
					condition1 = seg[0] <= start1 and end1 <=seg[1]
					condition2 = start1 <= seg[0] < end1 or start1 < seg[1] <= end1
					condition = condition0 or condition1 or condition2
					if  condition:
						return seg
				return None
		elif axis == 'y':
			if len(feature.segmentsY) == 0:
				return None
			else:
				for seg in feature.segmentsY:
					condition0 = start1 <= seg[0] and seg[1] <= end1
					condition1 = seg[0] <= start1 and end1 <=seg[1]
					condition2 = start1 <= seg[0] < end1 or start1 < seg[1] <= end1
					condition = condition0 or condition1 or condition2
					if condition:
						return seg
				return None

	def proposals_to_arrays_sharing(self):
		"""Begin with array proposals, scan regions of interest to determine the
		exact bounding box and periods for corresponding regions with sharing
		projective feature and periods."""

		# rtree for indexing
		proposalTree = index.Index()
		for i,proposal in enumerate(self.arrayList):
			proposalTree.insert(i, proposal.coord_tuple)

		obsoletes = {}
		classifiedX, classifiedY = {}, {}
		for i, proposal in enumerate(self.arrayList):
			if i in obsoletes:
				continue
			# x-axis
			if i not in classifiedX:
				# draw the projective box
				left, right = self.bbox.left, self.bbox.right	# world size
				middle = (proposal.bbox.bottom + proposal.bbox.top)/2
				periody = proposal.periodY
				bottom, top = middle - 2*periody,  middle + 2.5*periody
				# project the polygon instances
				sharingProps = proposalTree.intersection((left, bottom, right, top))
				indexList = list(self.polygonTree.intersection((left, bottom, right, top)))
				polygons = [self.polygonList[i] for i in indexList]
				feature = ProjectiveFeature()
				feature.project(polygons, mode='multiple', axis='x')
				feature.period_proposals(mode='multiple')

				# filter proposals and match periods
				segmTree = index.Index()
				for i, segment in enumerate(feature.segmentsX):
					segmTree.insert(i, (segment[0], 0, segment[1], 1))
				for ix in sharingProps:
					if ix in classifiedX:
						continue
					p = self.arrayList[ix]
					pl, pb, pr, pt = p.coord_tuple
					ppy = p.periodY
					if (pb <= bottom) and (pt >= top) and (4*periody > ppy):
						classifiedX[ix] = 0
						touches = list(segmTree.intersection((pl, 0, pr, 1)))
						if touches:
							segm = feature.segmentsX[touches[0]]
							self.arrayList[ix].update(segm)
						else:
							obsoletes[ix] = 0	# fake arrays
					else:
						obsoletes[ix] = 0
			# y-axis
			if i not in classifiedY:
				# draw the projective box
				bottom, top = self.bbox.bottom, self.bbox.top	# world size
				middle = (proposal.bbox.left + proposal.bbox.right)/2
				periodx = proposal.periodX
				left, right = middle - 2*periodx, middle + 2.5*periodx
				# project the polygon instances
				sharingProps = proposalTree.intersection((left, bottom, right, top))
				indexList = list(self.polygonTree.intersection((left, bottom, right, top)))
				polygons = [self.polygonList[i] for i in indexList]
				feature = ProjectiveFeature()
				feature.project(polygons, mode='multiple', axis='y')
				feature.period_proposals(mode='multiple')

				# filter proposals and match periods
				segmTree = index.Index()
				for i, segment in enumerate(feature.segmentsY):
					segmTree.insert(i, (segment[0], 0, segment[1], 1))
				for ix in sharingProps:
					if ix in classifiedY:
						continue
					p = self.arrayList[ix]
					pl, pb, pr, pt = p.coord_tuple
					ppx = p.periodX
					if (pl <= left) and (pr >= right) and (4*periodx > ppx):
						classifiedY[ix] = 0
						touches = list(segmTree.intersection((pb, 0, pt, 1)))
						if touches:
							segm = feature.segmentsY[touches[-1]]
							self.arrayList[ix].update(segm, axis='y')
						else:
							obsoletes[ix] = 0	# fake arrays
					else:
						obsoletes[ix] = 0

		# update array list
		realArrays = []
		for i, array in enumerate(self.arrayList):
			if i not in obsoletes:
				array = self.arrayList[i]
				realArrays.append(PArray(array.bbox, array.periodX, array.periodY))
		self.arrayList = realArrays

	def visualize(self):
		"""Combine all arrays's bounding boxes and box of bottom left most element."""
		regions, area = [], 0
		for array in self.arrayList:
			area += array.bbox.area()
			left, bottom = array.bbox.left, array.bbox.bottom
			element = db.Box(left, bottom, left+array.periodX, bottom+array.periodY)
			regions.extend([array.bbox, element])

		print('Array area is {}, array count is {}.'.format(area, len(self.arrayList)))
		return regions
