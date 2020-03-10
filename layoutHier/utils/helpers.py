"""
@author: 	Meenchow Yin
@date: 		2019.12.17	initial version;
			2020.02.24 	all helper functions are aggregated.
@version: 	0.2
@brief:     Define some help functions.
"""

import klayout.db as db
from rtree import index

from layoutHier.utils.structures import *


def lcm(a, b):
	"""Calculate least common multiple of a pair of given integer."""
	assert a > 0 and b > 0 and isinstance(a, int) and isinstance(b, int), \
			"For inputs{}, positive integers only!".format((a,b))

	m, n = a, b
	# greatest common divisor
	while b != 0:
		c = a%b
		a, b = b, c
	return int(m*n/a)

#********maximal repetition finding********
def maximal_periods(string):
	"""Implementation of an algorithm computing the repetitions in a word. Please
	refer to <An optimal algorithm for computing the repetitions in a word>."""

	assert isinstance(string, (str, tuple, list)), "Input should be iterable."

	# initialize all data structures
	N = len(string)
	# positions [0: N], index [0: 2*N]
	small = []
	D, E = [0 for i in range(N)], [0 for i in range(N)]
	dClass = [DLinkList() for i in range(2*N)]
	eClass = [DLinkList() for i in range(2*N)]
	nodeListd = [Node(i) for i in range(N)]  # wrapper of position for fast transfer
	nodeListe = [Node(i) for i in range(N)]  # wrapper of position for fast transfer
	newIndex = list(range(2*N-1, -1, -1))   # stack

	eleDict = {}
	for pos, ele in enumerate(string):
		if ele in eleDict:
			k = eleDict[ele]
			E[pos] = k
			eClass[k].append(nodeListe[pos])
		else:
			k = newIndex.pop()
			eleDict[ele] = k
			E[pos] = k
			eClass[k].append(nodeListe[pos])
			small.append(k)

	eleDict = {}
	for pos, ele in enumerate(string):
		if ele in eleDict:
			j = eleDict[ele]
			eleDict[ele] = pos
			D[j] = pos - j
			dClass[D[j]].append(nodeListd[j])
		else:
			eleDict[ele] = pos
	for pos in eleDict.values():
		D[pos] = -1 # inf
	p, repetitions = 1, []


	while small:
		subClass = [[] for _ in range(N)]
		lastSmall = [-1 for _ in range(N)]
		queue, split = [], {}
		# computation of the maximal repetitions of period partition
		exclude = {}
		for i in dClass[p].range_values():
			if i not in exclude:
				origin = i
				e = 1
				exclude[i] = 0
				while (i+p < N and D[i+p] == p):
					i, e = i + p, e + 1
					exclude[i] = 0
				repetitions.append((origin, p, e+1))
		p += 1
		if p > N/2:
			return repetitions

		# copy of small classes in Queue
		while small:
			s = small.pop(0)
			for j in eClass[s].range_values():
				if j == 0:
					continue
				queue.append((j, s))
				k = E[j-1]
				if k not in split:
					split[k] = k
					subClass[k].append(k)
					lastSmall[k] = -1

		# computations of new values of Equivalences and Differences
		while queue:
			j, s = queue.pop(0)
			i = j - 1
			k = E[i]
			if lastSmall[k] != s:
				lastSmall[k] = s
				newI = newIndex.pop()
				subClass[k].append(newI)
			kNew = subClass[k][-1]
			nodeIprev = nodeListe[i].prev
			if nodeIprev is not None:
				i_ = nodeIprev.value
				node = nodeListd[i_]
				if D[i_] > 0:
					dClass[D[i_]].delete(node)
					D[i_] += D[i]
					dClass[D[i_]].append(node)

			# transfer i at the end of eClass[kNew]
			eClass[k].delete(nodeListe[i])
			eClass[kNew].append(nodeListe[i])
			E[i] = kNew
			if D[i] > 0:
				dClass[D[i]].delete(nodeListd[i])
			D[i] = -1
			nodeIprev = nodeListe[i].prev
			if nodeIprev is not None:
				i_ = nodeIprev.value
				node = nodeListd[i_]
				if D[i_] > 0:
					dClass[D[i_]].delete(node)
				D[i_] = i - i_
				dClass[D[i_]].append(node)

		# determination of the small classes
		splitSet = list(split.keys())
		for k in splitSet:
			if eClass[k].count == 0:
				newIndex.append(k)
				subClass[k].remove(k)	  # k should be the first
			if len(subClass[k]) > 0:
				big = subClass[k][0]
				for c in subClass[k]:
					if eClass[c].count > eClass[big].count:
						big = c
				for c in subClass[k]:
					if c == big:
						continue
					small.append(c)
	return repetitions


