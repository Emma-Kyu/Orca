from dataclasses import dataclass

TEXT_STATE = "TEXT"

@dataclass
class DelimiterRule:
	name: str
	start: str
	end: str

class StreamingDelimiterParser:
	def __init__(self, rules):
		self.rules = rules
		self.state = TEXT_STATE
		self.active_rule = None
		self.pending = ""

	def feed(self, token):
		results = []

		self.pending += token

		while self.pending:
			if self.state == TEXT_STATE:

				match = self._find_earliest_start()

				if match is not None:
					rule, idx = match

					if idx > 0:
						results.append(("CHUNK", self.pending[:idx], TEXT_STATE))

					self.state = rule.name
					self.active_rule = rule

					results.append(("ENTER", rule.name, self.state))

					self.pending = self.pending[idx + len(rule.start):]
					continue

				safe, keep = self._split_safe_prefix(self._start_delimiters())

				if safe:
					results.append(("CHUNK", safe, TEXT_STATE))

				self.pending = keep
				break
			else:

				end = self.active_rule.end
				idx = self.pending.find(end)

				if idx != -1:

					if idx > 0:
						results.append(("CHUNK", self.pending[:idx], self.state))

					results.append(("EXIT", self.active_rule.name, TEXT_STATE))

					self.pending = self.pending[idx + len(end):]

					self.state = TEXT_STATE
					self.active_rule = None
					continue

				safe, keep = self._split_safe_prefix([end])

				if safe:
					results.append(("CHUNK", safe, self.state))

				self.pending = keep
				break

		return results

	def finalize(self):
		results = []

		if self.pending:
			results.append(("CHUNK", self.pending, self.state))
			self.pending = ""

		return results

	def _find_earliest_start(self):
		best = None

		for rule in self.rules:
			idx = self.pending.find(rule.start)

			if idx == -1:
				continue

			if best is None or idx < best[1]:
				best = (rule, idx)

		return best

	def _start_delimiters(self):
		return [rule.start for rule in self.rules]

	def _split_safe_prefix(self, delimiters):

		keep_len = self._suffix_prefix_overlap(self.pending, delimiters)

		if keep_len == 0:
			return self.pending, ""

		return self.pending[:-keep_len], self.pending[-keep_len:]

	def _suffix_prefix_overlap(self, text, delimiters):

		max_keep = 0

		for delim in delimiters:

			limit = min(len(text), len(delim) - 1)

			for k in range(1, limit + 1):

				if text.endswith(delim[:k]):
					if k > max_keep:
						max_keep = k

		return max_keep