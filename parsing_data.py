from __future__ import annotations
from dataclasses import dataclass, field
from math import isnan
from typing import Optional
from pathlib import Path
import re
import ast

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
	'''
	Results pertaining to a baryon state
	- Label of the state (Grd, 1st, 2nd, 3rd)
	- Index of the state (0, 1, 2, 3)
	- Calculated mass interval -> It's an Interval object
	- PDG mass -> For now just a WIP; will be changed later
	- LatticeQCD mass -> For now just a WIP; will be changed later
	- Partial waves -> A dictionary of Interval objects, one per wave type
	- Diquarks -> A dictionary of Interval objects, one per diquark type
	'''
	state_label: str
	state_index: int
	calculated_mass: Interval = field(default_factory=Interval.nan)
	pdg_mass: Interval = field(default_factory=Interval.nan)
	lattice_mass: Interval = field(default_factory=Interval.nan)
	partial_waves: dict[str, Interval] = field(default_factory=dict)
	diquarks: dict[str, Interval] = field(default_factory=dict)

@dataclass
class ChannelResult:
	'''
	All state results for a given baryon channel
	'''
	channel_key: ChannelKey
	states: dict[str, StateResult] = field(default_factory=dict)

	def add_state(self, state_result: StateResult) -> None:
		self.states[state_result.state_label] = state_result

	def get_state(self, state_label: str) -> StateResult:
		return self.states[state_label]

@dataclass
class BaryonResult:
	'''
	All baryon channel results for a given baryon
	'''
	baryon_name: str
	channels: dict[ChannelKey, ChannelResult] = field(default_factory=dict)

	def add_channel(self, channel_result: ChannelResult) -> None:
		self.channels[channel_result.channel_key] = channel_result

	def get_channel(self, channel_key: ChannelKey) -> ChannelResult:
		return self.channels[channel_key]

@dataclass
class AllResults:
	'''
	All results, for all baryons
	'''
	baryons: dict[str, BaryonResult] = field(default_factory=dict)

	def add_baryon(self, baryon_result: BaryonResult) -> None:
		self.baryons[baryon_result.baryon_name] = baryon_result

	def get_baryon(self, baryon_name: str) -> BaryonResult:
		return self.baryons[baryon_name]

# -----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BaryonSpec:
	'''
	Specification of a baryon category
	- Baryon name
	- Heavy flavors that exist, from f, g and h
	- Three-quark composition
	- Diquark labels
	- Wave labels, for completness (we already have what they are by default)
	'''
	name: str
	heavy_structure: str
	composition_pattern: str
	diquark_labels: tuple[str, ...]
	wave_labels: tuple[str, ...] = ("s-wave", "p-wave", "d-wave", "f-wave")

	def is_light_only(self) -> bool:
		'''
		Return True if this baryon has no heavy flavors.
		'''
		return self.heavy_structure == "none"

	def allowed_flavor_assignments(self) -> list[FlavorAssignment]:
		'''
		Return all allowed heavy-flavor assignments for this baryon.

		The allowed assignments depend only on the heavy-flavor structure
		pattern of the baryon.
		'''

		if self.heavy_structure == "none":
			return [FlavorAssignment()]

		if self.heavy_structure == "f":
			return [
				FlavorAssignment(f="s"),
				FlavorAssignment(f="c"),
				FlavorAssignment(f="b"),
			]

		if self.heavy_structure == "fg":
			return [
				FlavorAssignment(f="s", g="c"),
				FlavorAssignment(f="s", g="b"),
				FlavorAssignment(f="c", g="b"),
			]

		if self.heavy_structure == "fgh":
			return [FlavorAssignment(f="s", g="c", h="b")]

		raise ValueError(f"Unsupported heavy_structure: {self.heavy_structure}")

	def allowed_channels(self) -> list[ChannelKey]:
		'''
		Return all valid channel keys for this baryon.

		Channels are generated by combining:
		- allowed flavor assignments
		- the allowed J values (1/2, 3/2)
		- the allowed parity values (Positive, Negative)
		'''

		channels = []

		for flavor_assignment in self.allowed_flavor_assignments():
			for J in ("1/2", "3/2"):
				for parity in ("Positive", "Negative"):

					channels.append(
						ChannelKey(
							flavor_assignment=flavor_assignment,
							J=J,
							parity=parity,
						)
					)

		return channels