#********fundamental functions for Pattern********

def inst_enlarge(bbox, instList, rtree, incremental=False):
	"""Enlarge the given instance in all direction and return the new instance list.
	@param bbox  the bounding box of the instance.
	@param instList  the list containing element instances.
	@param rtree  all basic element index are stored in a rtree.
	"""
	workingLen = 1000

	flagLeft, flagBottom, flagRight, flagTop = False, False, False, False
	stringList, boxList = [], []
	(instLeft, instBottom, instRight, instTop) = box_tuple(bbox)
	if incremental:
		#elements (polygon) forming the instance
		formerList = list(rtree.intersection((instLeft, instBottom, instRight, instTop)))

	#left direction
	aimRegion = (instLeft - workingLen, instBottom, instLeft-1, instTop)
	leftBar = (instLeft-1, instBottom, instLeft-1, instTop)
	flagLeft, nearestLeft = nearest_element(rtree, instList, aimRegion, leftBar)         #obtain the nearest element
	if flagLeft:
		bboxSeed = db.Box(bbox.left, bbox.bottom, bbox.right, bbox.top) + nearestLeft.bbox                                  #merge box to get original box
		bboxStable1, inst1 = box_expand(bboxSeed, instList, rtree)              #expand the seed to get new stale inst without cutting
		if incremental:
			for idx in formerList:
				inst1.remove(idx)
			string1 = indexes_to_string(inst1, instList)
			string1.append(( (instLeft+instRight)/2, (instBottom + instTop)/2, -1, T1, 7))
		else:
			string1 = indexes_to_string(inst1, instList)
		stringList.append(string1)
		boxList.append(bboxStable1)

	#bottom direction
	aimRegion = (instLeft, instBottom-workingLen, instRight, instBottom-1)
	bottomBar = (instLeft, instBottom, instRight, instBottom)
	flagBottom, nearestBottom = nearest_element(rtree, instList, aimRegion, bottomBar)
	if flagBottom:
		not_same = True
		bboxSeed = db.Box(bbox.left, bbox.bottom, bbox.right, bbox.top) + nearestBottom.bbox
		bboxStable2, inst2 = box_expand(bboxSeed, instList, rtree)
		for boxx in boxList:
			if boxx == bboxStable2:
				not_same = False
		if not_same:
			if incremental:
				for idx in formerList:
					inst2.remove(idx)
				string2 = indexes_to_string(inst2, instList)
				string2.append(( (instLeft+instRight)/2, (instBottom + instTop)/2, -1, T1, 7))
			else:
				string2 = indexes_to_string(inst2, instList)
			stringList.append(string2)
			boxList.append(bboxStable2)

	#right direction
	aimRegion = (instRight+1, instBottom, instRight+workingLen, instTop)
	rightBar = (instRight, instBottom, instRight, instTop)
	flagRight, nearestRight = nearest_element(rtree, instList, aimRegion, rightBar)
	if flagRight:
		not_same = True
		bboxSeed = db.Box(bbox.left, bbox.bottom, bbox.right, bbox.top) + nearestRight.bbox
		bboxStable3, inst3 = box_expand(bboxSeed, instList, rtree)
		for boxx in boxList:
			if boxx == bboxStable3:
				not_same = False
		if not_same:
			if incremental:
				for idx in formerList:
					inst3.remove(idx)
				string3 = indexes_to_string(inst3, instList)
				string3.append(( (instLeft+instRight)/2, (instBottom + instTop)/2, -1, T1, 7))
			else:
				string3 = indexes_to_string(inst3, instList)
			stringList.append(string3)
			boxList.append(bboxStable3)

	#top direction
	aimRegion = (instLeft, instTop+1, instRight, instTop+workingLen)
	topBar = (instLeft, instTop, instRight, instTop)
	flagTop, nearestTop = nearest_element(rtree, instList, aimRegion, topBar)
	if flagTop:
		not_same = True
		bboxSeed = db.Box(bbox.left, bbox.bottom, bbox.right, bbox.top) + nearestTop.bbox
		bboxStable4, inst4 = box_expand(bboxSeed, instList, rtree)
		for boxx in boxList:
			if boxx == bboxStable4:
				not_same = False
		if not_same:
			if incremental:
				for idx in formerList:
					inst4.remove(idx)
				string4 = indexes_to_string(inst4, instList)
				string4.append(( (instLeft+instRight)/2, (instBottom + instTop)/2, -1, T1, 7))
			else:
				string4 = indexes_to_string(inst4, instList)
			stringList.append(string4)
			boxList.append(bboxStable4)

	return stringList, boxList

