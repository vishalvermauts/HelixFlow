from pydantic import BaseModel
from typing import List, Optional


class MessageContract(BaseModel):
    role: str
    content: str


class InferenceRequest(BaseModel):
    model: str
    messages: List[MessageContract]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class StatusResponse(BaseModel):
    status: str
    engine: str
    cache: str
