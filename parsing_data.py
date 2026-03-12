from __future__ import annotations
from dataclasses import dataclass, field
from math import isnan
from typing import Optional

@dataclass(frozen=True)
# frozen=True ensures immutability, meaning once a class is created in an instance of it, its values cannot be changed
# Basically a constant definition but for a class
class Interval:
	'''
	Class that represents [min value, max value]
	'''
	min_value: float # attribute of class Interval
	max_value: float

	@classmethod # Invokes the naming convention of cls for Class
	def nan(cls) -> "Interval":
		return cls(float("nan"), float("nan"))
	
	@classmethod
	def from_val_pm_unc(cls, value: float, uncertainty: float) -> "Interval":
		return cls(value - uncertainty, value + uncertainty)
	
	def is_nan(self):
		'''
		Returns True if both the minimum and maximum values of the interval are NaN
		'''
		return isnan(self.min_value) and isnan(self.max_value)
	
	def format(self, decimals: int = 4) -> str:
		'''
		Returns the interval as a string [min, max]. If both min and max values are NaN, returns [NaN, NaN]
		'''
		if self.is_nan():
			return "[NaN, NaN]"
		return f"[{self.min_value:.{decimals}f}, {self.max_value:.{decimals}f}]"

@dataclass(frozen=True)
class FlavorAssignment:
	'''
	Heavy flavor assignement to the f, g and/or h flavors of a baryon
	'''
	f: Optional[str] = None
	g: Optional[str] = None
	h: Optional[str] = None

	def code(self) -> Optional[str]:
		'''
		Builds the heavy flavors for the given f, g and/or h
		E.g: f = "s" -> "s"
		E.g: f = "s", g = "c" -> "sc"
		'''
		parts = [x for x in (self.f, self.g, self.h) if x is not None]
		return "".join(parts) if parts else None

	def is_light_only(self) -> bool:
		return self.code() is None

	def mapping(self) -> dict[str, str]:
		result = {}
		if self.f is not None:
			result["f"] = self.f
		if self.g is not None:
			result["g"] = self.g
		if self.h is not None:
			result["h"] = self.h
		return result

	def substitute_symbols(self, text: str) -> str:
		'''
		Useful for doing stuff like this:
		SC(nf) becomes SC(ns) when f = s
		AV(fg) becomes AV(sc) when f = s, g = c
		'''
		result = text
		for symbol, flavor in self.mapping().items():
			result = result.replace(symbol, flavor)
		return result

@dataclass(frozen=True)
class ChannelKey:
	'''
	Builds the complete baryon channel: heavy flavor assignement, J value and parity value
	'''
	flavor_assignment: FlavorAssignment
	J: str
	parity: str

	def j_code(self) -> str:
		if self.J == "1/2":
			return "J12"
		if self.J == "3/2":
			return "J32"
		raise ValueError(f"Unsupported J value: {self.J}")

	def prefix(self) -> str:
		flavor_code = self.flavor_assignment.code()

		if flavor_code is None:
			return f"{self.j_code()}_{self.parity}_"
		return f"[{flavor_code}]_{self.j_code()}_{self.parity}_"

	def summary_channel_name(self) -> str:
		'''
		The prefix without the last _ is useful for reading information of one of the input data files
		'''
		return self.prefix().rstrip("_")
	
	def display_label(self) -> str:
		return f"J = {self.J}, Parity = {self.parity}"

@dataclass
class StateResult:
	state_label: str
	state_index: int
	calculated_mass: Interval = field(default_factory=Interval.nan)
	pdg_mass: str = "WIP"
	lattice_mass: str = "WIP"
	partial_waves: dict[str, Interval] = field(default_factory=dict)
	diquarks: dict[str, Interval] = field(default_factory=dict)

@dataclass
class ChannelResult:
    channel_key: ChannelKey
    states: dict[str, StateResult] = field(default_factory=dict)

    def add_state(self, state_result: StateResult) -> None:
        self.states[state_result.state_label] = state_result

    def get_state(self, state_label: str) -> StateResult:
        return self.states[state_label]

@dataclass
class BaryonResult:
    baryon_name: str
    channels: dict[ChannelKey, ChannelResult] = field(default_factory=dict)

    def add_channel(self, channel_result: ChannelResult) -> None:
        self.channels[channel_result.channel_key] = channel_result

    def get_channel(self, channel_key: ChannelKey) -> ChannelResult:
        return self.channels[channel_key]

@dataclass
class AllResults:
    baryons: dict[str, BaryonResult] = field(default_factory=dict)

    def add_baryon(self, baryon_result: BaryonResult) -> None:
        self.baryons[baryon_result.baryon_name] = baryon_result

    def get_baryon(self, baryon_name: str) -> BaryonResult:
        return self.baryons[baryon_name]

print(__file__)
