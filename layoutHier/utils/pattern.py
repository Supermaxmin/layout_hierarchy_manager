"""
@author: 	Meenchow Yin
@date: 		2019.05.01
@modified:	2019.05.21
			2019.06.17 Insert methold of Pattern is optimized.
			2019.11.11 Class ProjectiveFeature is added.
			2019.12.17 Class template is added.
@version: 	1.2
@brief:     encoder of via layer cluster resulters(variant of polygon encoder)
Encode of via layer cluster resulters to string  which converts
the geometry-based layout into (x,y,PID,TID) like layout and the auxiliary library.
"""

import copy
import math
import operator

import klayout.db as db
from rtree import index

from layoutHier.utils.helpers import *
from layoutHier.utils.structures import *

__all__ = ["ProjectiveFeature", "PolygonInst", "PolygonPattern", "PolygonLib",\
			"Instance", "Template", "Pattern", "PatternLib"]


class ProjectiveFeature(object):
	"""The projective feature is exactly (1) a list of (x/y coordinate, polygons'
	number) for one polygon pattern or (2) a list of (x/y coordinate, pid, poly-
	gons' number) for multi-patterns in a region. They both reflect the distribu-
	tion along x/y direction."""

	def __init__(self, fx=None, fy=None, segmentsX=None, segmentsY=None, threshold=4):
		"""x,y projective feature and the threshold for Array finding. """
		self.featureX = fx
		self.featureY = fy
		self.segmentsX = segmentsX
		self.segmentsY = segmentsY
		self.THRESH = threshold

	@property
	def feature(self):
		return (self.featureX, self.featureY)

	@feature.setter
	def feature(self, f):
		"""f feature should be duo tuple or list."""
		assert len(f) == 2, 'length of feature should be two.'
		self.featureX = f[0]
		self.featureY = f[1]

	def project(self, polygonList, mode='single', axis='x'):
		"""Project polygons to the @param axis to form feature.
		@param polygon: it can be a polygon instance.
		@param mode: 'single' or 'multiple'.
		@param axis: projection axis, 'x', 'y' or 'both'."""
		assert isinstance(polygonList[0], PolygonInst), "Polygon must be an instance."
		dictX = {}
		dictY = {}
		for polygon in polygonList:
			left, bottom = polygon.bbox.left, polygon.bbox.bottom
			if mode == 'single':
				if axis == 'x' or axis == 'both':
					if left in dictX:
						dictX[left] = (dictX[left][0], dictX[left][1]+1)
					else:
						dictX[left] = (left, 1)
				if axis == 'y' or axis == 'both':
					if bottom in dictY:
						dictY[bottom] = (dictY[bottom][0], dictY[bottom][1]+1)
					else:
						dictY[bottom] = (bottom, 1)
			elif mode == 'multiple':
				if axis == 'x' or axis == 'both':
					key = (left, polygon.pid)
					if key in dictX:
						dictX[key] = (dictX[key][0], dictX[key][1], dictX[key][2]+1)
					else:
						dictX[key] = (key[0], key[1], 1)
				if axis == 'y' or axis == 'both':
					key = (bottom, polygon.pid)
					if key in dictY:
						dictY[key] = (dictY[key][0], dictY[key][1], dictY[key][2]+1)
					else:
						dictY[key] = (key[0], key[1], 1)
			else:
				raise Exception("mode is 'single' or 'multiple'.")

		self.featureX = [x for x in dictX.values()]
		self.featureY = [y for y in dictY.values()]
		if mode == 'single':
			self.featureX.sort(key= lambda x: x[0])
			self.featureY.sort(key= lambda x: x[0])
		elif mode == 'multiple':
			self.featureX.sort(key = lambda x: (x[0], x[1]))
			self.featureY.sort(key= lambda x: (x[0], x[1]))

	def period_proposals(self, mode='single'):
		"""To search the possible array proposals through x,y projective feature.
		@param mode: 'single' for one pattern or 'multiple' for multi-patterns."""
		#find period segments along both axis
		if self.featureX:
			if mode == 'single':
				self.segmentsX = ProjectiveFeature._period_find_multiscale(
					self.featureX, self.THRESH)
			elif mode == 'multiple':
				self.segmentsX = ProjectiveFeature._period_find_multiple(
					self.featureX, self.THRESH)
		if self.featureY:
			if mode == 'single':
				self.segmentsY = ProjectiveFeature._period_find_multiscale(
					self.featureY, self.THRESH)
			elif mode == 'multiple':
				self.segmentsY = ProjectiveFeature._period_find_multiple(
					self.featureY, self.THRESH)

	@staticmethod
	def _period_find_multiscale(feature, THRESH):
		"""	Find all possible periods in the projective feature with complex
		criterion--downsample the feature and find periods multiscaly.
		@return a list of periodic segments."""
		SCALE = 15
		# find periods multiscaly
		scale = 1
		periodSegments = []
		while scale < SCALE:
			coarseFeature = [x for (i, x) in enumerate(feature) if i%scale == 0]
			periodSegments.extend(ProjectiveFeature._period_find_simple(
								  coarseFeature, THRESH))
			scale += 1
		# analyze relations between different periodic segments ,than keep longest
		keep, remove = [], {}
		segmentsTree = index.Index()  # segments rtree for selection
		periodSegments.sort(key=lambda x: x[1]-x[0], reverse=True)
		for i, segment in enumerate(periodSegments):
			segmentsTree.insert(i, (segment[0], 0, segment[1], 1))

		for i, segment in enumerate(periodSegments):
			if i in remove:
				continue
			keep.append(segment)
			temp = segmentsTree.intersection((segment[0], 0, segment[1], 1))
			for j in temp:
				if j != i:
					remove[j] = j
		# sort periodic segments in ascending order along axis
		keep.sort(key=lambda x: x[0])
		return keep

	@staticmethod
	def _period_find_simple(feature, THRESH):
		"""Find periodic segments in the projective feature with adjacent
		leap consistent criterion."""
		freshingSegments = {}   # value = (start_coord, end_coord, leap, number)
		periodSegments = []
		for (coord, num) in feature:
			if num < THRESH:
				continue
			if num in freshingSegments:
				start, end, leap, number = freshingSegments[num]
				leap0 = coord - end
				if leap == 0:
					freshingSegments[num] = (start, coord, leap0, 2)
				elif leap == leap0:
					freshingSegments[num] = (start, coord, leap0, number+1)
				else:
					freshingSegments[num] = (coord, coord, 0, 1)
					# append the periodic segment
					if number > THRESH:
						periodSegments.append((start, end, leap))
			else:
				freshingSegments[num] = (coord, coord, 0, 1)
		# deal with the remaining segments
		for segment in freshingSegments.values():
			if segment[2] != 0 and segment[3] > THRESH:
				periodSegments.append(segment[:3])
		return periodSegments

	@staticmethod
	def _period_find_multiple(feature, THRESH):
		"""Find periodic segments for multi-patterns projective feature.
		@return a list of periodic segments."""
		MAX_PERIOD = 100     # max gap numbers for a period
		KEYLEN = 7
		LAST = len(feature)
		if LAST < 14:
			KEYLEN = 3
		# dots like (distance between 2 projections, polygon id, polygon's num)
		dotQueue = [(0,0,0) for i in range(MAX_PERIOD)]
		keyDict, segments, dots = {}, [], []
		ruler, start, Match = 0, 0, False
		for i in range(LAST-1):
			dots.append((feature[i+1][0]-feature[i][0], feature[i][1], feature[i][2]))

		for i, dot in enumerate(dots):
			dotQueue = [dot] + dotQueue[:MAX_PERIOD-1]

			if Match:
				assert ruler > 0, "Ruler {} should be greater than 0.".format(ruler)

				if dot != dotQueue[ruler] or i == LAST-2:	# exception for last one
					# record periodic segments
					period = feature[start+ruler][0] - feature[start][0]
					small = feature[start][0]
					big = feature[i+1][0] if i == LAST-2 else feature[i][0]
					numWhole = math.ceil((big-small)/period)
					# go back to search mode
					ruler, start, Match = 0, 0, False
					dotQueue = [(0,0,0) for i in range(MAX_PERIOD)]
					segments.append((small, big, period, numWhole))
				else:
					continue
			else:
				key = tuple(dotQueue[KEYLEN-1::-1])
				if key in keyDict:
					# switch into match mode
					start = keyDict[key]
					ruler = i - start
					start -= KEYLEN-1
					forward = i + ruler
					if forward < LAST-1 and dots[forward] != dots[i]:
						keyDict[key] = i
						key0 = tuple(dotQueue[MAX_PERIOD-1:MAX_PERIOD-KEYLEN-1:-1])
						if key0 in keyDict:
							keyDict.pop(key0)
					else:
						keyDict.clear()
						Match = True
				else:
					# keep searching
					keyDict[key] = i
					key0 = tuple(dotQueue[MAX_PERIOD-1:MAX_PERIOD-KEYLEN-1:-1])
					if key0 in keyDict:
						keyDict.pop(key0)
		segments.sort(key=lambda x: x[0])

		return segments


