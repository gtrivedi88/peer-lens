"""
Base Structure and Format Rule
A base class that all specific structure rules will inherit from.
This ensures a consistent interface for all rules.
"""

from typing import List, Dict, Any

# A generic base rule to be inherited from a central location
# in a real application. The # type: ignore comments prevent the
# static type checker from getting confused by the fallback class.
try:
    from ..base_rule import BaseRule  # type: ignore
except ImportError:
    class BaseRule:  # type: ignore
        def _get_rule_type(self) -> str:
            return 'base'
        def _create_error(self, **kwargs) -> Dict[str, Any]:
            return kwargs


class BaseStructureRule(BaseRule):
    """
    Abstract base class for all structure and format rules.
    It defines the common interface for analyzing text.
    """

    def analyze(self, text: str, sentences: List[str], nlp=None, context=None) -> List[Dict[str, Any]]:
        """
        Analyzes the text for a specific structure or format violation.
        This method must be implemented by all subclasses.
        """
        raise NotImplementedError("Subclasses must implement the analyze method.")