@dataclass
class ProjectCatalog:
	'''
	Global catalog describing the full structure of the project.

	This class centralizes all structural metadata required by the
	program, including:

	- the list of baryon categories
	- their corresponding specifications
	- ordering conventions used for output
	- allowed channel parameters
	'''

	baryon_specs: dict[str, BaryonSpec] = field(default_factory=dict)

	# Order in which baryons should appear in the final output
	baryon_order: tuple[str, ...] = (
		"Delta",
		"Lambda_f",
		"Nucleon",
		"Omega_fff",
		"Omega_ffg",
		"Omega_fgg",
		"Omega_fgh",
		"OmegaPrime_fgh",
		"Sigma_f",
		"Xi_ff",
		"Xi_fg",
		"XiPrime_fg",
	)

	# Global ordering conventions
	J_order: tuple[str, ...] = ("1/2", "3/2")
	parity_order: tuple[str, ...] = ("Positive", "Negative")
	state_order: tuple[str, ...] = ("Grd", "1st", "2nd", "3rd")
	wave_order: tuple[str, ...] = ("s-wave", "p-wave", "d-wave", "f-wave")

	@classmethod
	def build_default(cls) -> "ProjectCatalog":
		'''
		Build the default project catalog containing all baryon
		specifications used in the research project.
		'''

		baryon_specs = {

			"Delta": BaryonSpec(
				name="Delta",
				heavy_structure="none",
				composition_pattern="nnn",
				diquark_labels=("SC(nn)", "AV(nn)"),
			),

			"Lambda_f": BaryonSpec(
				name="Lambda_f",
				heavy_structure="f",
				composition_pattern="nnf",
				diquark_labels=("SC(nn)", "SC(nf)", "AV(nn)", "AV(nf)"),
			),

			"Nucleon": BaryonSpec(
				name="Nucleon",
				heavy_structure="none",
				composition_pattern="nnn",
				diquark_labels=("SC(nn)", "AV(nn)"),
			),

			"Omega_fff": BaryonSpec(
				name="Omega_fff",
				heavy_structure="f",
				composition_pattern="fff",
				diquark_labels=("SC(ff)", "AV(ff)"),
			),

			"Omega_ffg": BaryonSpec(
				name="Omega_ffg",
				heavy_structure="fg",
				composition_pattern="ffg",
				diquark_labels=("SC(ff)", "SC(fg)", "AV(ff)", "AV(fg)"),
			),

			"Omega_fgg": BaryonSpec(
				name="Omega_fgg",
				heavy_structure="fg",
				composition_pattern="fgg",
				diquark_labels=("SC(fg)", "SC(gg)", "AV(fg)", "AV(gg)"),
			),

			"Omega_fgh": BaryonSpec(
				name="Omega_fgh",
				heavy_structure="fgh",
				composition_pattern="fgh",
				diquark_labels=("SC(fg)", "SC(fh)", "SC(gh)", "AV(fg)", "AV(fh)", "AV(gh)"),
			),

			"OmegaPrime_fgh": BaryonSpec(
				name="OmegaPrime_fgh",
				heavy_structure="fgh",
				composition_pattern="fgh",
				diquark_labels=("SC(fg)", "SC(fh)", "SC(gh)", "AV(fg)", "AV(fh)", "AV(gh)"),
			),

			"Sigma_f": BaryonSpec(
				name="Sigma_f",
				heavy_structure="f",
				composition_pattern="nnf",
				diquark_labels=("SC(nn)", "SC(nf)", "AV(nn)", "AV(nf)"),
			),

			"Xi_ff": BaryonSpec(
				name="Xi_ff",
				heavy_structure="f",
				composition_pattern="nff",
				diquark_labels=("SC(nf)", "SC(ff)", "AV(nf)", "AV(ff)"),
			),

			"Xi_fg": BaryonSpec(
				name="Xi_fg",
				heavy_structure="fg",
				composition_pattern="nfg",
				diquark_labels=("SC(nf)", "SC(ng)", "SC(fg)", "AV(nf)", "AV(ng)", "AV(fg)"),
			),

			"XiPrime_fg": BaryonSpec(
				name="XiPrime_fg",
				heavy_structure="fg",
				composition_pattern="nfg",
				diquark_labels=("SC(nf)", "SC(ng)", "SC(fg)", "AV(nf)", "AV(ng)", "AV(fg)"),
			),
		}

		return cls(baryon_specs=baryon_specs)

	def get_baryon_spec(self, baryon_name: str) -> BaryonSpec:
		'''
		Retrieve the specification of a baryon by name.
		'''
		return self.baryon_specs[baryon_name]

	def ordered_baryon_specs(self) -> list[BaryonSpec]:
		'''
		Return baryon specifications in the canonical project order.
		'''
		return [self.baryon_specs[name] for name in self.baryon_order]

# -----------------------------------------------------------------------------------------

@dataclass
class ProjectPaths:
	'''
	Paths for the input data files
	'''

	code_path: Path
	data_path: Path

	@property
	def baryons_path(self) -> Path:
		return self.data_path / "baryons"
	
	@property
	def new_classes_path(self) -> Path:
		'''
		Full path to new_classes.py, which contains the hard-coded
		PDG and Lattice mass intervals.
		'''
		return (
			self.code_path.parent.parent.parent
			/ "QuarkDiquark"
			/ "Current"
			/ "python_code"
			/ "new_classes.py"
		)

	@property
	def apmeb_summary_path(self) -> Path:
		return self.baryons_path / "APMEB_Summary.txt"
	
	@property
	def all_results_output_path(self) -> Path:
		return self.baryons_path / "All_Results.txt"

	@classmethod
	def build_defaults(cls) -> "ProjectPaths":
		return cls(
			code_path = Path(__file__).resolve(),
			data_path = Path(__file__).resolve().parent.parent.parent / "QuarkDiquark" / "Current" / "outputs")

def debug_paths(paths: ProjectPaths) -> None:

	if not paths.code_path.exists():
		raise FileNotFoundError(f"Path of this python code not found: {paths.code_path}")
	if not paths.data_path.exists():
		raise FileNotFoundError(f"Path for the input data and output file not found: {paths.data_path}")
	if not paths.baryons_path.exists():
		raise FileNotFoundError(f"Path for the partial waves and diquark data not found: {paths.baryons_path}")
	if not paths.apmeb_summary_path.exists():
		raise FileNotFoundError(f"Masses input file not found: {paths.apmeb_summary_path}")
	
	print(paths.code_path)
	print(paths.data_path)
	print(paths.baryons_path)
	print(paths.apmeb_summary_path)

