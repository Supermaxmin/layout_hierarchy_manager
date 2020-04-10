"""
@author: 	Meenchow Yin
@date: 		2019.12.17
@version: 	0.1
@brief:     Define some basice data structures.
"""

from enum import Enum

# definition of oid/tid
# Enumeration of OID and TID
class TID(Enum):
	T1 = 1; T2 = 2; T3 = 3; T4 = 4
	T5 = 5; T6 = 6; T7 = 7; T8 = 8

class OID(Enum):
	O1 = 1; O2 = 2; O3 = 3; O4 = 4
	O5 = 5; O6 = 6; O7 = 7; O8 = 8

T1 = TID.T1; T2 = TID.T2; T3 = TID.T3; T4 = TID.T4
T5 = TID.T5; T6 = TID.T6; T7 = TID.T7; T8 = TID.T8

O1 = OID.O1; O2 = OID.O2; O3 = OID.O3; O4 = OID.O4
O5 = OID.O5; O6 = OID.O6; O7 = OID.O7; O8 = OID.O8

# OID to TID dictionary list for distinct polygon symmetry type
oidToTid = list()
oidToTid.append({O1:T1, O2:T2, O3:T3, O4:T4, O5:T5, O6:T6, O7:T7, O8:T8})  #No symmetry
oidToTid.append({O1:T1, O2:T2, O3:T3, O4:T4, O5:T1, O6:T2, O7:T3, O8:T8})  #2-fold central
oidToTid.append({O1:T1, O2:T2, O3:T1, O4:T2, O5:T1, O6:T2, O7:T1, O8:T2})  #4-fold central
oidToTid.append({O1:T1, O2:T1, O3:T2, O4:T3, O5:T4, O6:T4, O7:T3, O8:T2})  #Vertical axis
oidToTid.append({O1:T1, O2:T2, O3:T3, O4:T3, O5:T2, O6:T1, O7:T4, O8:T4})  #Horizontal axis
oidToTid.append({O1:T1, O2:T2, O3:T2, O4:T1, O5:T3, O6:T4, O7:T4, O8:T3})  #+pi/4 axis
oidToTid.append({O1:T1, O2:T2, O3:T3, O4:T4, O5:T4, O6:T3, O7:T2, O8:T1})  #-pi/4 axis
oidToTid.append({O1:T1, O2:T1, O3:T2, O4:T2, O5:T1, O6:T1, O7:T2, O8:T2})  #2-fold central and axial
oidToTid.append({O1:T1, O2:T1, O3:T1, O4:T1, O5:T1, O6:T1, O7:T1, O8:T1})  #4-fold central and axial

# TID to OID dictionary list for distinct polygon symmetry type
tidToOid = list()
tidToOid.append({T1:O1, T2:O2, T3:O3, T4:O4, T5:O5, T6:O6, T7:O7, T8:O8})  #No symmetry
tidToOid.append({T1:O1, T2:O2, T3:O3, T4:O4})                              #2-fold central
tidToOid.append({T1:O1, T2:O2})                                            #4-fold central
tidToOid.append({T1:O1, T2:O3, T3:O4, T4:O5})                              #Vertical axis
tidToOid.append({T1:O1, T2:O2, T3:O3, T4:O7})                              #Horizontal axis
tidToOid.append({T1:O1, T2:O2, T3:O5, T4:O6})                              #+pi/4 axis
tidToOid.append({T1:O1, T2:O2, T3:O3, T4:O4})                              #-pi/4 axis
tidToOid.append({T1:O1, T2:O3})                                            #2-fold central and axial
tidToOid.append({T1:O1})  												   #4-fold central and axial


# linked list
class Node(object):
	def __init__(self, value):
		self.value = value
		self.__next = None
		self.__prev = None

	@property
	def next(self):
		return self.__next

	@next.setter
	def next(self, n):
		self.__next = n

	@property
	def prev(self):
		return self.__prev

	@prev.setter
	def prev(self, n):
		self.__prev = n

	def to(self, dest):
		node = self
		while True:
			if node.value == dest:
				return node
			elif node.value > dest:
				return None
			node = node.__next
			if node is None:
				return None

	def __call__(self):
		return self.value

	def __str__(self):
		return "Node(%s)" % str(self.value)

	def __repr__(self):
		return "<Node(%s)>" % repr(self.value)

