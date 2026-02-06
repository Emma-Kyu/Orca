from dataclasses import dataclass, field

@dataclass
class Hyperparameters:
	temperature: float = 0.8
	min_p: float = 0.1
	top_k: int = 40
	presence_penalty: float = 0.0
	repetition_penalty: float = 1.0
	repeat_last_n: int = 64

	# XTC
	xtc_threshold: float = 0.1
	xtc_probability: float = 0.0

	# DRY sampling
	dry_multiplier: float = 0.0
	dry_base: float = 1.75
	dry_allowed_length: int = 2
	dry_penalty_last_n: int = -1
	dry_sequence_breakers: list[str] = field(
		default_factory=lambda: ['\n', ':', '"', '*']
	)

	# Misc
	n_predict: int = 512
	logit_bias: list = field(default_factory=list)
	samplers: list[str] = field(
		default_factory=lambda: [
			"dry", "top_k", "typ_p", "top_p",
			"min_p", "xtc", "temperature"
		]
	)

	# Legacy fallback
	seed: int = -1

	@classmethod
	def from_dict(cls, params: dict):
		return cls(**params)

	def to_payload(self, messages: list[dict]) -> dict:
		return {
			"messages": messages,

			"temperature": self.temperature,

			"xtc_threshold": self.xtc_threshold,
			"xtc_probability": self.xtc_probability,

			"min_p": self.min_p,
			"top_k": self.top_k,

			"presence_penalty": self.presence_penalty,
			"repeat_penalty": self.repetition_penalty,
			"repeat_last_n": self.repeat_last_n,

			"id_slot": 0,
			"cache_prompt": True,
			"stream": True,
			"n_predict": self.n_predict,
			"seed": self.seed,
			"logit_bias": self.logit_bias,
			"samplers": self.samplers,

			# DRY specific
			"dry_multiplier": self.dry_multiplier,
			"dry_base": self.dry_base,
			"dry_allowed_length": self.dry_allowed_length,
			"dry_penalty_last_n": self.dry_penalty_last_n,
			"dry_sequence_breakers": self.dry_sequence_breakers,
		}