#paths = ProjectPaths.build_defaults()
#debug_paths(paths)

# -----------------------------------------------------------------------------------------

@dataclass
class APMEBSummaryParser:
	'''
	Parser for the APMEB_Summary.txt file

	results should look something like this:
	- Want the mass interval of the 2nd excited state of the Sigma_f baryon in the f = c, J = 3/2, Positive parity channel?
	- results["Sigma_f"]["[c]_J12_Positive"]["2nd"] = [<MIN MASS VALUE>, <MAX MASS VALUE>], an Interval object

	'''

	# Pattern definition for header: === Baryon: <BARYON CATEGORY> ===
	# For example: === Baryon: Delta ===
	baryon_pattern: re.Pattern = field(default_factory=lambda: re.compile(r"^=== Baryon: (?P<baryon>.+) ===$"))

	# Pattern definition for file name prefix without final _: [<HEAVY FLAVOR ASSIGNEMENT>]_<J>_<parity> 
	# For example: [s]_J12_Positive
	channel_pattern: re.Pattern = field(default_factory=lambda: re.compile(r"^\s*Channel:\s*(?P<channel>.+?)\s*$"))

	# Pattern definition for state mass results: <STATE> : [<MIN MASS VALUE>, <MAX MASS VALUE>] MeV (Width: <MASS WIDTH> MeV)
	# For example: Grd : [1744.0, 1785.0] MeV (Width: 41.0 MeV)
	state_pattern: re.Pattern = field(default_factory=lambda: re.compile(
		r"^\s*(?P<state>Grd|1st|2nd|3rd)\s*:\s*"
		r"\[(?P<min>-?\d+(?:\.\d+)?),\s*(?P<max>-?\d+(?:\.\d+)?)\]\s*MeV"
	))

	def parse(self, file_path: Path) -> dict[str, dict[str, dict[str, Interval]]]:

		if not file_path.exists():
			raise FileNotFoundError(f"APMEB_summary.txt file not found: {file_path}")
		
		with open(file_path, "r") as file:
			lines = file.readlines()
		
		results: dict[str, dict[str, dict[str, Interval]]] = {}

		current_baryon: str | None = None
		current_channel: str | None = None

		for raw_line in lines[2:]: # First two lines of the file are neglegible

			line = raw_line.rstrip("\n")

			# Seeing if line mathces baryon header

			baryon_match = self.baryon_pattern.match(line)
			if baryon_match:
				current_baryon = baryon_match.group("baryon")
				current_channel = None

				if current_baryon not in results:
					results[current_baryon] = {}
				
				continue

			# Seeing if line matches channel

			channel_match = self.channel_pattern.match(line)
			if channel_match:

				if current_baryon is None:
					raise ValueError(f"Found a channel before any baryon block: {line}")

				current_channel = channel_match.group("channel")

				if current_baryon not in results[current_baryon]:
					results[current_baryon][current_channel] = {}
				
				continue

			# Seeing if line mathces state results

			state_match = self.state_pattern.match(line)
			if state_match:

				if current_baryon is None or current_channel is None:
					raise ValueError(f"Found a state interval before baryon/channel context: {line}")

				state_label = state_match.group("state")
				min_value = float(state_match.group("min"))
				max_value = float(state_match.group("max"))

				results[current_baryon][current_channel][state_label] = Interval(
					min_value=min_value,
					max_value=max_value,
				)

		return results
	
	def parse_default(self, paths: ProjectPaths) -> dict[str, dict[str, dict[str, Interval]]]:
		return self.parse(paths.apmeb_summary_path)
	
	def get_interval(
		self,
		parsed_results: dict[str, dict[str, dict[str, Interval]]],
		baryon_name: str,
		channel_name: str,
		state_label: str,
	) -> Interval:
		'''
		Safely retrieve one interval from already-parsed summary data.

		If the requested baryon, channel, or state does not exist,
		return Interval.nan().
		'''

		return (
			parsed_results
			.get(baryon_name, {})
			.get(channel_name, {})
			.get(state_label, Interval.nan())
		)

def debug_APMEB_parser() -> None:

	paths = ProjectPaths.build_defaults()
	debug_paths(paths)

	parser = APMEBSummaryParser()
	mass_results = parser.parse_default(paths)

	print(f"Mass interval for Delta Grd state, J = 3/2, Positive parity: {mass_results["Delta"]["J32_Positive"]["Grd"]}")
	print(f"Mass interval for Sigma_c 1st state, J = 1/2, Positive parity: {mass_results["Sigma_f"]["[c]_J12_Positive"]["1st"]}")
	print(f"Mass interval for Omega_cc 2nd state, J = 1/2, Negative parity: {mass_results["Omega_fgg"]["[sc]_J12_Negative"]["2nd"]}")
	print(f"Mass interval for Omega_cc 2nd state, J = 1/2, Negative parity: {parser.get_interval(mass_results, "Omega_fgg", "[sc]_J32_Negative", "2nd")}")
	print(f"Mass interval for Omega_cb 3rd state, J = 1/2, Positive parity: {parser.get_interval(mass_results, "Omega_fgh", "[scb]_J12_Positive", "3rd")}")
	#print(f"Mass interval for Omega_cc 2nd state, J = 3/2, Negative parity: {mass_results["Omega_fgg"]["[sc]_J32_Negative"]["2nd"]}")
	#print(f"Mass interval for Omega_cb 3rd state, J = 1/2, Positive parity: {mass_results["Omega_fgh"]["[scb]_J12_Positive"]["3rd"]}")