class PolygonInst(object):
	"""String-based polygon which is composed of polygon ID and transformation ID."""

	def __init__(self, bbox=None, pid=None, tid=None, symmetryType=0, visited=False):
		"""Polygon instance class which keep some necessary infomation for
		@param bbox: bounding of the polygon
		@param visited: flag indicating whether it has been visited or not in a
		propagation without discarding"""
		self.bbox = bbox
		self.pid = pid
		self.tid = tid
		self.symmetryType = symmetryType
		self.visited = visited


class PolygonPattern(object):
	"""The basic element of the auxiliary library which corresponds to cluster
	code one by one."""
	def __init__(self, pid=None, symmetryType=None, code=None, instList=[], feature=None):

		self.pid = pid
		self.symmetryType = symmetryType
		self.code = code
		self.instList = instList
		if not feature:
			feature  = ProjectiveFeature()
		self.feature = feature

	def __len__(self):
		return len(self.instList)

	def __str__(self):
		return "PID:%d, TID:%d" %(self.pid, self.symmetryType)

	def insert(self, instance):
		# for x in self.instList:
			# if instance.bbox == x.bbox:
				# return
		self.instList.append(instance)
		# maintain the order
		# self.instList.sort(key = lambda x: (x.bbox.left, x.bbox.right))

	def restore(self, instance):
		"""compatible for polygon pattern propagation directly."""

		if instance.pid != self.pid:
			print("Instance and pattern does not match!")
			return
		centerx = (instance.bbox.left + instance.bbox.right)/2
		centery = (instance.bbox.bottom + instance.bbox.top)/2
		instString = list()
		instString.append((centerx, centery, instance.pid, instance.tid, instance.symmetryType))
		return instString

	def project(self):
		"""Project the polygon instances in the pattern' instList to x/y axis so
		that x/y features and periodic segments are derived."""
		self.feature.project(self.instList, mode='single', axis='both')
		self.feature.period_proposals(mode='single')


