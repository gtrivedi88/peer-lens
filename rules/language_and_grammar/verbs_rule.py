"""
Verbs Rule (Refactored to use Shared Passive Voice Analyzer)
Based on IBM Style Guide topics: "Verbs: Tense", "Verbs: Voice"

This refactored version uses the centralized PassiveVoiceAnalyzer to eliminate
code duplication while maintaining sophisticated context-aware suggestions.
"""
from typing import List, Dict, Any

try:
    from .base_language_rule import BaseLanguageRule
except ImportError:
    # Fallback for direct execution
    try:
        from base_language_rule import BaseLanguageRule
    except ImportError:
        # Define a minimal BaseLanguageRule for testing
        class BaseLanguageRule:
            def __init__(self):
                pass
            def _create_error(self, **kwargs):
                return kwargs

try:
    from .passive_voice_analyzer import PassiveVoiceAnalyzer, ContextType
except ImportError:
    # Fallback for direct execution
    try:
        from passive_voice_analyzer import PassiveVoiceAnalyzer, ContextType
    except ImportError:
        PassiveVoiceAnalyzer = None
        ContextType = None

try:
    from spacy.tokens import Doc, Token
except ImportError:
    Doc = None
    Token = None

class VerbsRule(BaseLanguageRule):
    """
    Checks for verb-related style issues using centralized passive voice analysis.
    Provides context-aware suggestions for descriptive vs instructional text.
    """
    
    def __init__(self):
        super().__init__()
        if PassiveVoiceAnalyzer:
            self.passive_analyzer = PassiveVoiceAnalyzer()
        else:
            self.passive_analyzer = None
    
    def _get_rule_type(self) -> str:
        return 'verbs'

    def analyze(self, text: str, sentences: List[str], nlp=None, context=None) -> List[Dict[str, Any]]:
        errors = []
        if not nlp or not self.passive_analyzer:
            return errors

        for i, sent_text in enumerate(sentences):
            if not sent_text.strip():
                continue
            
            doc = nlp(sent_text)
            
            # --- PASSIVE VOICE ANALYSIS (using shared analyzer) ---
            passive_constructions = self.passive_analyzer.find_passive_constructions(doc)
            
            for construction in passive_constructions:
                # Enhanced context classification
                context_type = self.passive_analyzer.classify_context(construction, doc)
                construction.context_type = context_type
                
                # Only flag passive voice in inappropriate contexts
                # Skip legitimate descriptive uses in technical documentation
                if context_type == ContextType.DESCRIPTIVE:
                    # Skip descriptive passive voice (e.g., "parameter was configured")
                    continue
                
                # Generate context-aware suggestions
                suggestions = self._generate_context_aware_suggestions(construction, doc, sent_text)
                
                errors.append(self._create_error(
                    sentence=sent_text,
                    sentence_index=i,
                    message="Sentence may be in the passive voice.",
                    suggestions=suggestions,
                    severity='medium',
                    span=(construction.span_start, construction.span_end),
                    flagged_text=construction.flagged_text
                ))

            # --- FUTURE TENSE CHECK ('will') ---
            for token in doc:
                if token.lemma_.lower() == "will" and token.tag_ == "MD":
                    head_verb = token.head
                    if head_verb.pos_ == "VERB":
                        suggestion = f"Use the present tense '{head_verb.lemma_}s' or the imperative mood '{head_verb.lemma_.capitalize()}'."
                        flagged_text = f"{token.text} {head_verb.text}"
                        span_start = token.idx
                        span_end = head_verb.idx + len(head_verb.text)
                        errors.append(self._create_error(
                            sentence=sent_text,
                            sentence_index=i,
                            message="Avoid future tense in procedural and descriptive text.",
                            suggestions=[suggestion],
                            severity='medium',
                            span=(span_start, span_end),
                            flagged_text=flagged_text
                        ))

            # --- PAST TENSE CHECK (with temporal context awareness) ---
            root_verb = self._find_root_token(doc)
            if (root_verb and root_verb.pos_ == 'VERB' and 'Tense=Past' in str(root_verb.morph) 
                and not self._is_passive_construction(root_verb, doc)):
                
                # ENHANCED: Skip past tense flagging when temporal context justifies it
                if self._has_legitimate_temporal_context(doc, sent_text):
                    continue
                
                flagged_text = root_verb.text
                span_start = root_verb.idx
                span_end = span_start + len(flagged_text)
                errors.append(self._create_error(
                    sentence=sent_text,
                    sentence_index=i,
                    message="Sentence may not be in the preferred present tense.",
                    suggestions=["Use present tense for instructions and system descriptions."],
                    severity='low',
                    span=(span_start, span_end),
                    flagged_text=flagged_text
                ))
        
        return errors

    def _generate_context_aware_suggestions(self, construction, doc: Doc, sentence: str) -> List[str]:
        """Generate intelligent suggestions based on context classification."""
        suggestions = []
        
        try:
            # Use the analyzer's context classification
            context_type = construction.context_type
            base_verb = construction.main_verb.lemma_
            passive_subject = construction.passive_subject
            
            # Find agent in by-phrase
            agent = self._find_agent_in_by_phrase(doc, construction.main_verb)
            
            # Check for negative context
            is_negative = self._has_negative_context(doc, construction.main_verb)
            
            if is_negative:
                # Handle negative constructions
                antonym = self._get_positive_alternative(base_verb, doc)
                if antonym:
                    if context_type == ContextType.DESCRIPTIVE:
                        suggestions.append(f"Rewrite positively: 'The system {antonym}s {passive_subject.text.lower()}' (use descriptive active voice)")
                    else:
                        suggestions.append(f"Rewrite positively: 'You must {antonym} {passive_subject.text.lower()}' (use positive action)")
                else:
                    suggestions.append(f"Rewrite as requirement: 'You must ensure {passive_subject.text.lower()} is {self._get_past_participle(base_verb)}' (specify the requirement)")
            
            elif context_type == ContextType.DESCRIPTIVE:
                # Generate descriptive suggestions
                self._add_descriptive_suggestions(suggestions, base_verb, passive_subject, agent, doc)
            
            elif context_type == ContextType.INSTRUCTIONAL:
                # Generate instructional suggestions
                self._add_instructional_suggestions(suggestions, base_verb, passive_subject, agent)
            
            else:
                # Uncertain context - provide both options
                suggestions.append(f"For descriptions: 'The system {self._conjugate_verb(base_verb, 'system')} {passive_subject.text.lower()}'")
                suggestions.append(f"For instructions: '{base_verb.capitalize()} the {passive_subject.text.lower()}'")
            
            # Add agent-based suggestion if available
            if agent and len(suggestions) < 2:
                verb_form = self._conjugate_verb(base_verb, agent)
                suggestions.append(f"Make the agent active: '{agent.capitalize()} {verb_form} {passive_subject.text.lower()}'")
            
            # Fallback
            if not suggestions:
                suggestions.append("Rewrite in active voice by identifying who or what performs the action")
                
        except Exception as e:
            suggestions = ["Rewrite in active voice by identifying who or what performs the action"]
        
        return suggestions[:3]

    def _add_descriptive_suggestions(self, suggestions: List[str], base_verb: str, 
                                   passive_subject: Token, agent: str, doc: Doc) -> None:
        """Add suggestions appropriate for descriptive context."""
        
        # Get appropriate actors for descriptive active voice
        descriptive_actors = self._get_descriptive_actors(base_verb, passive_subject, doc)
        
        for actor in descriptive_actors:
            # Check for same-root awkwardness and use alternative verb if needed
            final_verb = self._get_stylistically_appropriate_verb(base_verb, actor)
            verb_form = self._conjugate_verb(final_verb, actor)
            
            if passive_subject and passive_subject.text.lower() in ['it', 'this', 'that']:
                suggestions.append(f"Use descriptive active voice: '{actor.capitalize()} {verb_form} {passive_subject.text.lower()}'")
            else:
                suggestions.append(f"Use descriptive active voice: '{actor.capitalize()} {verb_form} the {passive_subject.text.lower()}'")
            
            if len(suggestions) >= 2:
                break
        
        # Fallback descriptive suggestion
        if not suggestions:
            if base_verb in ['document', 'describe', 'specify', 'define']:
                # Avoid same-root awkwardness in fallback too
                fallback_verb = self._get_stylistically_appropriate_verb(base_verb, 'the documentation')
                suggestions.append(f"Use descriptive active voice: 'The documentation {self._conjugate_verb(fallback_verb, 'documentation')} {passive_subject.text.lower()}'")
            else:
                suggestions.append(f"Use descriptive active voice: 'The system {self._conjugate_verb(base_verb, 'system')} {passive_subject.text.lower()}'")

    def _get_stylistically_appropriate_verb(self, base_verb: str, actor: str) -> str:
        """
        Return a stylistically appropriate verb, avoiding same-root awkwardness.
        
        E.g., avoid "documentation documents" -> use "documentation describes"
        """
        # Extract the root noun from the actor
        actor_root = actor.replace('the ', '').replace('a ', '').replace('an ', '')
        
        # Check if actor root and verb lemma are too similar (same-root awkwardness)
        if self._is_same_root_awkward(actor_root, base_verb):
            # Use alternative verbs for common cases (avoid multi-word verbs for now)
            verb_alternatives = {
                'document': 'describe',
                'describe': 'detail', 
                'specify': 'define',
                'define': 'outline',
                'configure': 'establish',
                'manage': 'handle',
                'process': 'handle',
                'support': 'enable'
            }
            
            alternative = verb_alternatives.get(base_verb)
            if alternative:
                return alternative
        
        return base_verb
    
    def _is_same_root_awkward(self, actor_root: str, verb: str) -> bool:
        """Check if using actor + verb creates awkward same-root construction."""
        # Handle obvious cases
        same_root_pairs = {
            ('documentation', 'document'),
            ('configuration', 'configure'), 
            ('specification', 'specify'),
            ('management', 'manage'),
            ('processing', 'process'),
            ('support', 'support')
        }
        
        return (actor_root, verb) in same_root_pairs or actor_root.startswith(verb) or verb.startswith(actor_root)

    def _add_instructional_suggestions(self, suggestions: List[str], base_verb: str, 
                                     passive_subject: Token, agent: str) -> None:
        """Add suggestions appropriate for instructional context."""
        
        # Use imperative mood for instructions
        if passive_subject and passive_subject.text.lower() in ['it', 'this', 'that']:
            suggestions.append(f"Use imperative: '{base_verb.capitalize()} {passive_subject.text.lower()}' (make the user the actor)")
        else:
            suggestions.append(f"Use imperative: '{base_verb.capitalize()} the {passive_subject.text.lower()}' (make the user the actor)")
        
        # Suggest specific actors for technical instructions
        if base_verb in ['configure', 'install', 'setup', 'deploy', 'enable', 'disable']:
            suggestions.append(f"Specify the actor: 'The administrator {self._conjugate_verb(base_verb, 'administrator')} the {passive_subject.text.lower()}'")
        elif base_verb in ['test', 'verify', 'check', 'validate']:
            suggestions.append(f"Specify the actor: 'You {base_verb} the {passive_subject.text.lower()}'")

    def _get_descriptive_actors(self, base_verb: str, passive_subject: Token, doc: Doc) -> List[str]:
        """Get appropriate actors for descriptive active voice."""
        
        # Use the analyzer's verb categorization
        verb_actors = {
            'document': ['the documentation', 'the manual', 'the guide'],
            'describe': ['the documentation', 'the specification', 'the manual'],
            'specify': ['the configuration', 'the settings', 'the parameters'],
            'define': ['the system', 'the configuration', 'the specification'],
            'configure': ['the system', 'the application', 'the software'],
            'provide': ['the system', 'the platform', 'the service'],
            'support': ['the system', 'the platform', 'the framework'],
            'manage': ['the system', 'the application', 'the service']
        }
        
        actors = verb_actors.get(base_verb, ['the system', 'the application'])
        
        # Context-based refinement using spaCy analysis
        context_words = [token.lemma_.lower() for token in doc]
        
        if any(word in context_words for word in ['database', 'data', 'record']):
            if base_verb in ['store', 'save', 'retrieve']:
                actors = ['the database', 'the data store'] + actors
        
        return actors[:2]

    # Utility methods (simplified from original)
    def _find_root_token(self, doc: Doc) -> Token:
        """Find the root token of the sentence."""
        for token in doc:
            if token.dep_ == "ROOT":
                return token
        return None

    def _is_passive_construction(self, verb_token: Token, doc: Doc) -> bool:
        """Check if a verb token is part of a passive voice construction."""
        if not verb_token:
            return False
        
        # Use analyzer for consistency
        constructions = self.passive_analyzer.find_passive_constructions(doc)
        return any(c.main_verb == verb_token for c in constructions)

    def _find_agent_in_by_phrase(self, doc: Doc, main_verb: Token) -> str:
        """Find the agent in a 'by' phrase."""
        for token in doc:
            if token.lemma_ == 'by' and token.head == main_verb:
                for child in token.children:
                    if child.dep_ == 'pobj':
                        return child.text
        return None

    def _has_negative_context(self, doc: Doc, main_verb: Token) -> bool:
        """Check if the passive construction is in a negative context."""
        for token in doc:
            if token.dep_ == 'neg' or token.lemma_ in ['not', 'never', 'cannot']:
                if token.head == main_verb or token.head.head == main_verb:
                    return True
        
        sentence_text = doc.text.lower()
        negative_patterns = ['can not be', 'cannot be', 'should not be', 'must not be']
        return any(pattern in sentence_text for pattern in negative_patterns)

    def _get_positive_alternative(self, verb_lemma: str, doc: Doc) -> str:
        """Get a positive alternative for a negated verb."""
        verb_alternatives = {
            'overlook': 'address', 'ignore': 'consider', 'miss': 'include',
            'skip': 'complete', 'avoid': 'ensure', 'neglect': 'maintain'
        }
        return verb_alternatives.get(verb_lemma)

    def _get_past_participle(self, verb_lemma: str) -> str:
        """Get the past participle form of a verb."""
        irregular_participles = {
            'configure': 'configured', 'install': 'installed', 'deploy': 'deployed',
            'address': 'addressed', 'consider': 'considered', 'include': 'included'
        }
        
        if verb_lemma in irregular_participles:
            return irregular_participles[verb_lemma]
        
        # Regular formation
        if verb_lemma.endswith('e'):
            return verb_lemma + 'd'
        else:
            return verb_lemma + 'ed'

    def _conjugate_verb(self, verb_lemma: str, subject: str) -> str:
        """Enhanced verb conjugation for both singular and descriptive subjects."""
        
        if subject.startswith('the '):
            subject_noun = subject[4:]
        else:
            subject_noun = subject.lower()
        
        third_person_singular = {
            'system', 'server', 'application', 'service', 'documentation', 'manual', 
            'configuration', 'database', 'interface', 'platform', 'framework'
        }
        
        if subject_noun in third_person_singular:
            if verb_lemma.endswith('e'):
                return verb_lemma + 's'
            elif verb_lemma.endswith(('s', 'sh', 'ch', 'x', 'z')):
                return verb_lemma + 'es'
            elif verb_lemma.endswith('y') and len(verb_lemma) > 1 and verb_lemma[-2] not in 'aeiou':
                return verb_lemma[:-1] + 'ies'
            else:
                return verb_lemma + 's'
        else:
            return verb_lemma

    def _has_legitimate_temporal_context(self, doc, sentence: str) -> bool:
        """
        Detect when past tense is legitimately appropriate due to temporal context.
        
        Past tense is appropriate for:
        - Historical descriptions ("Before this update...")
        - Bug reports and issue descriptions  
        - Release notes and change descriptions
        - Temporal comparisons ("Previously...")
        """
        sentence_lower = sentence.lower()
        
        # Temporal indicators that justify past tense
        temporal_indicators = {
            # Version/update context
            'before this update', 'before the update', 'prior to this update',
            'before this release', 'before the release', 'in previous versions',
            'in earlier versions', 'previously', 'formerly', 'originally',
            
            # Issue/bug context  
            'this issue occurred', 'this condition occurred', 'this problem occurred',
            'the issue was', 'the problem was', 'the bug was', 'the error was',
            'users experienced', 'this caused', 'this resulted in',
            
            # Historical context
            'in the past', 'historically', 'before the fix', 'before the change',
            'until now', 'until this version', 'up until', 'prior to',
            
            # Specific temporal phrases
            'this condition occurred', 'the service could not', 'users could not',
            'the system was unable', 'it was not possible', 'this failed to'
        }
        
        # Check for explicit temporal indicators
        for indicator in temporal_indicators:
            if indicator in sentence_lower:
                return True
        
        # Pattern detection using spaCy for more sophisticated analysis
        temporal_patterns = self._detect_temporal_patterns(doc)
        if temporal_patterns:
            return True
        
        # Context clues from document structure (if available)
        context_clues = self._detect_release_notes_context(sentence_lower)
        if context_clues:
            return True
        
        return False
    
    def _detect_temporal_patterns(self, doc) -> bool:
        """Use spaCy to detect temporal patterns that justify past tense."""
        
        # Look for temporal prepositions at sentence start
        if len(doc) > 0:
            first_token = doc[0]
            temporal_prepositions = {'before', 'after', 'during', 'until', 'since', 'when'}
            if first_token.lemma_.lower() in temporal_prepositions:
                return True
        
        # Look for temporal nouns/phrases
        temporal_nouns = {'update', 'release', 'version', 'fix', 'change', 'modification'}
        for token in doc:
            if (token.lemma_.lower() in temporal_nouns and 
                any(child.text.lower() in {'this', 'the', 'previous', 'earlier'} 
                    for child in token.children)):
                return True
        
        # Look for modal past constructions indicating capability/possibility
        for token in doc:
            if (token.lemma_.lower() in {'could', 'would', 'might'} and 
                token.tag_ == 'MD'):
                # Check if this is describing a past limitation/capability
                head_verb = token.head
                if head_verb and head_verb.lemma_.lower() in {'reload', 'access', 'load', 'connect', 'process'}:
                    # Check for negative context
                    if any(child.lemma_.lower() == 'not' for child in token.children):
                        return True
        
        return False
    
    def _detect_release_notes_context(self, sentence_lower: str) -> bool:
        """Detect if this appears to be release notes or changelog context."""
        
        release_notes_indicators = {
            'fixed', 'resolved', 'addressed', 'corrected', 'improved',
            'enhanced', 'updated', 'modified', 'changed', 'added', 'removed',
            'introduced', 'deprecated', 'replaced', 'migrated'
        }
        
        issue_description_patterns = {
            'failed to', 'unable to', 'could not', 'did not', 'would not',
            'was not', 'were not', 'caused', 'resulted in', 'led to'
        }
        
        # Check for release notes language
        for indicator in release_notes_indicators:
            if indicator in sentence_lower:
                return True
        
        # Check for issue description patterns
        for pattern in issue_description_patterns:
            if pattern in sentence_lower:
                return True
        
        return False