#debug_APMEB_parser()

# -----------------------------------------------------------------------------------------

@dataclass
class AnalysisFileParser:
	'''
	Shared parser for PartWavs_Analysis.txt and DQ_Analysis.txt files.

	Both file types have the same high-level structure:
	- first 4 lines are ignored
	- then come 4 state blocks
	- each block starts with: State: <STATE> (i=<INDEX>)
	- component lines have: <component> : <value> +/- <uncertainty> (<method>)
	- each block also contains a SUM line, which is ignored by this parser

	This base class extracts Interval objects from the contribution lines.
	'''

	# Example: State: 2nd (i=2)
	state_header_pattern: re.Pattern = field(default_factory=lambda: re.compile(
		r"^State:\s*(?P<state>Grd|1st|2nd|3rd)\s*\(i=(?P<index>\d+)\)\s*$"
	))

	# Example:   s-wave          : 0.4237 +/- 0.0062 (cubic)
	component_pattern: re.Pattern = field(default_factory=lambda: re.compile(
		r"^\s*(?P<component>.+?)\s*:\s*"
		r"(?P<value>-?\d+(?:\.\d+)?)\s*\+/-\s*"
		r"(?P<uncertainty>-?\d+(?:\.\d+)?)\s*"
		r"\((?P<method>.+?)\)\s*$"
	))

	# Example:   SUM             : 1.0000
	sum_pattern: re.Pattern = field(default_factory=lambda: re.compile(
		r"^\s*SUM\s*:\s*(?P<sum>-?\d+(?:\.\d+)?)\s*$"
	))

	def parse_file(
		self,
		file_path: Path,
		expected_components: tuple[str, ...] | list[str],
	) -> dict[str, dict[str, Interval]]:
		'''
		Parse one analysis file and return:

		results[state_label][component_name] = Interval(...)

		Only the expected components are retained. Missing components are filled
		with Interval.nan().
		'''

		if not file_path.exists():
			raise FileNotFoundError(f"Analysis file not found: {file_path}")

		with open(file_path, "r") as file:
			lines = file.readlines()

		results: dict[str, dict[str, Interval]] = {}
		current_state: str | None = None

		# First four lines are header text and are ignored
		for raw_line in lines[4:]:
			line = raw_line.rstrip("\n")

			state_match = self.state_header_pattern.match(line)
			if state_match:
				current_state = state_match.group("state")
				results[current_state] = {
					component: Interval.nan()
					for component in expected_components
				}
				continue

			if current_state is None:
				continue

			if self.sum_pattern.match(line):
				# The SUM line is currently not needed for the normalized result model
				continue

			component_match = self.component_pattern.match(line)
			if component_match:
				component_name = component_match.group("component").strip()

				# Ignore unexpected components silently for now.
				# The parser only stores the components relevant to the current baryon/file type.
				if component_name not in expected_components:
					continue

				value = float(component_match.group("value"))
				uncertainty = float(component_match.group("uncertainty"))

				results[current_state][component_name] = Interval.from_val_pm_unc(
					value=value,
					uncertainty=uncertainty,
				)

		# Ensure all four expected states exist, even if the file is incomplete
		for state_label in ("Grd", "1st", "2nd", "3rd"):
			if state_label not in results:
				results[state_label] = {
					component: Interval.nan()
					for component in expected_components
				}

		return results

	def get_interval(
		self,
		parsed_results: dict[str, dict[str, Interval]],
		state_label: str,
		component_name: str,
	) -> Interval:
		'''
		Safely retrieve one interval from already-parsed analysis data.

		If the requested state or component does not exist,
		return Interval.nan().
		'''

		return (
			parsed_results
			.get(state_label, {})
			.get(component_name, Interval.nan())
		)

@dataclass
class WaveAnalysisParser(AnalysisFileParser):
	'''
	Parser for PartWavs_Analysis.txt files.

	The expected components are always the four partial waves:
	- s-wave
	- p-wave
	- d-wave
	- f-wave
	'''

	wave_components: tuple[str, ...] = ("s-wave", "p-wave", "d-wave", "f-wave")

	def parse(self, file_path: Path) -> dict[str, dict[str, Interval]]:
		'''
		Parse one partial-wave analysis file.
		'''
		return self.parse_file(
			file_path=file_path,
			expected_components=self.wave_components,
		)

@dataclass
class DiquarkAnalysisParser(AnalysisFileParser):
	'''
	Parser for DQ_Analysis.txt files.

	The symbolic diquark labels stored in BaryonSpec are converted into their
	physical form using the FlavorAssignment of the specific channel being read.
	For example:

	- AV(nf) -> AV(nc) when f = c
	- SC(fg) -> SC(sc) when f = s and g = c
	'''

	def parse(
		self,
		file_path: Path,
		baryon_spec: BaryonSpec,
		flavor_assignment: FlavorAssignment,
	) -> dict[str, dict[str, Interval]]:
		'''
		Parse one diquark analysis file using the physical diquark labels
		corresponding to the given baryon specification and flavor assignment.
		'''

		physical_diquark_labels = tuple(
			flavor_assignment.substitute_symbols(label)
			for label in baryon_spec.diquark_labels
		)

		return self.parse_file(
			file_path=file_path,
			expected_components=physical_diquark_labels,
		)

