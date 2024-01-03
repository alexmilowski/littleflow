from pydantic import BaseModel
import datetime
from enum import Enum
from typing import Any
from flask.json.provider import DefaultJSONProvider

class StatusCode(Enum):
    Success = 'Success'
    Error = 'Error'
    Unavailable = 'Unavailable'

class StatusResponse(BaseModel):
   status: StatusCode = StatusCode.Success
   message: str = ''
   data: Any = None

class VersionInfo(BaseModel):
   littleflow: str
   littleflow_redis: str

class WorkflowId(BaseModel):
   workflow: str

class ArchiveLocation(BaseModel):
   bucket: str = None
   uri: str = None

class Location(BaseModel):
   uri: str = None

class WorkflowStart(BaseModel):
   workflow: str
   input: Any = None

class ServiceJSONProvider(DefaultJSONProvider):
   def default(self, obj):
      if isinstance(obj,Enum):
         return obj.value
      if isinstance(obj, datetime.datetime):
         return obj.isoformat()
      if isinstance(obj, datetime.date):
         return obj.isoformat()
      if isinstance(obj, datetime.time):
         return obj.isoformat()
      if isinstance(obj,BaseModel):
         # TODO: This should probable be configurable
         return obj.dict(exclude_none=True,exclude={'_id' : True, 'spec': {'_id'}})
      return super().default(obj)

