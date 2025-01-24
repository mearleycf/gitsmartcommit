"""Tests for commit message validation."""
import pytest
from gitsmartcommit.commit_message.validation import (
    ValidationHandler,
    EmptyMessageHandler,
    SubjectLengthHandler,
    SubjectPeriodHandler,
    ConventionalFormatHandler,
    BlankLineHandler,
    BodyLineLengthHandler,
    create_validation_chain,
)

def test_empty_message_handler():
    handler = EmptyMessageHandler()
    
    # Test empty message
    is_valid, msg = handler.validate("")
    assert not is_valid
    assert "Empty commit message" in msg
    
    # Test whitespace-only message
    is_valid, msg = handler.validate("   \n  ")
    assert not is_valid
    assert "Empty commit message" in msg
    
    # Test valid message
    is_valid, msg = handler.validate("feat: add feature")
    assert is_valid

def test_subject_length_handler():
    handler = SubjectLengthHandler(max_length=10)
    
    # Test too long
    is_valid, msg = handler.validate("This is way too long")
    assert not is_valid
    assert "Subject line too long" in msg
    
    # Test exactly max length
    is_valid, msg = handler.validate("1234567890")
    assert is_valid
    
    # Test under max length
    is_valid, msg = handler.validate("short")
    assert is_valid

def test_subject_period_handler():
    handler = SubjectPeriodHandler()
    
    # Test with period
    is_valid, msg = handler.validate("feat: add feature.")
    assert not is_valid
    assert "should not end with a period" in msg
    
    # Test without period
    is_valid, msg = handler.validate("feat: add feature")
    assert is_valid

def test_conventional_format_handler():
    handler = ConventionalFormatHandler()
    
    # Test without colon
    is_valid, msg = handler.validate("bad format")
    assert not is_valid
    assert "must follow format" in msg
    
    # Test with colon
    is_valid, msg = handler.validate("feat: good format")
    assert is_valid

def test_blank_line_handler():
    handler = BlankLineHandler()
    
    # Test without blank line
    is_valid, msg = handler.validate("feat: add feature\nNo blank line")
    assert not is_valid
    assert "blank line after subject" in msg
    
    # Test with blank line
    is_valid, msg = handler.validate("feat: add feature\n\nWith blank line")
    assert is_valid
    
    # Test single line
    is_valid, msg = handler.validate("feat: add feature")
    assert is_valid

def test_body_line_length_handler():
    handler = BodyLineLengthHandler(max_length=10)
    
    # Test too long body line
    is_valid, msg = handler.validate("feat: add\n\nThis line is way too long")
    assert not is_valid
    assert "Body line too long" in msg
    
    # Test valid body lines
    is_valid, msg = handler.validate("feat: add\n\nShort\nAlso short")
    assert is_valid

def test_validation_chain():
    chain = create_validation_chain(max_subject_length=50, max_body_length=72)
    
    # Test valid conventional commit
    is_valid, msg = chain.handle(
        "feat(scope): add new feature\n\n"
        "This is a valid commit message with a proper body that\n"
        "explains the changes in detail."
    )
    assert is_valid
    
    # Test multiple validation failures
    is_valid, msg = chain.handle(
        "this is a very long subject line that will definitely exceed the maximum length.\n"
        "no blank line\n"
        "This is an extremely long body line that will definitely exceed the maximum length limit we have set."
    )
    assert not is_valid
    assert "Subject line too long" in msg  # Should fail at first violation

def test_chain_order():
    """Test that validations happen in the correct order."""
    # Create a chain that will fail at different points
    chain = create_validation_chain()
    
    # Should fail at empty message
    is_valid, msg = chain.handle("")
    assert not is_valid
    assert "Empty commit message" in msg
    
    # Should fail at subject length
    is_valid, msg = chain.handle("x" * 51)
    assert not is_valid
    assert "Subject line too long" in msg
    
    # Should fail at conventional format
    is_valid, msg = chain.handle("invalid format")
    assert not is_valid
    assert "must follow format" in msg
    
    # Should fail at blank line
    is_valid, msg = chain.handle("feat: valid\nno blank line")
    assert not is_valid
    assert "blank line after subject" in msg 