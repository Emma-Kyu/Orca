class BarrierTracker:
	def __init__(self):
		self.barriers: dict[str, set[str]] = {}
		self.function_to_barrier: dict[str, str] = {}

	def create_barrier(self, barrier_id: str, function_ids: set[str] | None = None):
		if not function_ids:
			return

		self.barriers[barrier_id] = set(function_ids)

		for fid in function_ids:
			self.function_to_barrier[fid] = barrier_id

	def resolve(self, function_id: str) -> str | None:
		bid = self.function_to_barrier.get(function_id)
		if not bid:
			return None

		remaining = self.barriers.get(bid)
		if not remaining:
			return None

		remaining.discard(function_id)
		self.function_to_barrier.pop(function_id, None)

		if not remaining:
			self.barriers.pop(bid, None)
			return bid

		return None

	def get_outstanding(self, barrier_id: str) -> set[str]:
		return self.barriers.get(barrier_id, set())

	def clear_barrier(self, barrier_id: str):
		fids = self.barriers.pop(barrier_id, set())

		for fid in fids:
			self.function_to_barrier.pop(fid, None)