# doubly sorted linked list
class SortedLinkedList(object):
	__slots__ = ('__head', '__tail', '__size', )

	def __init__(self, iterable=None):
		self.__head = None
		self.__tail = None
		self.__size = 0
		if iterable:
			self.__extend(iterable)

	@property
	def head(self):
		return self.__head

	@head.setter
	def head(self, h):
		self.__head = h

	@property
	def tail(self):
		return self.__tail

	@tail.setter
	def tail(self, t):
		self.__tail = t

	@property
	def size(self):
		return self.__size

	@size.setter
	def size(self, s):
		self.__size = s

	def __extend(self, iterable):
		for value in iterable:
			self.append_value(value)

	def __len__(self):
		return self.__size

	def __repr__(self):
		if self.__head is not None:
			return "LinkedList([%s])" % ', '.join((repr(x) for x in self))
		else:
			return 'LinkedList()'

	def __iter__(self):
		current = self.__head
		while current is not None:
			yield current
			current = current.next

	def at(self, value):
		if self.__head is None:
			return None
		node = self.__head
		node1 = node.to(value)
		return node1

	def append(self, node):
		if self.__head is None:
			self.__head = node
			self.__tail = node
		else:
			tail = self.__tail
			tail.next = node
			node.prev = tail
			self.__tail = node
		self.__size += 1
		return node

	def append_value(self, value):
		node = Node(value)
		self.append(node)

	def join(self, dlList, mode='tail'):
		if mode == 'tail':
			self.__tail.next = dlList.head
			dlList.head.prev = self.__tail

			self.__tail = dlList.tail
			self.__size += dlList.size
			dlList.head, dlList.tail = None, None
			dlList.size = 0
		elif mode == 'head':
			self.__head.prev = dlList.tail
			dlList.tail.next = self.__head

			self.__head = dlList.head
			self.__size += dlList.size
			dlList.head, dlList.tail = None, None
			dlList.size = 0
		else:
			raise ValueError("Param mode should be 'head' or 'tail', not %s." %mode)

	def pop(self, node=None):
		if node is None:
			node = self.__tail

		prev, next = node.prev, node.next
		if prev is None:
			self.__head = next
		else:
			prev.next = next
			node.prev = None
		if next is None:
			self.__tail = prev
		else:
			next.prev = prev
			node.next = None
		self.__size -= 1

	def pop_values(self, list):
		node = self.__head
		for val in list:
			while True:
				next = node.next
				if node.value == val:
					self.pop(node)
					node = next
					break
				else:
					node = next

	def pop_segment(self, start, end):
		"""Pop the segment specified by @param start and @param end."""
		node = self.__head
		nodeStart = node.to(start)
		if nodeStart is None:
			return

		sizePop = 1
		node = nodeStart
		while True:
			if node.value == end:
				nodeEnd = node
				break
			sizePop += 1
			node = node.next
			if node is None:
				return

		if nodeStart == self.__head:
			if nodeEnd == self.__tail:
				self.__head = None
				self.__tail = None
			else:
				self.__head = nodeEnd.next
				self.__head.prev = None
		else:
			if nodeEnd == self.__tail:
				self.__tail = nodeStart.prev
				self.__tail.next = None
			else:
				nodeEnd.next.prev = nodeStart.prev
				nodeStart.prev.next = nodeEnd.next
		self.__size -= sizePop

	def clear(self, rtree=None, size=None):
		if rtree is not None and size is not None:
			x , w, h = size
			for node in self:
				rtree.insert(1, (x, node.value, x+w, node.value+h))
		self.size = 0
		self.__head = None
		self.__tail = None

	def period_find(self, rtree, size, Threshold=15):
		"""@return: starting node and period"""
		x , w, h = size
		while self.__size > 2:
			nodeF = self.__head
			first = nodeF.value
			jumpFirst = nodeF.next.value - nodeF.value

			node = nodeF.next
			for i in range(Threshold):
				jump = node.next.value - node.value
				if jump == jumpFirst:
					leap = node.value - first
					node1 = node.next.to(node.value+leap)
					if node1:
						if self.__size == 3 or node1.to(node.value+2*leap):
							return nodeF, leap
				node = node.next
				if node.next is None:
					return None, None
			rtree.insert(1, (x, nodeF.value, x+w, nodeF.value+h))
			self.pop(nodeF)

		return None, None


# doubly linked list
class DLinkList(object):
	"""Doubly linked list class which operates at 'node level'.
	Node's prev/next point is maintained by user."""
	def __init__(self):
		self.__head = None
		self.__tail = None
		self.__count = 0

	def __str__(self):
		all = "The list includes "
		for val in self.range_values():
			all = all + str(val) + ', '
		return all + '.'
	@property
	def head(self):
		return self.__head

	@property
	def tail(self):
		return self.__tail

	@property
	def count(self):
		return self.__count

	def range_values(self):
		"""Traverse list at value level."""
		head = self.__head
		while head:
			yield head.value
			head = head.next

	def range_nodes(self):
		"""Traverse list at node level."""
		head = self.__head
		while head:
			yield head
			head = head.next

	def is_empty(self):
		return self.__head is None

	def length(self):
		return self.__count

	def append(self, node):
		"""Append node at the list tail."""
		node.next = None
		if self.is_empty():
			self.__head = node
			self.__tail = node
			node.prev = None
		else:
			tail = self.__tail
			tail.next = node
			node.prev = tail
			self.__tail = node
		self.__count += 1

	def delete(self, node):
		"""Delete the node specified."""
		if self.is_empty():
			return
		if self.__head == node:
			if self.__tail == node:
				self.__head, self.__tail = None, None
			else:
				self.__head = node.next
				node.next.prev = None
		else:
			if self.__tail == node:
				self.__tail = node.prev
				self.__tail.next = None
			else:
				node.prev.next = node.next
				node.next.prev = node.prev
		self.__count -= 1