def debug_wave_and_diquark_parser() -> None:

	paths = ProjectPaths.build_defaults()
	#debug_paths(paths)

	catalog = ProjectCatalog.build_default() # Needed for the diquark labels of each baryon

	wave_parser = WaveAnalysisParser()
	diquark_parser = DiquarkAnalysisParser()

	wave_file_eg = paths.baryons_path / "Nucleon" / "analysis_waves" / "J12_Positive_PartWavs_Analysis.txt"
	wave_results = wave_parser.parse(wave_file_eg)
	print(wave_results["Grd"]["s-wave"])

	diquark_file_eg = paths.baryons_path / "Sigma_f" / "analysis_diquarks" / "[c]_J32_Positive_DQ_Analysis.txt"
	diquark_results = diquark_parser.parse(diquark_file_eg, catalog.get_baryon_spec("Sigma_f"), FlavorAssignment(f="c"))
	# Note that in the diquark parser, two implicit information from the file path are written explicitly:
	# - The baryon
	# - The heavy flavor assignment
	print(diquark_results["Grd"]["AV(nc)"])

#debug_wave_and_diquark_parser()

# -----------------------------------------------------------------------------------------

@dataclass
class PDGLatticeParser:
	'''
	Parser for the hard-coded add_state(...) entries in new_classes.py.

	This parser reads the source file as plain text, extracts all add_state(...)
	calls, reproduces the channel-placement logic of add_state, and builds two
	normalized lookup tables:

	- pdg_results[baryon_name][channel_name][state_label] = Interval(...)
	- lattice_results[baryon_name][channel_name][state_label] = Interval(...)

	The parser does not import new_classes.py. It only reads the explicit
	hard-coded add_state instances from the source text.
	'''

	# Matches lines such as:
	# add_state("Nucleon", "1/2", "+", 938.3, 939.6, "PDG")
	add_state_pattern: re.Pattern = field(default_factory=lambda: re.compile(
		r'^\s*add_state\((?P<args>.*)\)\s*(?:#.*)?$'
	))

	state_order: tuple[str, ...] = ("Grd", "1st", "2nd", "3rd")

	def parse(
		self,
		new_classes_path: Path,
	) -> tuple[
		dict[str, dict[str, dict[str, Interval]]],
		dict[str, dict[str, dict[str, Interval]]],
	]:
		'''
		Parse new_classes.py and return:

		- pdg_results
		- lattice_results
		'''

		if not new_classes_path.exists():
			raise FileNotFoundError(f"new_classes.py not found: {new_classes_path}")

		with open(new_classes_path, "r") as file:
			lines = file.readlines()

		pdg_results: dict[str, dict[str, dict[str, Interval]]] = {}
		lattice_results: dict[str, dict[str, dict[str, Interval]]] = {}

		for raw_line in lines:
			line = raw_line.strip()

			match = self.add_state_pattern.match(line)
			if not match:
				continue

			args_text = match.group("args")
			name, J, P, m_min, m_max, source = self._parse_add_state_args(args_text)

			baryon_name, flavor_assignment = self._split_name_and_flavors(name)
			target_channels = self._target_channel_names(flavor_assignment, J, P)
			interval = Interval(min_value=float(m_min), max_value=float(m_max))

			target_results = pdg_results if source == "PDG" else lattice_results

			for channel_name in target_channels:
				self._store_first_free_state(
					target_results=target_results,
					baryon_name=baryon_name,
					channel_name=channel_name,
					interval=interval,
				)

		return pdg_results, lattice_results

	def get_interval(
		self,
		parsed_results: dict[str, dict[str, dict[str, Interval]]],
		baryon_name: str,
		channel_name: str,
		state_label: str,
	) -> Interval:
		'''
		Safely retrieve one PDG/Lattice interval.

		If the requested baryon, channel, or state does not exist,
		return Interval.nan().
		'''

		return (
			parsed_results
			.get(baryon_name, {})
			.get(channel_name, {})
			.get(state_label, Interval.nan())
		)

	def _parse_add_state_args(
		self,
		args_text: str,
	) -> tuple[str, str, str, float, float, str]:
		'''
		Parse the argument list of one add_state(...) call.

		Example input:
		'"Nucleon", "1/2", "+", 938.3, 939.6, "PDG"'
		'''

		parsed = ast.parse(f"f({args_text})", mode="eval")
		call_node = parsed.body

		if not isinstance(call_node, ast.Call):
			raise ValueError(f"Could not parse add_state arguments: {args_text}")

		args = [ast.literal_eval(arg) for arg in call_node.args]

		if len(args) == 5:
			# Defensive support in case source is omitted and defaults to PDG
			name, J, P, m_min, m_max = args
			source = "PDG"
		elif len(args) == 6:
			name, J, P, m_min, m_max, source = args
		else:
			raise ValueError(f"Unexpected add_state argument count: {args_text}")

		if source not in ("PDG", "Lattice"):
			raise ValueError(f"Unexpected source in add_state: {source}")

		return name, J, P, float(m_min), float(m_max), source

	def _split_name_and_flavors(
		self,
		name: str,
	) -> tuple[str, FlavorAssignment]:
		'''
		Convert names such as:

		- Nucleon
		- Sigma_f_[c]
		- Xi_fg_[sc]
		- Omega_fgh_[scb]

		into:
		- baryon_name
		- FlavorAssignment
		'''

		if "_[" not in name:
			return name, FlavorAssignment()

		baryon_name, flavor_part = name.split("_[", 1)
		flavor_code = flavor_part.rstrip("]")

		if len(flavor_code) == 1:
			return baryon_name, FlavorAssignment(f=flavor_code)

		if len(flavor_code) == 2:
			return baryon_name, FlavorAssignment(f=flavor_code[0], g=flavor_code[1])

		if len(flavor_code) == 3:
			return baryon_name, FlavorAssignment(
				f=flavor_code[0],
				g=flavor_code[1],
				h=flavor_code[2],
			)

		raise ValueError(f"Unexpected flavor code in add_state name: {name}")

	def _target_channel_names(
		self,
		flavor_assignment: FlavorAssignment,
		J: str,
		P: str,
	) -> list[str]:
		'''
		Reproduce the channel-expansion logic of add_state.

		- J == "?" expands to both 1/2 and 3/2
		- P == "?" expands to both Positive and Negative
		'''

		if J == "?":
			J_values = ["1/2", "3/2"]
		else:
			J_values = [J]

		if P == "?":
			parities = ["Positive", "Negative"]
		elif P == "+":
			parities = ["Positive"]
		elif P == "-":
			parities = ["Negative"]
		else:
			raise ValueError(f"Unexpected parity value in add_state: {P}")

		channel_names = []

		for J_value in J_values:
			for parity in parities:
				channel_key = ChannelKey(
					flavor_assignment=flavor_assignment,
					J=J_value,
					parity=parity,
				)
				channel_names.append(channel_key.summary_channel_name())

		return channel_names

	def _store_first_free_state(
		self,
		target_results: dict[str, dict[str, dict[str, Interval]]],
		baryon_name: str,
		channel_name: str,
		interval: Interval,
	) -> None:
		'''
		Store one interval in the first free state slot of a channel.

		State order is:
		- Grd
		- 1st
		- 2nd
		- 3rd

		If all four slots are already occupied, the new interval is ignored,
		which matches the behavior of add_state in new_classes.py.
		'''

		if baryon_name not in target_results:
			target_results[baryon_name] = {}

		if channel_name not in target_results[baryon_name]:
			target_results[baryon_name][channel_name] = {}

		channel_states = target_results[baryon_name][channel_name]

		for state_label in self.state_order:
			if state_label not in channel_states:
				channel_states[state_label] = interval
				return

		# If all four states already exist, do nothing
		return

