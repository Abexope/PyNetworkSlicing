"""
下行RAN模拟系统

"""

from random import randint, seed, choice, paretovariate, lognormvariate
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
			(log(self._x_max) - self._mu) / self._sigma
		)   # 实例化基于Scipy包的截断正态分布生成器
		return exp(tmp.rvs())   # 生成随机数，返回去对数化结果


class Generator:
	
	def __init__(self):
		self._type = self._choice()
	
	@staticmethod
	def _choice():
		return choice(("VoLTE", "Video", "URLLC"))
	
	def type(self):
		"""返回随机生成数据包类型"""
		return self._type
	
	def size(self):
		"""返回随机生成数据包大小"""
		if self.type() == "VoLTE":
			return 40       # Constant, 40 Byte
		if self.type() == "Video":
			random_generator = TruncatePareto(x_min=100, x_max=250, param=1.2)      # 截断Pareto分布
			return random_generator.generate()      # Byte
		if self.type() == "URLLC":
			random_generator = TruncateLogNorm(x_min=1e3, x_max=5e6, mu=2e6, sigma=0.722e6)     # 截断正太分布
			return random_generator.generate()      # Byte
	
	def rate(self):
		"""返回数据包速率大小"""
		if self.type() == "VoLTE":
			return 51       # 51 Kbps
		if self.type() == "Video":
			return 5e3      # 5 Mbps
		if self.type() == "URLLC":
			return 10e3     # 10 Mbps


class Package:
	"""数据包接口"""
	
	def __init__(self, time, generator=Generator()):            # generator：数据包属性生成器，后续改成默认传参
		self._time = time                           # 数据包发送时间，slot数
		self._type = generator.type()               # 服务类型
		self._size = generator.size()               # 数据包大小
		self._rate = generator.rate()               # 数据包速率
	
	def interval(self):
		"""返回数据包发送用时"""
		return ceil(self._size / self._rate) // 0.5    # 返回的是slot数
	
	def size(self):
		"""返回数据包大小"""
		return self._size
	
	def rate(self):
		"""返回数据包速率"""
		return self._rate
	
	def service(self):
		"""返回数据包类型"""
		return self._type


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


class Packing(Event):
	"""数据包生成事件"""
	
	def __init__(self, packing_time, custom):
		super(Packing, self).__init__(packing_time, custom)
		custom.add_event(self)
	
	def run(self):
		time, custom = self.time(), self.custom()
		print(time, "generate package")
		package = Package(time)
		Packing(time + randint(0, 160), custom)     # 引发下一个数据包生成事件
		if custom.has_queued_package():     # 如果有数据包在等待队列中
			custom.enqueue(package)         # 加入等待队列
			return
		status = custom.find_channel(package.service())
		if status is not None:           # 如果信道可占用则执行数据包发送事件
			print(time, "send package in Packing")      # 数据并未送入等待队列直接发送
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
		print(time, "sending accomplished")
		custom.free_channel(self.package.service)
		custom.count_package_1()                            # 数据包计数
		custom.total_time_acc(time - self.package.time)
		if custom.has_queued_package():                     # 如果有数据包在Custom的等待队列中
			package = custom.next_package()                 # 队头数据包出队列
			custom.find_channel(package.service)            # 当前数据包发送后，更新信道占用状态channel_status
			print(time, "send package in Sending")       # 数据从等待队列中提取后发送
			custom.wait_time_acc(time - package.time)
			Sending(time + package.send_interval(), package, custom)


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
		self.wait_line = Queue()
		self.total_wait_time = 0
		self.total_used_time = 0
		self.package_num = 0
		self.channel_status = {"VoLTE": True}       # True：可用 False：被占用
		
	def wait_time_acc(self, n):
		self.total_wait_time += n
		
	def total_time_acc(self, n):
		self.total_used_time += n
		
	def count_package_1(self):
		self.package_num += 1
		
	def has_queued_package(self):
		return not self.wait_line.is_empty()
	
	def find_channel(self, service: str) -> bool or None:     # 占用信道
		"""
		
		:param service: 服务类型 VoLTE Video URLLC
		:return:
		"""
		if self.channel_status[service]:
			self.channel_status[service] = not self.channel_status[service]
			return service
		
	def free_channel(self, service) -> None:     # 释放信道
		"""
		
		:param service: 服务类型 VoLTE Video URLLC
		:return:
		"""
		if not self.channel_status[service]:
			self.channel_status[service] = not self.channel_status[service]
		else:
			raise ValueError("Clear gate error")
	
	def add_event(self, event):
		self.simulator.add_event(event)
		
	def current_time(self):
		return self.simulator.current_time()
	
	def enqueue(self, package):
		self.wait_line.enqueue(package)
		
	def next_package(self):
		return self.wait_line.dequeue()
	
	def simulate(self):
		Packing(packing_time=0, custom=self)
		self.simulator.run()
		

if __name__ == '__main__':
	cus = Custom(DURATION)
	cus.simulate()
	print(
		"总用时", cus.total_used_time, '\n',
		"总候时", cus.total_wait_time, '\n',
		"总包数", cus.package_num, '\n',
		"数据包对列剩余", len(cus.wait_line), '\n',
		"帧利用率", cus.total_wait_time / cus.duration
	)
	
	pass
