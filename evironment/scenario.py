"""
下行RAN模拟系统

"""

from abc import ABCMeta, abstractmethod
from random import randint, paretovariate, seed, choice
from math import ceil, exp, log
from scipy.stats import truncnorm

from base.queue import Queue, PriorQueue

# 全局变量
DURATION = 2000     # 一帧1000毫秒，2000个slot，每个slot0.5毫秒
# seed(0)


class TruncatePareto:
	"""截断Pareto分布"""
	
	def __init__(self, x_min, x_max, param):
		self._x_min = x_min
		self._x_max = x_max
		self._param = param     # Pareto分布形状参数
	
	def generate(self):
		return min(self._x_min + paretovariate(self._param), self._x_max)
	
	
class TruncateLogNorm:
	"""截断正态分布"""
	
	def __init__(self, x_min, x_max, mu, sigma):
		self._x_min = x_min     # 线性上限
		self._x_max = x_max     # 线性下限
		self._mu = mu
		self._sigma = sigma
	
	def generate(self):
		tmp = truncnorm(
			(log(self._x_min) - self._mu) / self._sigma,
			(log(self._x_max) - self._mu) / self._sigma,
			loc=self._mu, scale=self._sigma
		)   # 实例化基于Scipy包的截断正态分布生成器
		return exp(tmp.rvs())   # 生成随机数，返回去对数化结果


class Package(object, metaclass=ABCMeta):
	"""数据包接口"""
	
	@abstractmethod
	def __init__(self, time):  # generator：数据包属性生成器，后续改成默认传参
		self._time = time  # 数据包发送时间，slot数
	
	@abstractmethod
	def size(self):
		"""返回数据包大小"""
		pass
	
	@abstractmethod
	def rate(self):
		"""返回数据包速率"""
		pass
	
	@abstractmethod
	def inter_arrival(self):
		"""返回下一数据包需求发生的时间间隔"""
		pass
	
	@abstractmethod
	def service(self):
		"""返回数据包类型"""
		pass
	
	def time(self):
		"""返回数据包需求生成时间"""
		return self._time
	
	def interval(self):
		"""返回数据包发送用时"""
		return ceil(self.size() / self.rate()) // 0.5  # 返回的是slot数


class VoLTEPackage(Package):
	"""VoLTE服务数据包"""
	
	def __init__(self, time):
		super(VoLTEPackage, self).__init__(time)
		self._type = "VoLTE"
		self._size = 40     # Byte
	
	def size(self): return self._size
	
	def rate(self): return 51  # Kbps
	
	def inter_arrival(self):
		pass
	
	def service(self): return self._type


class VideoPackage(Package):
	"""Video服务数据包"""
	
	def __init__(self, time):
		super(VideoPackage, self).__init__(time)
		self._type = "Video"
		self._rate = 5e3  # 5 Mbps
	
	def size(self):
		random_generator = TruncatePareto(x_min=100, x_max=250, param=1.2)  # 截断Pareto分布
		return random_generator.generate()  # Byte
	
	def rate(self): return self._rate
	
	def inter_arrival(self):
		pass
	
	def service(self): return self._type


class URLLCPackage(Package):
	"""URLLC服务数据包"""
	
	def __init__(self, time):
		super(URLLCPackage, self).__init__(time)
		self._type = "URLLC"
		self._rate = 10e3  # 10 Mbps
	
	def size(self):
		random_generator = TruncateLogNorm(x_min=1e6, x_max=5e6, mu=2e6, sigma=0.722e6)  # 截断正太分布
		return random_generator.generate()  # Byte
	
	def rate(self): return self._rate
	
	def inter_arrival(self):
		pass
	
	def service(self): return self._type


class Generator:
	
	@classmethod
	def generator(cls, time: int, service_type: str) -> Package:
		if service_type == "VoLTE":
			return VoLTEPackage(time)
		elif service_type == "Video":
			return VideoPackage(time)
		elif service_type == "URLLC":
			return URLLCPackage(time)
		else:
			raise ValueError("Illegal value of service type.")


