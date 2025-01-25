"""Commit message validation."""
from typing import Tuple
from .validation import create_validation_chain

class CommitMessageValidator:
    """Validates commit messages against conventional commit standards."""
    
    def __init__(self, max_subject_length: int = 50, max_body_length: int = 72):
        self.max_subject_length = max_subject_length
        self.max_body_line_length = max_body_length
        self.validation_chain = create_validation_chain(max_subject_length, max_body_length)
        
    def validate(self, message: str) -> Tuple[bool, str]:
        """Validate a commit message against standards."""
        return self.validation_chain.handle(message) 