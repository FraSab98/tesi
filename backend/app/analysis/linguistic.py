"""
Analisi linguistica delle trascrizioni con spaCy.

Estrae feature stilometriche ispirate al Paper 11 (Barrios et al., 2025)
che ha dimostrato differenze significative nelle narrazioni di adolescenti
con ADHD rispetto ai controlli.

Feature estratte:
- Word count: numero totale di parole
- Lexical diversity (MATTR): variabilità del vocabolario
- Lexical density: proporzione di parole contenuto (nomi, verbi, aggettivi)
- Cohesion: frequenza di connettivi
- Syntactic complexity: profondità media dell'albero sintattico
- Function word distribution: distribuzione di pronomi, congiunzioni

Per italiano usa il modello: it_core_news_lg
Installa con: python -m spacy download it_core_news_lg
"""

import logging
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import spacy
    from spacy.language import Language
    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False
    Language = None


@dataclass
class LinguisticFeatures:
    """Feature linguistiche estratte da un testo."""
    word_count: int
    sentence_count: int
    mean_sentence_length: float
    lexical_diversity: float       # TTR (Type-Token Ratio)
    mattr: float                   # Moving-Average TTR (più robusto per testi di lunghezze diverse)
    lexical_density: float         # % parole contenuto
    cohesion: float                # % connettivi
    mean_syntactic_depth: float    # profondità media albero sintattico
    # Distribuzioni POS
    pos_distribution: dict = field(default_factory=dict)
    # Function words (utili come in Paper 11)
    function_word_freq: dict = field(default_factory=dict)
    # Pronomi specifici (Paper 11: "je" vs "on" in francese; "io" vs "si" in italiano)
    pronoun_distribution: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "mean_sentence_length": round(self.mean_sentence_length, 2),
            "lexical_diversity": round(self.lexical_diversity, 4),
            "mattr": round(self.mattr, 4),
            "lexical_density": round(self.lexical_density, 4),
            "cohesion": round(self.cohesion, 4),
            "mean_syntactic_depth": round(self.mean_syntactic_depth, 2),
            "pos_distribution": self.pos_distribution,
            "function_word_freq": dict(
                sorted(self.function_word_freq.items(),
                       key=lambda x: -x[1])[:20]
            ),  # top 20
            "pronoun_distribution": self.pronoun_distribution,
        }


class LinguisticAnalyzer:
    """Analizzatore linguistico basato su spaCy."""

    _nlp_cache: dict = {}

    # Categorie POS per calcoli
    CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "PROPN"}
    COHESION_POS = {"CCONJ", "SCONJ", "PRON", "DET", "ADP"}

    def __init__(self, model: str = "it_core_news_lg"):
        if not _SPACY_AVAILABLE:
            raise ImportError(
                "spaCy non installato. "
                "Installa con: pip install spacy && "
                "python -m spacy download it_core_news_lg"
            )
        self.model_name = model
        self._load_nlp()

    def _load_nlp(self):
        """Caching del modello spaCy."""
        if self.model_name not in LinguisticAnalyzer._nlp_cache:
            logger.info(f"Caricamento modello spaCy '{self.model_name}'")
            try:
                LinguisticAnalyzer._nlp_cache[self.model_name] = spacy.load(self.model_name)
            except OSError:
                raise OSError(
                    f"Modello spaCy '{self.model_name}' non trovato. "
                    f"Installa con: python -m spacy download {self.model_name}"
                )
        self.nlp = LinguisticAnalyzer._nlp_cache[self.model_name]

    def analyze(self, text: str) -> LinguisticFeatures:
        """Estrae tutte le feature linguistiche dal testo."""
        if not text or len(text.strip()) == 0:
            return self._empty_features()

        doc = self.nlp(text)

        # Tokens validi: escludi punteggiatura e spazi
        tokens = [t for t in doc if not t.is_punct and not t.is_space]

        if len(tokens) == 0:
            return self._empty_features()

        word_count = len(tokens)
        sentences = list(doc.sents)
        sentence_count = len(sentences)
        mean_sent_len = word_count / sentence_count if sentence_count else 0

        # Diversità lessicale (TTR semplice)
        unique_lemmas = {t.lemma_.lower() for t in tokens}
        ttr = len(unique_lemmas) / word_count

        # MATTR (finestra mobile di 50 token) - robusto a lunghezze diverse
        mattr = self._compute_mattr(tokens, window=50)

        # Densità lessicale
        content_tokens = [t for t in tokens if t.pos_ in self.CONTENT_POS]
        lexical_density = len(content_tokens) / word_count

        # Coesione (connettivi e determinanti)
        cohesion_tokens = [t for t in tokens if t.pos_ in self.COHESION_POS]
        cohesion = len(cohesion_tokens) / word_count

        # Profondità sintattica media
        mean_depth = self._mean_tree_depth(doc)

        # Distribuzione POS
        pos_counts = Counter(t.pos_ for t in tokens)
        pos_dist = {pos: count / word_count for pos, count in pos_counts.items()}

        # Function words (parole grammaticali)
        function_tokens = [
            t.text.lower() for t in tokens
            if t.pos_ in {"CCONJ", "SCONJ", "DET", "ADP", "PRON", "PART", "AUX"}
        ]
        function_freq = dict(Counter(function_tokens))

        # Pronomi (Paper 11: indicatori di prospettiva)
        pronoun_tokens = [t.text.lower() for t in tokens if t.pos_ == "PRON"]
        pronoun_dist = dict(Counter(pronoun_tokens))

        return LinguisticFeatures(
            word_count=word_count,
            sentence_count=sentence_count,
            mean_sentence_length=mean_sent_len,
            lexical_diversity=ttr,
            mattr=mattr,
            lexical_density=lexical_density,
            cohesion=cohesion,
            mean_syntactic_depth=mean_depth,
            pos_distribution=pos_dist,
            function_word_freq=function_freq,
            pronoun_distribution=pronoun_dist,
        )

    def _compute_mattr(self, tokens: list, window: int = 50) -> float:
        """Moving Average Type-Token Ratio (Covington & McFall 2010).

        Per testi brevi (< window) ritorna il TTR semplice.
        """
        if len(tokens) <= window:
            unique = {t.lemma_.lower() for t in tokens}
            return len(unique) / len(tokens) if tokens else 0.0

        ttrs = []
        for i in range(len(tokens) - window + 1):
            chunk = tokens[i:i + window]
            unique = {t.lemma_.lower() for t in chunk}
            ttrs.append(len(unique) / window)
        return sum(ttrs) / len(ttrs)

    def _mean_tree_depth(self, doc) -> float:
        """Profondità media dell'albero sintattico."""
        def depth(token):
            d = 0
            cur = token
            while cur.head != cur:
                d += 1
                cur = cur.head
                if d > 50:  # safety
                    break
            return d

        tokens = [t for t in doc if not t.is_punct and not t.is_space]
        if not tokens:
            return 0.0
        return sum(depth(t) for t in tokens) / len(tokens)

    @staticmethod
    def _empty_features() -> LinguisticFeatures:
        return LinguisticFeatures(
            word_count=0, sentence_count=0, mean_sentence_length=0.0,
            lexical_diversity=0.0, mattr=0.0, lexical_density=0.0,
            cohesion=0.0, mean_syntactic_depth=0.0,
        )
