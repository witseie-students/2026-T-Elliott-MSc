"""
Pydantic models shared across the engine.
"""

from typing import List, Dict, Literal, Optional
from pydantic import BaseModel

class NarratorTurn(BaseModel):
    action: Literal["think", "final"]
    narrative: str
    final_answer: Optional[str] = None

class RumsfeldTurn(BaseModel):            
    knowns: List[str]
    unknowns: List[str]

class BranchDecision(BaseModel):
    branch: Literal["single", "multi"]
    plan:   Optional[str] = None
    plans:  Optional[List[Dict[str, str]]] = None

class QuestionTurn(BaseModel):
    question: str

class NullQuestionTurn(BaseModel):
    null_question: str

class Bundle(BaseModel):
    answer: str
    reasoning: List[str]
    confidence: float