class PolygonLib(object):
	"""
	This encapsulate a 2-dim list and a dict to realise bidirectional search.
	patternList[PatternCount] = basic pattern,
	codeDict[code] = [PID][TID]
	"""

	def __init__(self, patternList=[], codeDict={}, patternCount=0, type='polygon'):
		assert(type == 'polygon' or type == 'cluster')

		self.patternList = patternList
		self.codeDict = codeDict
		self.patternCount = patternCount      #indicating the pattern number in lib
		self.type = type

	def encode(self, bbox, pointList):
		"""
		Encode the cluster/polygon met into instance and element in the library,
		here are 2 situtations,that is, cluster/polygon is first met or not.
		@param bbox: bounding box of the encoding instance
		@param pointList: point list of the encoding instance,its order is
		counter-clockwise for polygon or lexicographically ordered for cluster.
		"""
		# sort as need
		if self.type == 'polygon':
			length = len(pointList)
			lableMin = 0
			for i in range(length):
				if pointList[i] < pointList[lableMin] :
					lableMin = i
				else:
					lableMin = lableMin
			pointList_1 = list()
			for i in range(length):
				pointList_1.append( pointList[(i+lableMin)%length] )
			pointList = pointList_1

		elif self.type == 'cluster':
			pointList.sort()
		else:
			print('Wrong object type! Neither polygon nor cluster!')
			return
		code1 = list()
		for i in range(1,len(pointList)):
			code1.append(  (pointList[i][0] - pointList[0][0], pointList[i][1] - pointList[0][1]) )

		# check if the O1 code exists in library
		if tuple(code1) in self.codeDict:	# hush map for quick enqury for dictionary
			# add the instance to the corresponding pattern
			pid = self.codeDict.get(tuple(code1))[0]
			tid = self.codeDict.get(tuple(code1))[1]
			symmetry = self.patternList[pid].symmetryType
			inst = PolygonInst(bbox, pid, tid, symmetry)
			self.patternList[pid].insert(inst)
		else:
			codeList = list()
			codeList.append(code1)                         #for O1
			codeList.append(code_transform_basic(code1, O2, self.type))     #for O2
			codeList.append(code_transform_basic(code1, O3, self.type))     #for O3
			codeList.append(code_transform_basic(code1, O4, self.type))     #for O4
			codeList.append(code_transform_basic(code1, O5, self.type))     #for O5
			codeList.append(code_transform_basic(code1, O6, self.type))     #for O6
			codeList.append(code_transform_basic(code1, O7, self.type))     #for O7
			codeList.append(code_transform_basic(code1, O8, self.type))     #for O8

			dict = {}						# oidTotid of the current cluster
			tidCodeList = [code1]			# tid related cluster code
			for i in range(8):				# get the oid-to-tid relation
				length = len(tidCodeList)
				for j in range(length):
					if codeList[i] == tidCodeList[j]:
						dict[OID(i + 1)] = TID(j + 1)
						break
					if j == length - 1:
						dict[OID(i + 1)] = TID(length + 1)
						tidCodeList.append(codeList[i])

			# obtain the symmetry of the cluster
			symmetryType = 0
			for i in range(8):
				if operator.eq(dict, oidToTid[i]):
					symmetryType = i
					break

			# assign the pattern library number
			pid = self.patternCount			# PID range from 0
			self.patternCount += 1			# update

			# update the pattern library
			inst = PolygonInst(bbox, pid, T1, symmetryType)
			pattern = PolygonPattern(pid, symmetryType, tidCodeList, [inst])
			for i in range(len(tidCodeList)):
				x = tidCodeList[i]
				self.codeDict[ tuple(x) ] = [pid, TID(i+1)]     # update code dictionary
			self.patternList.append(pattern)                    # update pattern list

		return inst


