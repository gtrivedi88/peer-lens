"""
Word Usage Rule for words starting with 'P'.
Enhanced with spaCy PhraseMatcher for efficient pattern detection.
"""
from typing import List, Dict, Any
from .base_word_usage_rule import BaseWordUsageRule

try:
    from spacy.tokens import Doc
except ImportError:
    Doc = None

class PWordsRule(BaseWordUsageRule):
    """
    Checks for the incorrect usage of specific words starting with 'P'.
    Enhanced with spaCy PhraseMatcher for efficient detection.
    """
    def _get_rule_type(self) -> str:
        return 'word_usage_p'
    
    def _setup_patterns(self, nlp):
        """Initialize spaCy PhraseMatcher with P-word patterns."""
        # Define word details for 'P' words
        word_details = {
            "pain point": {"suggestion": "Avoid jargon. Use 'challenge', 'issue', or 'problem'.", "severity": "medium"},
            "pane": {"suggestion": "Use specifically for a framed section of a window. Do not use interchangeably with 'panel' or 'window'.", "severity": "low"},
            "partner": {"suggestion": "Avoid generic use. Use 'IBM Business Partner' when appropriate.", "severity": "medium"},
            "path name": {"suggestion": "Write as 'pathname' (one word).", "severity": "low"},
            "PDF": {"suggestion": "Do not use as a noun. Use 'PDF file' or 'PDF document'.", "severity": "medium"},
            "per": {"suggestion": "Avoid. Use 'according to' or rewrite the sentence.", "severity": "low"},
            "perform": {"suggestion": "Avoid if a more direct verb like 'run' or 'install' is possible.", "severity": "low"},
            "please": {"suggestion": "Avoid in technical information; it can be inappropriate in some cultures.", "severity": "medium"},
            "plug-in": {"suggestion": "Write as 'plugin' (one word).", "severity": "low"},
            "pop up": {"suggestion": "Use 'pop-up' (hyphenated) as an adjective, not a verb.", "severity": "low"},
            "power up": {"suggestion": "Use 'power on' or 'turn on'.", "severity": "medium"},
            "practise": {"suggestion": "Use the spelling 'practice'.", "severity": "low"},
            "preinstall": {"suggestion": "Write as 'preinstall' (one word).", "severity": "low"},
            "prior to": {"suggestion": "Use 'before'.", "severity": "low"},
            "program product": {"suggestion": "Use 'licensed program'.", "severity": "medium"},
            "punch": {"suggestion": "Do not use for keyboard actions. Use 'press' or 'type'.", "severity": "high"},
        }
        
        # Use base class method to setup patterns
        self._setup_word_patterns(nlp, word_details)

    def analyze(self, text: str, sentences: List[str], nlp=None, context=None) -> List[Dict[str, Any]]:
        errors = []
        if not nlp:
            return errors
        doc = nlp(text)
        
        # Ensure patterns are initialized
        self._ensure_patterns_ready(nlp)

        # NEW ENHANCED APPROACH: Use base class PhraseMatcher functionality
        word_usage_errors = self._find_word_usage_errors(doc, "Review usage of the term")
        errors.extend(word_usage_errors)
        
        return errors