def debug_pdg_lattice_parser() -> None:

	parser = PDGLatticeParser()

	new_classes_path = (
		Path(__file__).resolve().parent.parent.parent
		/ "QuarkDiquark"
		/ "Current"
		/ "python_code"
		/ "new_classes.py"
	)

	pdg_results, lattice_results = parser.parse(new_classes_path)

	print(parser.get_interval(pdg_results, "Nucleon", "J12_Positive", "Grd"))
	print(parser.get_interval(lattice_results, "Omega_fff", "[c]_J32_Positive", "Grd"))
	print(parser.get_interval(pdg_results, "Omega_fgh", "[scb]_J32_Negative", "Grd"))

#debug_pdg_lattice_parser()

# -----------------------------------------------------------------------------------------

@dataclass
class ResultsAssembler:
	'''
	Build the complete normalized AllResults structure by combining
	data from all parsers and project metadata.
	'''

	paths: ProjectPaths
	catalog: ProjectCatalog

	mass_parser: APMEBSummaryParser
	wave_parser: WaveAnalysisParser
	diquark_parser: DiquarkAnalysisParser
	pdg_lattice_parser: PDGLatticeParser

	def assemble(self) -> AllResults:
		'''
		Construct the full AllResults object by iterating through all
		expected baryons, channels, and states.
		'''

		all_results = AllResults()

		# Parse the mass-related sources once
		mass_data = self.mass_parser.parse_default(self.paths)
		pdg_data, lattice_data = self.pdg_lattice_parser.parse(self.paths.new_classes_path)

		for baryon_spec in self.catalog.ordered_baryon_specs():

			baryon_result = BaryonResult(baryon_spec.name)

			for flavor_assignment in baryon_spec.allowed_flavor_assignments():

				for channel_key in baryon_spec.allowed_channels():

					# Keep only channels matching the current flavor assignment
					if channel_key.flavor_assignment != flavor_assignment:
						continue

					channel_result = ChannelResult(channel_key)
					channel_prefix = channel_key.prefix()
					channel_name = channel_key.summary_channel_name()

					wave_file = (
						self.paths.baryons_path
						/ baryon_spec.name
						/ "analysis_waves"
						/ f"{channel_prefix}PartWavs_Analysis.txt"
					)

					dq_file = (
						self.paths.baryons_path
						/ baryon_spec.name
						/ "analysis_diquarks"
						/ f"{channel_prefix}DQ_Analysis.txt"
					)

					if wave_file.exists():
						wave_data = self.wave_parser.parse(wave_file)
					else:
						wave_data = {}

					if dq_file.exists():
						dq_data = self.diquark_parser.parse(
							dq_file,
							baryon_spec,
							flavor_assignment,
						)
					else:
						dq_data = {}

					for state_index, state_label in enumerate(self.catalog.state_order):

						state_result = StateResult(
							state_label=state_label,
							state_index=state_index,
						)

						# Calculated mass interval from APMEB
						state_result.calculated_mass = self.mass_parser.get_interval(
							mass_data,
							baryon_spec.name,
							channel_name,
							state_label,
						)

						# PDG mass interval
						state_result.pdg_mass = self.pdg_lattice_parser.get_interval(
							pdg_data,
							baryon_spec.name,
							channel_name,
							state_label,
						)

						# Lattice mass interval
						state_result.lattice_mass = self.pdg_lattice_parser.get_interval(
							lattice_data,
							baryon_spec.name,
							channel_name,
							state_label,
						)

						# Partial waves
						for wave in self.catalog.wave_order:
							state_result.partial_waves[wave] = (
								wave_data
								.get(state_label, {})
								.get(wave, Interval.nan())
							)

						# Diquarks
						for dq in baryon_spec.diquark_labels:
							physical_dq = flavor_assignment.substitute_symbols(dq)

							state_result.diquarks[physical_dq] = (
								dq_data
								.get(state_label, {})
								.get(physical_dq, Interval.nan())
							)

						channel_result.add_state(state_result)

					baryon_result.add_channel(channel_result)

			all_results.add_baryon(baryon_result)

		return all_results

