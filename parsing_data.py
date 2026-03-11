from __future__ import annotations
from dataclasses import dataclass
from math import isnan
from typing import Optional

@dataclass(frozen=True)
# frozen=True ensures immutability, meaning once a class is created in an instance of it, its values cannot be changed
# Basically a constant definition but for a class
class Interval:
	min_value: float # attribute of class Interval
	max_value: float

	@classmethod # Invokes the naming convention of cls for Class
	def interval_nan(cls) -> "Interval":
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
class FlavorAssignement:
	f: Optional[str] = None
	g: Optional[str] = None
	h: Optional[str] = None