class Template(object):
	"""Template is simplified version of Class Pattern which only encode layout
	once without transformation. In other words, it is translation invariant."""

	def __init__(self, template):
		self.template = template

	@classmethod
	def instance_template(cls, instance):
		"""Create template from an polygon instance."""
		template = [(0, 0, inst0.pid, inst0.tid, inst0.symmetryType)]
		return cls(template)

	def __iter__(self):
		for t in self.template:
			yield t

	def __len__(self):
		return len(self.template)

	def merge(self, seed1, template, seed2, lowerleft):
		"""Merge two, given two templates and their instances(bounding boxes)."""
		all = []
		for point in seed1:
			for s in self.template:
				all.append((s[0]+point[0]-lowerleft[0], s[1]+point[1]-lowerleft[1], s[2], s[3], s[4]))
		for point in seed2:
			for s in template:
				all.append((s[0]+point[0]-lowerleft[0], s[1]+point[1]-lowerleft[1], s[2], s[3], s[4]))

		return Template(all)

class Instance(object):
	"""Instance of the repeating pattern."""

	def __init__(self, bbox=None, pid=None, tid=None, pattern=None, ci=[]):
		self.bbox = bbox
		self.pid = pid
		self.tid = tid
		self.pattern = pattern
		self.childInsts = ci

	@classmethod
	def deepcopy(cls, inst):
		box = db.Box(inst.bbox)
		return cls(box, inst.pid, inst.tid, inst.pattern)

	def __eq__(self, inst):
		if self.bbox.left==inst.bbox.left and self.bbox.bottom==inst.bbox.bottom:
			return True
		else:
			return False

	def __lt__(self,  inst):
		if self.bbox.left < inst.bbox.left:
			return True
		elif self.bbox.left==inst.bbox.left and self.bbox.bottom<inst.bbox.bottom:
			return True
		else:
			return False