def debug_results_assembler() -> None:

	paths = ProjectPaths.build_defaults()
	catalog = ProjectCatalog.build_default()

	assembler = ResultsAssembler(
		paths = paths,
		catalog = catalog,
		mass_parser = APMEBSummaryParser(),
		wave_parser = WaveAnalysisParser(),
		diquark_parser = DiquarkAnalysisParser()
	)

	results = assembler.assemble()

	print(results.get_baryon("Nucleon"))
	print("")
	print(results.get_baryon("Sigma_f"))

#debug_results_assembler()

def debug_expected_inputs() -> None:
	'''
	Print a completeness report for all expected baryon/flavor/channel inputs.

	For each expected channel, this reports whether:
	- the channel is present in APMEB_Summary.txt
	- the partial-wave file exists
	- the diquark file exists

	This is useful for diagnosing missing calculations, wrong prefixes,
	or path mismatches before assembling the full result tree.
	'''

	paths = ProjectPaths.build_defaults()
	catalog = ProjectCatalog.build_default()
	mass_parser = APMEBSummaryParser()

	mass_data = mass_parser.parse_default(paths)

	print("\n=== Expected Input Completeness Report ===\n")

	for baryon_spec in catalog.ordered_baryon_specs():

		print(f"Baryon: {baryon_spec.name}")

		for flavor_assignment in baryon_spec.allowed_flavor_assignments():

			flavor_code = flavor_assignment.code()
			if flavor_code is None:
				print("  Flavor assignment: light-only")
			else:
				print(f"  Flavor assignment: {flavor_code}")

			for channel_key in baryon_spec.allowed_channels():

				# Keep only channels belonging to the current flavor assignment
				if channel_key.flavor_assignment != flavor_assignment:
					continue

				channel_name = channel_key.summary_channel_name()
				channel_prefix = channel_key.prefix()

				wave_file = (
					paths.baryons_path
					/ baryon_spec.name
					/ "analysis_waves"
					/ f"{channel_prefix}PartWavs_Analysis.txt"
				)

				dq_file = (
					paths.baryons_path
					/ baryon_spec.name
					/ "analysis_diquarks"
					/ f"{channel_prefix}DQ_Analysis.txt"
				)

				apmeb_has_channel = (
					baryon_spec.name in mass_data
					and channel_name in mass_data[baryon_spec.name]
				)

				wave_exists = wave_file.exists()
				dq_exists = dq_file.exists()

				print(f"    {channel_name}")
				print(f"      APMEB   : {'YES' if apmeb_has_channel else 'NO'}")
				print(f"      Waves   : {'YES' if wave_exists else 'NO'}")
				print(f"      Diquarks: {'YES' if dq_exists else 'NO'}")

		print()
		print("Btw, APMEB stands for All Possible Methods Error Bar, meaning its a mass interval built from the uncertainty of all appropriate methods' mean values")
		print()

#debug_expected_inputs()

# -----------------------------------------------------------------------------------------

