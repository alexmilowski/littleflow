from dataclasses import dataclass, field
from enum import Enum

class LiteralType(Enum):
   EMPTY = 0
   YAML = 1
   JSON_OBJECT = 2
   JSON_ARRAY = 3

@dataclass
class ParameterLiteral:
   value : str
   type : LiteralType = LiteralType.EMPTY
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
   index : int = -1

@dataclass
class LiteralSource(Step):
   index : int
   value : str
   type : LiteralType = LiteralType.EMPTY
   line : int = 0
   column : int = 0

@dataclass
class ResourceSource(Step):
   index : int
   uri : str = ''
   parameters: ParameterLiteral = None

@dataclass
class ResourceSink(Step):
   index : int
   uri : str = ''
   merge : bool = False
   parameters: ParameterLiteral = None

@dataclass
class Task(Step):
   index : int
   name : str
   merge : bool = False
   line : int = 0
   column : int = 0
   parameters : ParameterLiteral = None

@dataclass
class Statement:
   source : str = None
   destination : str = None
   merge_destination : bool = False
   steps : list[Step] = field(default_factory=list)

@dataclass
class SubFlow(Step):
   index : int
   merge : bool = False
   named_inputs : dict = field(default_factory=dict)
   named_outputs : dict = field(default_factory=dict)
   statements : list[Statement] = field(default_factory=list)

@dataclass
class Declaration:
   kind : str
   name : str
   doc : str = None
   parameters : ParameterLiteral = None

@dataclass
class Workflow:
   name : str = None
   indexed : list[Step] = field(default_factory=list)
   flows : list[SubFlow] = field(default_factory=list)
   declarations : dict = field(default_factory=dict)
   doc : str = None
