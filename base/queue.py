"""对列数据结构"""


class PriorQueue:
	"""优先队列"""
	
	def __init__(self):
		self._elements = list()  # 基于线性表实现
		self._length = 0
	
	def __len__(self):
		return self._length
	
	def __str__(self):
		return "[" + " -> ".join([str(item) for item in self._elements]) + "]"
	
	def is_empty(self):
		return not self._elements
	
	def enqueue(self, e):
		"""加入队列"""
		i = len(self._elements) - 1
		while i >= 0:
			if self._elements[i] <= e:
				i -= 1
			else:
				break
		self._elements.insert(i + 1, e)
		self._length += 1
	
	def peek(self):
		"""获取优先级最高的元素"""
		if self.is_empty():
			raise ValueError("Empty queue!")
		return self._elements[-1]
	
	def dequeue(self):
		"""出队列"""
		if self.is_empty():
			raise ValueError("Empty queue!")
		self._length -= 1
		return self._elements.pop()


class Queue:
	"""基本队列"""
	
	def __init__(self):
		self._elements = list()
		self._length = 0
	
	def __len__(self):
		return self._length
	
	def __str__(self):
		return "[" + " -> ".join([str(item) for item in self._elements[::-1]]) + "]"
	
	def is_empty(self):
		return not self._elements
	
	def enqueue(self, e):
		self._elements.append(e)
		self._length += 1
	
	def peek(self):
		if self.is_empty():
			raise ValueError("Empty queue!")
		return self._elements[0]
	
	def dequeue(self):
		if self.is_empty():
			raise ValueError("Empty queue!")
		self._length -= 1
		return self._elements.pop(0)