def nearest_element(rtree, instList, aimRegion, aimBar):
	"""Search one direction(left,right,bottom,top) which is represented by aimRegion
	to find the nearest element and return it .
	@param rtree  the rtree structure storing elements index.
	@param instList  the list containing element instances.
	@param aimRegion  the region indicating search region.
	"""

	candidates = list(rtree.intersection( aimRegion) )
	candTree = index.Index()
	for i in candidates:
		candTree.insert(i, box_tuple(instList[i].bbox) )
	nearest = list(candTree.nearest(aimBar, 1))

	if nearest:
		inst = instList[nearest[0]]
		if inst.visited: 		#instance with visited True has been propagated for all, so prune.
			flag = False
		else:
			flag = True
	else:
		inst = None
		flag = False
	return flag, inst

def box_merge(bbox, bbox1):
	"""merge bbox1 into bbox to form a bigger one."""
	bbox.left = bbox.left if bbox.left < bbox1.left else bbox1.left
	bbox.bottom = bbox.bottom if bbox.bottom < bbox1.bottom else bbox1.bottom
	bbox.right = bbox1.right if bbox.right < bbox1.right else bbox.right
	bbox.top = bbox1.top if bbox.top < bbox1.top else bbox.top

def box_expand(boxSeed, eleList, rtree):
	"""expand the seed box until it stabliziles."""

	while (True):
		#obtain boxes intersecting with the four edges of the seed(overlaping and touching)
		boxEdge = list(rtree.intersection((boxSeed.left, boxSeed.top, boxSeed.right, boxSeed.top)))
		boxEdge.extend( list(rtree.intersection((boxSeed.left, boxSeed.bottom, boxSeed.right, boxSeed.bottom)) ))
		boxEdge.extend( list(rtree.intersection((boxSeed.left, boxSeed.bottom, boxSeed.left, boxSeed.top)) ))
		boxEdge.extend( list(rtree.intersection((boxSeed.right, boxSeed.bottom, boxSeed.right, boxSeed.top)) ))
		boxEdge = list(set(boxEdge))

		#remove inside boxes
		edgeCopy = boxEdge.copy()
		for boxIndex in edgeCopy:
			box = eleList[boxIndex].bbox
			if box.inside(boxSeed):
				boxEdge.remove(boxIndex)

		if boxEdge:
			for boxIndex in boxEdge:
				box = eleList[boxIndex].bbox
				box1 = boxSeed + box
				box_merge(boxSeed, box)
		else:
			instList = list( rtree.intersection(box_tuple(boxSeed)) )
			return boxSeed, instList         #new stable instance bounding box and corresponding element index

def box_tuple(bbox):
	"""return a tuple."""
	return (bbox.left, bbox.bottom, bbox.right, bbox.top)

def indexes_to_string(idxList, instList):
		"""A helper function that converts element instance list to 5-tuple like string."""

		instString = list()
		for index in idxList:
			inst = instList[index]
			centerx = (inst.bbox.left + inst.bbox.right)/2
			centery = (inst.bbox.bottom + inst.bbox.top)/2
			instString.append((centerx, centery, inst.pid, inst.tid, inst.symmetryType))
		return instString

def tid_update(oldTid, oid, symmetryType):
	"""function to update TID after specific OID operation,like,
	   oid = R90 which means to rotate 90degree counterclockwise """

	if oid == O1:
		return oldTid
	else:
		oldOid = tidToOid[symmetryType].get(oldTid)
		if oldOid.value % 2 == 0:
			newOid0 = oldOid.value - oid.value + 1
		else:
			newOid0 = oldOid.value + oid.value - 1
		if newOid0 > 8:
			newOid = OID(newOid0 - 8)
		elif newOid0 < 1:
			newOid = OID(newOid0 + 8)
		else:
			newOid = OID(newOid0)
		return oidToTid[symmetryType].get(newOid)

