"""Commit message validation."""
from typing import Tuple

class CommitMessageValidator:
    """Validates commit messages against conventional commit standards."""
    
    def __init__(self):
        self.max_subject_length = 50
        self.max_body_line_length = 72
        
    def validate(self, message: str) -> Tuple[bool, str]:
        """Validate a commit message against standards."""
        lines = message.split('\n')
        if not lines:
            return False, "Empty commit message"
            
        subject = lines[0]
        
        # Validate subject line
        if len(subject) > self.max_subject_length:
            return False, f"Subject line too long ({len(subject)} > {self.max_subject_length})"
            
        if subject.endswith('.'):
            return False, "Subject line should not end with a period"
            
        # Validate conventional commit format
        if ':' not in subject:
            return False, "Subject line must follow format: type(scope): description"
            
        # Validate body
        if len(lines) > 1:
            if not lines[1] == '':
                return False, "Leave one blank line after subject"
                
            for line in lines[2:]:
                if len(line) > self.max_body_line_length:
                    return False, f"Body line too long: {line}"
                    
        return True, "Valid commit message" 