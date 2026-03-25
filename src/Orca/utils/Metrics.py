import time
from enum import Enum
from contextlib import contextmanager

class Unit(Enum):
	SECONDS = 0
	MILLISECONDS = 1
	PER_SECOND = 2

class Metrics:
	def __init__(self):
		self._created = time.time()
		self.metrics = {}
		self.counts = {}
		self.start_times = {}

	def add_metrics(self, name, value, unit: Unit):
		self.metrics[name] = (value, unit)

	def set_count(self, name, count):
		self.counts[name] = count

	def add_count(self, name, count):
		if name in self.metrics:
			self.counts[name] += count
		else:
			self.set_count(name, count)

	def add_to_metric(self, name, delta, unit: Unit):
		if name in self.metrics:
			existing_value, existing_unit = self.metrics[name]
			if existing_unit != unit:
				raise ValueError(f"Unit mismatch for metric '{name}': existing {existing_unit}, new {unit}")
			self.metrics[name] = (existing_value + delta, unit)
		else:
			self.add_metrics(name, delta, unit)

	def finalize_rate(self, metric_name, count_name, time_name):
		if count_name in self.counts and time_name in self.metrics:
			count = self.counts[count_name]
			time_val, time_unit = self.metrics[time_name]
			seconds = time_val if time_unit == Unit.SECONDS else time_val / 1000
			if seconds > 0:
				self.add_metrics(metric_name, count / seconds, Unit.PER_SECOND)

	def start_timer(self, name):
		self.start_times[name] = time.time()

	def stop_timer(self, name, unit=Unit.MILLISECONDS):
		if name not in self.start_times:
			return
		duration = time.time() - self.start_times[name]
		if unit == Unit.MILLISECONDS:
			duration *= 1000

		self.add_to_metric(name, duration, unit)
		del self.start_times[name]

	@contextmanager
	def time(self, name, unit=Unit.MILLISECONDS):
		start = time.time()
		yield
		end = time.time()
		duration = end - start
		if unit == Unit.MILLISECONDS:
			duration *= 1000
		self.add_metrics(name, duration, unit)

	def print(self, include_total=False, total_unit=Unit.MILLISECONDS):
		parts = []
		total_seconds = 0.0

		for name, (value, unit) in self.metrics.items():
			if unit == Unit.MILLISECONDS:
				total_seconds += value / 1000
				parts.append(f"{name} = {value:.1f}ms")
			elif unit == Unit.SECONDS:
				total_seconds += value
				parts.append(f"{name} = {value:.2f}s")
			elif unit == Unit.PER_SECOND:
				parts.append(f"{name} = {value:.0f}/s")
			else:
				parts.append(f"{name} = {value}")
			
		print("[metrics]", " | ".join(parts))

	def __enter__(self):
		self._start = time.time()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self._end = time.time()
		self.add_metrics("total", (self._end - self._start) * 1000.0, Unit.MILLISECONDS)
		self.print()

	def now(self) -> float:
		return time.time() - self._created