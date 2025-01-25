"""Shared models for git-smart-commit."""
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field

class CommitType(str, Enum):
    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"

@dataclass
class FileChange:
    path: str
    status: str
    content_diff: str
    is_staged: bool

class CommitUnit(BaseModel):
    type: CommitType
    scope: Optional[str]
    description: str
    files: List[str]
    body: Optional[str]
    message: Optional[str]

class RelationshipResult(BaseModel):
    groups: List[List[str]] = Field(description="Groups of related files")
    reasoning: str = Field(description="Explanation of why files are grouped together")
    commit_units: List[CommitUnit] = Field(default_factory=list, description="Suggested commit units for each group")

class CommitMessageResult(BaseModel):
    commit_type: CommitType
    scope: Optional[str]
    description: str
    reasoning: str = Field(description="Explanation of why these changes were made")
    related_files: List[str]