class Event:
	"""事件接口"""
	
	def __init__(self, event_time, custom):
		self._event_time = event_time
		self._custom = custom
	
	def __lt__(self, other_event):
		return self._event_time < other_event.time()
	
	def __le__(self, other_event):
		return self._event_time < other_event.time()
	
	def custom(self):
		"""返回宿主系统"""
		return self._custom
	
	def time(self):
		return self._event_time
	
	def run(self):
		"""事件具体流程定义"""
		pass


class VoLTEPacking(Event):
	"""VoLTE数据包生成事件"""
	
	def __init__(self, packing_time, custom):
		super(VoLTEPacking, self).__init__(packing_time, custom)
		self._service_type = "VoLTE"
		custom.add_event(self)
	
	def run(self):
		time, custom = self.time(), self.custom()
		print(time, "generate {} package in VoLTEPacking".format(self._service_type))
		package = Generator.generator(time, self._service_type)     # 生成当前事件的数据包
		VoLTEPacking(time + randint(0, 160), custom)                # 实例化引发下一个同种数据包生成事件对象，直接进入custom的事件队列
		if custom.has_queued_package(self._service_type):
			custom.enqueue(package)
			return
		# status = custom.find_channel(package.service())
		status = custom.find_channel()
		if status is not None:
			print(time, "send VoLTE package in VoLTEPacking [{} Byte]".format(package.size()))
			Sending(time + package.interval(), package, custom)
		else:
			custom.enqueue(package)
			
			
class VideoPacking(Event):
	"""Video数据包生成事件"""
	
	def __init__(self, packing_time, custom):
		super(VideoPacking, self).__init__(packing_time, custom)
		self._service_type = "Video"
		custom.add_event(self)
	
	def run(self):
		time, custom = self.time(), self.custom()
		print(time, "generate {} package in VoLTEPacking".format(self._service_type))
		package = Generator.generator(time, self._service_type)  # 生成当前事件的数据包
		VideoPacking(time + randint(0, 160), custom)  # 实例化引发下一个同种数据包生成事件对象，直接进入custom的事件队列
		if custom.has_queued_package(self._service_type):
			custom.enqueue(package)
			return
		# status = custom.find_channel(package.service())
		status = custom.find_channel()
		if status is not None:
			print(time, "send Video package in VoLTEPacking [{:.2f} Byte]".format(package.size()))
			Sending(time + package.interval(), package, custom)
		else:
			custom.enqueue(package)


class URLLCPacking(Event):
	"""URLLC数据包生成事件"""
	
	def __init__(self, packing_time, custom):
		super(URLLCPacking, self).__init__(packing_time, custom)
		self._service_type = "URLLC"
		custom.add_event(self)
	
	def run(self):
		time, custom = self.time(), self.custom()
		print(time, "generate {} package in VoLTEPacking".format(self._service_type))
		package = Generator.generator(time, self._service_type)  # 生成当前事件的数据包
		URLLCPacking(time + randint(0, 160), custom)  # 实例化引发下一个同种数据包生成事件对象，直接进入custom的事件队列
		if custom.has_queued_package(self._service_type):
			custom.enqueue(package)
			return
		# status = custom.find_channel(package.service())
		status = custom.find_channel()
		if status is not None:
			print(time, "send URLLC package in VoLTEPacking [{:.2f} Byte]".format(package.size()))
			Sending(time + package.interval(), package, custom)
		else:
			custom.enqueue(package)


class Sending(Event):
	"""数据包发送事件"""
	
	def __init__(self, send_time, package, custom):
		super(Sending, self).__init__(send_time, custom)
		self.package = package
		custom.add_event(self)
	
	def run(self):
		time, custom = self.time(), self.custom()
		print(time, "{} sending accomplished".format(self.package.service()))
		# custom.free_channel(self.package.service())
		custom.free_channel()
		custom.count_package_1()                            # 数据包计数
		custom.total_time_acc(time - self.package.time())
		if custom.has_queued_package(self.package.service()):                     # 如果有数据包在Custom的等待队列中
			package = custom.next_package(self.package.service())                 # 队头数据包出队列
			# custom.find_channel(package.service())            # 当前数据包发送后，更新信道占用状态channel_status
			custom.find_channel()
			print(time, "send {} package in Sending [{:.2f} Byte]".format(package.service(), package.size()))       # 数据从等待队列中提取后发送
			custom.wait_time_acc(time - package.time())
			Sending(time + package.interval(), package, custom)