def resort(point_list, type):
	"""cluster: Resort the new born point list with oid in descending order
	   polygon: To find the most lowerleft point and set it as oringe to resort the point list"""

	point_list.insert(0, (0, 0))
	length = len(point_list)
	if type == 'polygon':
		lableMin = 0
		for i in range(length):
			if point_list[i] < point_list[lableMin] :
				lableMin = i
			else:
				lableMin = lableMin
		point_list_1 = list()
		for i in range(length):
			point_list_1.append( point_list[(i+lableMin)%length] )

		for i in range(length-1):
			point_list[i] = (point_list_1[i+1][0]-point_list_1[0][0], point_list_1[i+1][1]-point_list_1[0][1])
	elif type == 'cluster':
		point_list.sort()
		for i in range(1, length):
			point_list[i] = (point_list[i][0]-point_list[0][0], point_list[i][1]-point_list[0][1])
	point_list.pop()

def code_transform_basic(code, oid, type):
	"""function to tansform point string(code) with specific operation,oid."""

	newCode = list()
	if oid == O1:
		return code
	elif oid == O2:           #R0M (-x,y)
		for i in range(len(code)):
			newCode.append( (- code[i][0], code[i][1] ) )
		newCode.reverse()
		resort(newCode, type)
		return newCode
	elif oid == O3:           #R90 (-y,x)
		for i in range(len(code)):
			newCode.append( (- code[i][1], code[i][0] ) )
		resort(newCode, type)
		return newCode
	elif oid == O4:           #R90M (y,x)
		for i in range(len(code)):
			newCode.append( ( code[i][1], code[i][0] ) )
		newCode.reverse()
		resort(newCode, type)
		return newCode
	elif oid == O5:           #R180 (-x,-y)
		for i in range(len(code)):
			newCode.append( (- code[i][0], - code[i][1] ) )
		resort(newCode, type)
		return newCode
	elif oid == O6:           #R180M (x,-y)
		for i in range(len(code)):
			newCode.append( ( code[i][0], - code[i][1] ) )
		newCode.reverse()
		resort(newCode, type)
		return newCode
	elif oid == O7:           #R270 (y,-x)
		for i in range(len(code)):
			newCode.append( ( code[i][1], - code[i][0] ) )
		resort(newCode, type)
		return newCode
	elif oid == O8:           #R270M (-y,-x)
		for i in range(len(code)):
			newCode.append( (- code[i][1], - code[i][0] ) )
		newCode.reverse()
		resort(newCode, type)
		return newCode

def code_transform(code, oid):
	newCode = list()
	if oid == O1:
		return code
	elif oid == O2:           #R0M (-x,y)
		for i in range(len(code)):
			newCode.append(  (- code[i][0], code[i][1], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )                  #update coordinate
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O3:           #R90 (-y,x)
		for i in range(len(code)):
			newCode.append( (- code[i][1], code[i][0], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O4:           #R90M (y,x)
		for i in range(len(code)):
			newCode.append( (code[i][1], code[i][0], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4] )  )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O5:           #R180 (-x,-y)
		for i in range(len(code)):
			newCode.append( (- code[i][0], - code[i][1], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O6:           #R180M (x,-y)
		for i in range(len(code)):
			newCode.append( ( code[i][0], - code[i][1], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O7:           #R270 (y,-x)
		for i in range(len(code)):
			newCode.append( ( code[i][1], - code[i][0], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode
	elif oid == O8:           #R270M (-y,-x)
		for i in range(len(code)):
			newCode.append( (- code[i][1], - code[i][0], code[i][2], tid_update(code[i][3], oid, code[i][4]), code[i][4]) )
		newCode.sort(key = lambda x: (x[0], x[1], x[2], x[3].value, x[4]))
		return newCode


#*********visualization***************
def shapes_save(shapes, layout, cell, layerIndex):
	"""Insert boxes in the layout for further check or visisualization.
	@param layerIndex: tuple(layer number, datatype number)
	"""

	layerInfo = layout.layer(layerIndex[0], layerIndex[1])
	for shape in shapes:
		cell.shapes(layerInfo).insert(shape)

def pattern_tree_plot(topPattern):

	raise NotImplementedError