class Pattern(object):
	"""
	Repeating pattern offers following metholds；
	@Return the 5-tuple like string when instance given;
	"""

	def __init__(self, pid = None, symmetryType = None, code = [], instList = [],
	 			polygonList = [], childPatterns = []):
		"""polygonList param is used to record the polygons making up pattern.
		@param polygonList: polygons composing the pattern.
		@param childPatterns: largest patterns whose part instances are covered
		by the pattern"""
		self.pid = pid
		self.symmetryType = symmetryType
		self.code = code
		self.instList = instList
		self.polygonList = polygonList
		self.childPatterns = childPatterns
		self.rtree = index.Index()
		self.cell = db.Cell()	# comresponding to pattern
		self.cell_build = False
		self.__instFlag = {}

	def __len__(self):
		return len(self.instList)

	def __iter__(self):
		for inst in self.instList:
			yield inst

	@classmethod
	def from_basic(cls, basicPattern):
		"""convert basic pattern(polygon) into repeating pattern."""
		pid = basicPattern.pid
		symmetryType = basicPattern.symmetryType
		codeList = list()
		instL = list()
		for i in range(len(tidToOid[symmetryType])):
			codeList.append( [(0, 0, pid, TID(i+1), symmetryType)] )
		for inst in basicPattern.instList:
			instL.append(Instance(inst.bbox, pid, inst.tid, ci=[]))
		instL.sort(key = lambda x: (x.bbox.left, x.bbox.bottom))
		return cls(pid, symmetryType, codeList, instL)

	@classmethod
	def deepcopy(cls, pattern):
		instList = []
		for inst in pattern.instList:
			instList.append(Instance.deepcopy(inst))
		code = copy.deepcopy(pattern.code)
		return cls(pattern.pid, pattern.symmetryType, code, instList)

	def area(self):
		return self.instList[0].bbox.area()*len(self)

	def inside(self, inst):
		"""Assert if an instance is inside the pattern."""
		overlappings = list(self.rtree.intersection(box_tuple(inst.bbox)))
		if len(overlappings) == 1:
			return inst.bbox.inside(self.instList[overlappings[0]].bbox)
		else:
			return False

	def overlap(self, upper):
		"""Check the overlapping type.
		@return:
			0 	self is outside of upper,
			1	self is inside of upper,
			2	self is part overlapping with upper.
		"""
		for inst in upper.instList:
			box = inst.bbox
			touches = list(self.rtree.intersection(box_tuple(box)))
			if touches:
				insideFlag = True
				for i in touches:
					if not self.instList[i].bbox.inside(box):
						insideFlag = False
						break
				if insideFlag:
					return 1
				else:
					return 2

		return 0

	def someInst(self, indexes):
		return [self.instList[i] for i in indexes]

	def remainings(self):
		"""Iterate over instances which do not appear in the @member instFlag."""
		for i in range(len(self)):
			if i not in self.__instFlag:
				yield self.instList[i]

	def instFlag_update(self, indexes):
		"""Update @member instFlag."""
		assert isinstance(indexes, (list, tuple)), "{} should be list or tuple.".format(indexes)
		for i in indexes:
			self.__instFlag[i] = 0

	def rtree_update(self):
		for i, inst in enumerate(self.instList):
			self.rtree.insert(i, box_tuple(inst.bbox))

	def pid_update(self, newPid):
		"""update pid with new pid when pattern is inserted into a new pattern library."""
		self.pid = newPid
		for inst in self.instList:
			inst.pid = newPid

	def is_same(self, pattern):
		"""check both code and instance list."""
		if self.code == pattern.code:		# pattern code is sorted
			length = len(self.instList)
			return True
		else:
			return False

	def is_include(self, pattern):
		"""check instance list."""
		length = len(self.instList)
		if length == len(pattern.instList):
			for inst in self.instList:
				if pattern.instList[0].bbox.inside(inst.bbox):
					return True
			return False
		else:
			return False

	def insert(self, instance):
		"""insert a existing instance to the corresponding pattern with it's uniqueness checking."""
		# maintain the order
		right = len(self.instList)-1
		left = 0
		while True:
			if left == right:
				if instance == self.instList[left]:
					pass
				elif instance < self.instList[left]:
					self.instList.insert(left, instance)
				else:
					self.instList.insert(left+1, instance)
				return
			middle = (left+right)//2
			if instance == self.instList[middle]:
				return
			elif instance < self.instList[middle]:
				left, right = left, max(middle-1,left)
			else:
				left, right = middle+1, right

	def restore(self, instance):
		if instance.pid != self.pid:
			print("Instance and pattern does not match!")
			return
		centerx = (instance.bbox.left + instance.bbox.right)/2
		centery = (instance.bbox.bottom + instance.bbox.top)/2
		instString = list()
		for ele in self.code[instance.tid.value - 1]:
			instString.append((ele[0]+centerx, ele[1]+centery, ele[2], ele[3], ele[4]))
		return instString

	def insert_polygon(self, polygon):
		self.polygonList.append(polygon)


