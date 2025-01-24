"""Commit message validation using Chain of Responsibility pattern."""
from abc import ABC, abstractmethod
from typing import Optional, Tuple

class ValidationHandler(ABC):
    """Abstract base class for validation handlers."""
    
    def __init__(self, next_handler: Optional['ValidationHandler'] = None):
        self.next_handler = next_handler
    
    def handle(self, message: str) -> Tuple[bool, str]:
        """Handle validation and pass to next handler if valid."""
        result = self.validate(message)
        if not result[0] or not self.next_handler:
            return result
        return self.next_handler.handle(message)
    
    @abstractmethod
    def validate(self, message: str) -> Tuple[bool, str]:
        """Validate the commit message."""
        pass

class EmptyMessageHandler(ValidationHandler):
    """Validates that the message is not empty."""
    
    def validate(self, message: str) -> Tuple[bool, str]:
        lines = message.split('\n')
        if not lines or not lines[0].strip():
            return False, "Empty commit message"
        return True, ""

class SubjectLengthHandler(ValidationHandler):
    """Validates the subject line length."""
    
    def __init__(self, max_length: int = 50, next_handler: Optional[ValidationHandler] = None):
        super().__init__(next_handler)
        self.max_length = max_length
    
    def validate(self, message: str) -> Tuple[bool, str]:
        subject = message.split('\n')[0]
        if len(subject) > self.max_length:
            return False, f"Subject line too long ({len(subject)} > {self.max_length})"
        return True, ""

class SubjectPeriodHandler(ValidationHandler):
    """Validates that the subject line doesn't end with a period."""
    
    def validate(self, message: str) -> Tuple[bool, str]:
        subject = message.split('\n')[0]
        if subject.endswith('.'):
            return False, "Subject line should not end with a period"
        return True, ""

class ConventionalFormatHandler(ValidationHandler):
    """Validates conventional commit format."""
    
    def validate(self, message: str) -> Tuple[bool, str]:
        subject = message.split('\n')[0]
        if ':' not in subject:
            return False, "Subject line must follow format: type(scope): description"
        return True, ""

class BlankLineHandler(ValidationHandler):
    """Validates blank line after subject."""
    
    def validate(self, message: str) -> Tuple[bool, str]:
        lines = message.split('\n')
        if len(lines) > 1 and lines[1] != '':
            return False, "Leave one blank line after subject"
        return True, ""

class BodyLineLengthHandler(ValidationHandler):
    """Validates body line lengths."""
    
    def __init__(self, max_length: int = 72, next_handler: Optional[ValidationHandler] = None):
        super().__init__(next_handler)
        self.max_length = max_length
    
    def validate(self, message: str) -> Tuple[bool, str]:
        lines = message.split('\n')
        if len(lines) > 2:  # Has body
            for line in lines[2:]:
                if len(line) > self.max_length:
                    return False, f"Body line too long: {line}"
        return True, ""

def create_validation_chain(max_subject_length: int = 50, max_body_length: int = 72) -> ValidationHandler:
    """Create the default validation chain."""
    body_length = BodyLineLengthHandler(max_body_length)
    blank_line = BlankLineHandler(body_length)
    conventional = ConventionalFormatHandler(blank_line)
    subject_period = SubjectPeriodHandler(conventional)
    subject_length = SubjectLengthHandler(max_subject_length, subject_period)
    empty_message = EmptyMessageHandler(subject_length)
    
    return empty_message 