class Simulator:
	"""通用事件模拟系统"""
	
	def __init__(self, duration):
		self._event_queue = PriorQueue()        # 事件优先队列
		self._time = 0                          # 系统时间(slot数)
		self._duration = duration               # 仿真持续时间(slot数)
	
	def run(self):
		while not self._event_queue.is_empty():
			event = self._event_queue.dequeue()
			self._time = event.time()           # 获取当前时间
			if self._time > self._duration:     # 模拟结束条件判定
				break
			event.run()     # 执行事件
	
	def add_event(self, event):
		self._event_queue.enqueue(event)
		
	def current_time(self):
		"""获取系统时间(slot序号)"""
		return self._time


class Custom:
	"""下行RAN场景模拟系统"""
	
	def __init__(self, duration):
		self.duration = duration
		self.simulator = Simulator(self.duration)
		self.wait_line = {"VoLTE": Queue(), "Video": Queue(), "URLLC": Queue()}   # 不同事件采用独立队列
		self.total_wait_time = 0
		self.total_used_time = 0
		self.package_num = 0
		# self.channel_status = {"VoLTE": True, "Video": True, "URLLC": True}       # True：可用 False：被占用
		self.channel_status = True
		
	def wait_time_acc(self, n):
		self.total_wait_time += n
		
	def total_time_acc(self, n):
		self.total_used_time += n
		
	def count_package_1(self):
		self.package_num += 1
		
	def has_queued_package(self, service_type):
		return not self.wait_line[service_type].is_empty()
	
	# def find_channel(self, service: str) -> bool or None:     # 占用信道
	# 	"""
	# 	True -> False
	# 	:param service: 服务类型 VoLTE Video URLLC
	# 	:return:
	# 	"""
	# 	if self.channel_status[service]:
	# 		self.channel_status[service] = not self.channel_status[service]
	# 		return service
	
	def find_channel(self) -> bool or None:     # 占用信道
		"""
		True -> False
		:param service: 服务类型 VoLTE Video URLLC
		:return:
		"""
		if self.channel_status:
			self.channel_status = not self.channel_status
			return self.channel_status
		
	# def free_channel(self, service) -> None:     # 释放信道
	# 	"""
	# 	False -> True
	# 	:param service: 服务类型 VoLTE Video URLLC
	# 	:return:
	# 	"""
	# 	if not self.channel_status[service]:
	# 		self.channel_status[service] = not self.channel_status[service]
	# 	else:
	# 		raise ValueError("Clear {} gate error".format(service))
	
	def free_channel(self) -> None:     # 释放信道
		"""
		False -> True
		:param service: 服务类型 VoLTE Video URLLC
		:return:
		"""
		if not self.channel_status:
			self.channel_status = not self.channel_status
		else:
			raise ValueError("Clear gate error")
	
	def add_event(self, event):
		self.simulator.add_event(event)
		
	def current_time(self):
		return self.simulator.current_time()
	
	def enqueue(self, package):
		self.wait_line[package.service()].enqueue(package)
		
	def next_package(self, service_type):
		return self.wait_line[service_type].dequeue()
	
	def simulate(self):
		# 不同事件、不同用户生成的入口，通过直接实例化对象的方式将自身传入到custom中
		VoLTEPacking(packing_time=0, custom=self)
		VideoPacking(packing_time=0, custom=self)
		URLLCPacking(packing_time=0, custom=self)
		self.simulator.run()
		

if __name__ == '__main__':
	cus = Custom(DURATION)
	cus.simulate()
	print(
		"总用时", cus.total_used_time, '\n',
		"总候时", cus.total_wait_time, '\n',
		"总包数", cus.package_num, '\n',
		"数据包队列剩余", [len(value) for value in cus.wait_line.values()], '\n',
		"帧利用率", cus.total_wait_time / cus.duration
	)
	pass