@dataclass
class AllResultsWriter:
	'''
	Write the normalized AllResults object to the final All_Results.txt file.

	This class is responsible only for formatting and writing output.
	It does not parse files and does not assemble data.
	'''

	indent_unit: str = "    "

	def write(self, all_results: AllResults, catalog: ProjectCatalog, output_path: Path) -> None:
		'''
		Write the complete All_Results.txt file.
		'''

		with open(output_path, "w") as file:
			for baryon_name in catalog.baryon_order:
				baryon_result = all_results.get_baryon(baryon_name)
				baryon_spec = catalog.get_baryon_spec(baryon_name)

				self._write_baryon_block(file, baryon_result, baryon_spec, catalog)
				file.write("=============================================================================\n")

	def _write_baryon_block(
		self,
		file,
		baryon_result: BaryonResult,
		baryon_spec: BaryonSpec,
		catalog: ProjectCatalog,
	) -> None:
		'''
		Write one full baryon block.
		'''

		file.write(f"Baryon: {baryon_spec.name}\n")

		if baryon_spec.is_light_only():
			for channel_key in baryon_spec.allowed_channels():
				channel_result = baryon_result.get_channel(channel_key)
				self._write_channel_section(
					file=file,
					channel_result=channel_result,
					baryon_spec=baryon_spec,
					catalog=catalog,
					base_indent_level=1,
				)
		else:
			for flavor_assignment in baryon_spec.allowed_flavor_assignments():
				header = self._format_heavy_flavor_header(baryon_spec, flavor_assignment)
				file.write(f"{self._indent(1)}{header}\n")

				for channel_key in baryon_spec.allowed_channels():
					if channel_key.flavor_assignment != flavor_assignment:
						continue

					channel_result = baryon_result.get_channel(channel_key)

					self._write_channel_section(
						file=file,
						channel_result=channel_result,
						baryon_spec=baryon_spec,
						catalog=catalog,
						base_indent_level=2,
					)

	def _write_channel_section(
		self,
		file,
		channel_result: ChannelResult,
		baryon_spec: BaryonSpec,
		catalog: ProjectCatalog,
		base_indent_level: int,
	) -> None:
		'''
		Write one channel section and its four state blocks.
		'''

		file.write(
			f"{self._indent(base_indent_level)}{channel_result.channel_key.display_label()}\n"
		)

		for state_label in catalog.state_order:
			state_result = channel_result.get_state(state_label)

			self._write_state_section(
				file=file,
				state_result=state_result,
				baryon_spec=baryon_spec,
				base_indent_level=base_indent_level + 1,
			)

	def _write_state_section(
		self,
		file,
		state_result: StateResult,
		baryon_spec: BaryonSpec,
		base_indent_level: int,
	) -> None:
		'''
		Write one state block, including masses, partial waves, and diquarks.
		'''

		state_display = self._format_state_label(state_result.state_label)

		file.write(f"{self._indent(base_indent_level)}State = {state_display}\n")
		file.write(
			f"{self._indent(base_indent_level)}Calculated mass interval = "
			f"{state_result.calculated_mass.format(decimals=1)}\n"
		)
		file.write(
			f"{self._indent(base_indent_level)}PDG mass interval = "
			f"{state_result.pdg_mass.format(decimals=1)}\n"
		)
		file.write(
			f"{self._indent(base_indent_level)}LatticeQCD mass interval = "
			f"{state_result.lattice_mass.format(decimals=1)}\n"
		)

		file.write(f"{self._indent(base_indent_level)}Partial waves distributions:\n")
		for wave_label in ("s-wave", "p-wave", "d-wave", "f-wave"):
			interval = state_result.partial_waves.get(wave_label, Interval.nan())
			file.write(
				f"{self._indent(base_indent_level + 1)}{wave_label} interval = "
				f"{interval.format(decimals=4)}\n"
			)

		file.write(f"{self._indent(base_indent_level)}Diquark distributions:\n")
		for diquark_label, interval in state_result.diquarks.items():
			file.write(
				f"{self._indent(base_indent_level + 1)}{diquark_label} interval = "
				f"{interval.format(decimals=4)}\n"
			)

		file.write(f"{self._indent(base_indent_level)}-----------------------------------------------------------------------------\n")

	def _format_state_label(self, state_label: str) -> str:
		'''
		Convert internal state labels into the display form used in All_Results.txt.
		'''

		mapping = {
			"Grd": "Grd (Ground)",
			"1st": "1st (First excited)",
			"2nd": "2nd (Second excited)",
			"3rd": "3rd (Third excited)",
		}

		return mapping[state_label]

	def _format_heavy_flavor_header(
		self,
		baryon_spec: BaryonSpec,
		flavor_assignment: FlavorAssignment,
	) -> str:
		'''
		Build the heavy-flavor specification line for one baryon/flavor case.
		'''

		assignment_parts = []
		if flavor_assignment.f is not None:
			assignment_parts.append(f"f = {flavor_assignment.f}")
		if flavor_assignment.g is not None:
			assignment_parts.append(f"g = {flavor_assignment.g}")
		if flavor_assignment.h is not None:
			assignment_parts.append(f"h = {flavor_assignment.h}")

		assignment_text = ", ".join(assignment_parts)
		composition_text = self._physical_composition(baryon_spec, flavor_assignment)

		return f"Heavy flavor specification: {assignment_text} (Forming {composition_text})"

	def _physical_composition(
		self,
		baryon_spec: BaryonSpec,
		flavor_assignment: FlavorAssignment,
	) -> str:
		'''
		Convert the symbolic composition pattern into the physical flavor composition.
		'''

		return flavor_assignment.substitute_symbols(baryon_spec.composition_pattern)

	def _indent(self, level: int) -> str:
		'''
		Return the indentation string for a given indentation level.
		'''

		return self.indent_unit * level

# -----------------------------------------------------------------------------------------

def main() -> None:
	'''
	Main entry point of the program.

	This function:
	- builds the default project paths
	- validates the required input locations
	- builds the default catalog
	- assembles the complete normalized result tree
	- writes All_Results.txt
	'''

	paths = ProjectPaths.build_defaults()
	catalog = ProjectCatalog.build_default()

	assembler = ResultsAssembler(
		paths=paths,
		catalog=catalog,
		mass_parser=APMEBSummaryParser(),
		wave_parser=WaveAnalysisParser(),
		diquark_parser=DiquarkAnalysisParser(),
		pdg_lattice_parser=PDGLatticeParser()
	)

	all_results = assembler.assemble()

	writer = AllResultsWriter()
	writer.write(
		all_results=all_results,
		catalog=catalog,
		output_path=paths.all_results_output_path,
	)

	print(f"All results written to: {paths.all_results_output_path}")


if __name__ == "__main__":
	main()
