import re
import uuid

from .FunctionParser import FunctionParser

class FunctionRegistry:
	def __init__(self):
		self._func_parser = FunctionParser()
		self._registry: dict[str, dict] = {}
		self._docs_by_client: dict[str, list[str]] = {}
		self._handlers: dict[str, callable] = {}

	def register_client(self, client_name: str, func_docs: list[str]) -> None:
		# Drop any old entries for this client
		self.remove_client(client_name)

		if not func_docs:
			return

		namespaced_docs = self._namespace_functions(client_name, func_docs)
		self._docs_by_client[client_name] = namespaced_docs

		for doc in namespaced_docs:
			text = doc.strip()
			if not text:
				continue

			try:
				meta = self._func_parser.definition(text)
			except Exception:
				continue

			fname = meta.get("function")
			if not fname:
				continue

			ns = meta.get("client") or client_name
			meta["client"] = ns

			key = f"{ns}:{fname}"
			self._registry[key] = meta 

	def remove_client(self, client_name: str) -> None:
		self._docs_by_client.pop(client_name, None)

		to_del = [k for k, meta in self._registry.items() if meta.get("client") == client_name]
		for k in to_del:
			self._registry.pop(k, None)

	def get_all_functions(self) -> list[str]:
		out: list[str] = []
		for docs in self._docs_by_client.values():
			out.extend(docs)
		return out

	def parse_calls(self, raw_call: str) -> list[dict]:
		text = raw_call.strip()
		text = text.strip("`")

		try:
			calls = self._func_parser.call(text)
		except Exception:
			# print(f"[WARN] Could not parse: {text}")
			return []

		if not calls:
			# print(f"[WARN] No calls found")
			return []

		results: list[dict] = []

		for call in calls:
			ns = call.get("client")
			fname = call.get("function")
			if not ns or not fname:
				continue

			key = f"{ns}:{fname}"
			spec = self._registry.get(key)
			if not spec:
				# print(f"[WARN] Unknown function call: {key}")
				continue

			params = spec.get("params", [])
			values = call.get("args", [])

			if len(values) != len(params):
				# print(f"[WARN] No such overload exists: {len(values)} arguments but spec wants {len(params)} params")
				continue

			typed_args: dict[str, object] = {}
			for (arg_name, arg_type), val in zip(params, values):
				typed_args[arg_name] = self._coerce_value(val, arg_type)

			results.append({
				"client": spec["client"],
				"function_id": f"fid-{uuid.uuid4().hex[:12]}",
				"function": spec["function"],
				"args": typed_args,

				"return": spec["return"],
				"async": spec["async"]
			})

		return results

	def _namespace_functions(self, client_name: str, functions: list[str]) -> list[str]:
		# Functions are always namespaced to the client
		out: list[str] = []
		for func in functions:
			match = re.search(r'`([^`]+)`', func)
			if not match:
				out.append(func)
				continue

			sig = match.group(1).strip()

			# Already namespaced for this client
			if re.search(rf'^(async\s+)?{re.escape(client_name)}:', sig):
				ns_sig = sig
			else:
				if sig.startswith("async "):
					ns_sig = re.sub(r'^async\s+', f"async {client_name}:", sig, 1)
				else:
					ns_sig = f"{client_name}:{sig}"

			out.append(func.replace(match.group(0), f"`{ns_sig}`"))
		return out

	def _coerce_value(self, val, target_type: str):
		if target_type == "str":
			return val if isinstance(val, str) else str(val)
		if target_type == "int":
			return int(val)
		if target_type == "float":
			return float(val)
		if target_type == "bool":
			if isinstance(val, bool):
				return val
			if isinstance(val, str):
				l = val.strip().lower()
				if l in ("true", "1"):
					return True
				if l in ("false", "0"):
					return False
			return bool(val)
		return val

	def register_local_function(self, client: str, func_name: str, handler):
		key = f"{client}:{func_name}"
		self._handlers[key] = handler

	def get_handler(self, key: str):
		return self._handlers.get(key)