class PatternLib(object):
	"""
	Repeating pattern library includes set of repeating patterns and map between code and PID/TID.
	"""

	def __init__(self, patternList = [], codeDict = {}, patternCount = 0):
		self.patternList = patternList			# PID equal the index
		self.codeDict = codeDict
		self.patternCount = patternCount

	def __iter__(self):
		for p in self.patternList:
			yield p

	@classmethod
	def from_basic(cls, basicLib):
		patternL = list()
		codeD = {}
		for pattern in basicLib.patternList:
			patternL.append(Pattern.from_basic(pattern))
			for i in range(len(tidToOid[pattern.symmetryType])):
				codeD[((0, 0, pattern.pid, TID(i+1), pattern.symmetryType))] = [pattern.pid, TID(i+1)]
		return cls(patternL, codeD, basicLib.patternCount)

	def encode(self, instString, bbox):
		"""encode the 5-tuple like string as the pattern and instance.
		   (centerx, centery, inst.pid, inst.tid, inst.symmetryType)
		"""
		# check if the pattern exists in library
		instString.sort(key = lambda x: (x[0], x[1], x[2], x[3].value))
		centerx = (bbox.left + bbox.right)/2
		centery = (bbox.bottom + bbox.top)/2
		code1 = list()
		for ele in instString:
			code1.append((ele[0]-centerx, ele[1]-centery, ele[2], ele[3], ele[4]))	# translation invariant
		if tuple(code1) in self.codeDict:	# hush map for quick enqury for dictionary
			# add the instance to the corresponding pattern
			pid = self.codeDict.get(tuple(code1))[0]
			inst = Instance(bbox, pid, self.codeDict.get(tuple(code1))[1], self.patternList[pid],ci=[])
			self.patternList[pid].insert(inst)
		else:
			codeList = list()
			codeList.append(code1)                         #for O1
			codeList.append(code_transform(code1, O2))     #for O2
			codeList.append(code_transform(code1, O3))     #for O3
			codeList.append(code_transform(code1, O4))     #for O4
			codeList.append(code_transform(code1, O5))     #for O5
			codeList.append(code_transform(code1, O6))     #for O6
			codeList.append(code_transform(code1, O7))     #for O7
			codeList.append(code_transform(code1, O8))     #for O8

			dict = {}						# oidTotid of the current cluster
			tidCodeList = [code1]			# tid related cluster code
			for i in range(8):				# get the oid-to-tid relation
				length = len(tidCodeList)
				for j in range(length):
					if codeList[i] == tidCodeList[j]:
						dict[OID(i + 1)] = TID(j + 1)
						break
					if j == length - 1:
						dict[OID(i + 1)] = TID(length + 1)
						tidCodeList.append(codeList[i])

			# obtain the symmetry of the cluster
			symmetryType = 0
			for i in range(8):
				if operator.eq(dict, oidToTid[i]):
					symmetryType = i
					break

			# assign the pattern library number
			pid = self.patternCount			# PID range from 0
			self.patternCount += 1			# update

			# update the pattern library
			box = db.Box(bbox)
			inst = Instance(box, pid, T1, ci=[])
			pattern = Pattern(pid, symmetryType, tidCodeList, [inst], [], [])
			inst.pattern = pattern
			for i in range(len(tidCodeList)):
				x = tidCodeList[i]
				self.codeDict[ tuple(x) ] = [pid, TID(i+1)]     #update code dictionary
			self.patternList.append(pattern)                    #update pattern list

		return inst

	def any_same(self, pattern):
		"""check if any pattern is the same as the given pattern."""
		if not tuple(pattern.code[0]) in self.codeDict:
			return False
		# pid = self.codeDict[tuple(pattern.code[0])][0]
		# pattern1 = self.patternList[pid]
		# return pattern1.is_same(pattern)
		else:
			return True

	def any_include(self, pattern):
		"""
		check if the given pattern is included by any pattern.
		if True update the hierarchy infomation of the corresponding pattern.
		"""
		for pattern1 in self.patternList:
			if pattern1.is_include(pattern):
				childP = pattern.childPatterns
				if len(childP) > 0 and childP[0] not in pattern1.childPatterns:
					# avoid including the same LR Pattern many times
					pattern1.childPatterns.extend(pattern.childPatterns)  #included pattern can't be LR pattern
				return True
		return False

	def insert(self, pattern):
		"""insert a existing pattern into the pattern library."""
		# pattern.pid_update(self.patternCount)
		self.patternList.append(pattern)
		for i in range(len(pattern.code)):
			x = pattern.code[i]
			self.codeDict[ tuple(x) ] = [pattern.pid, TID(i+1)]
		self.patternCount += 1

	def remove(self, pattern):
		"""remove a existing pattern from the pattern library."""
		self.patternCount = self.patternCount-1
		id = pattern.pid
		# codeList = pattern.code
		self.patternList.pop(id)     #pid is maintained
		# for i in range(id, self.patternCount):
			# self.patternList[i].pid = i
			# for code in codeList:
				# self.codeDict.get(tuple(code))[0] = i

	def pattern_rtree_construct(self):
		"""Construct rtree for all patterns after library becomes stale."""
		for pattern in self.patternList:
			pattern.rtree_update()
