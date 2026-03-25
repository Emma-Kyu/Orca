import uuid

class Client:
	def __init__(self, socket, client_id, modalities):
		self.socket = socket;
		self.client_id = client_id
		self.modalities = modalities

class ClientManager:
	def __init__(self):
		self.clients: dict[str, Client] = {}

	def connect(self, client_details: dict, websocket=None) -> str:
		client_name = client_details["client"]
		client_id = f"cid-{uuid.uuid4().hex[:12]}"

		self.clients[client_name] = Client(websocket, client_id, client_details["modalities"])
		print(f"Client '{client_name}' connected with id {client_id} preferring {client_details["modalities"]}")
		return client_id

	def is_client_connected(self, name: str) -> bool:
		return name in self.clients

	def is_client_connected_by_id(self, client_id: str) -> bool:
		return any(client.client_id == client_id for client in self.clients.values())

	def disconnect(self, name: str):
		removed = self.clients.pop(name, None)
		if removed:
			print(f"Client '{name}' disconnected")
		print(f"'{name}' is not a connected client")

	def disconnect_socket(self, websocket) -> str | None:
		target_name = None
		for name, client in list(self.clients.items()):
			if client.socket == websocket:
				target_name = name
				break

		if target_name:
			self.clients.pop(target_name, None)
			print(f"Client '{target_name}' disconnected")
			return target_name
		return None

	def get_socket(self, name: str):
		client = self.client_sockets.get(name, None)
		return client.socket if client else None

	def get_sockets(self) -> list:
		return [client.socket for client in self.clients.values() if client.socket is not None]

	def get_clients(self) -> list[str]:
		return list(self.clients.keys())

	def get_client_name_from_id(self, client_id: str) -> str | None:
		for name, client in self.clients.items():
			if client.client_id == client_id:
				return name
		return None

	def get_client_modalities(self) -> dict[str, list]:
		modalities_map = {}

		for client in self.clients.values():
			for modality in client.modalities:
				if modality not in modalities_map:
					modalities_map[modality] = []
				if client.socket:
					modalities_map[modality].append(client.socket)

		return modalities_map
