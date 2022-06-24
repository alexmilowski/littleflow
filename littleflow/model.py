from dataclasses import dataclass, field

@dataclass
class ParameterLiteral:
   value : 'typing.Any'
   media_type : str = None
   line : int = 0
   column : int = 0

@dataclass
class Destination:
   pass

@dataclass
class LabelDestination(Destination):
   name : str

@dataclass
class Step:
   pass

@dataclass
class Start(Step):
   index : int = 0

@dataclass
class End(Step):
   index : int

@dataclass
class Iterate(Step):
   step : Step = None

@dataclass
class LiteralSource(Step):
   index : int
   parameters: ParameterLiteral

@dataclass
class ResourceSource(Step):
   index : int
   uri : str = ''
   parameters: ParameterLiteral = None

@dataclass
class ResourceSink(Step):
   index : int
   uri : str = ''
   parameters: ParameterLiteral = None

@dataclass
class Task(Step):
   index : int
   name : str
   line : int = 0
   column : int = 0
   parameters : ParameterLiteral = None

@dataclass
class Statement:
   source : str = None
   destination : str = None
   steps : list[Step] = field(default_factory=list)

@dataclass
class Flow:
   named_inputs : dict = field(default_factory=dict)
   named_outputs : dict = field(default_factory=dict)
   statements : list[Statement] = field(default_factory=list)
   indexed : list[Step] = field(default_factory=list)

@dataclass
class Subflow(Step):
   index : int
   flow : Flow
