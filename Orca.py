import yaml
import asyncio
import argparse

from dotenv import load_dotenv

class Orca:
	def __init__(self, config: dict):
		self.config = config

		# subprocesses
		self.llm = None

	async def run(self):
		pass

if __name__ == "__main__":
	# Get config data
	load_dotenv()
	parser = argparse.ArgumentParser()
	parser.add_argument("config", help="Path to YAML config")
	args = parser.parse_args()

	# Load config
	with open(args.config, "r") as file:
		config = yaml.safe_load(file.read())

	# Run app
	app = Orca(args.config)
	asyncio.run(app.run())