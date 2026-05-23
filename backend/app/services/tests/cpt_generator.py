"""
Generator per Continuous Performance Test (CPT).

Strategia: l'LLM non è la scelta migliore per generare sequenze random
di lettere con vincoli numerici - è più efficiente generarle in Python.
Usiamo invece l'LLM solo per la scelta intelligente dei distrattori
(alfabeto effettivamente usato), e procedurale per la sequenza.
"""

import random
from typing import Type, List
from pydantic import BaseModel

from app.schemas.cpt import CPTConfig, CPTSequence, CPTStimulus
from app.services.tests.base import TestGenerator


class CPTGenerator(TestGenerator[CPTConfig, CPTSequence]):
    """Generator per Continuous Performance Test."""

    @property
    def test_name(self) -> str:
        return "CPT"

    @property
    def category(self) -> str:
        return "A"

    @property
    def output_schema(self) -> Type[CPTSequence]:
        return CPTSequence

    def default_temperature(self) -> float:
        return 0.2  # test con vincoli molto stretti

    def build_system_prompt(self, config: CPTConfig) -> str:
        return (
            "Sei un generatore di stimoli per test neuropsicologici validati clinicamente. "
            "Stai generando una sequenza per un Continuous Performance Test (CPT). "
            "Rispetta rigorosamente i vincoli statistici e l'ordine specificato. "
            "Restituisci SOLO il JSON conforme allo schema, senza spiegazioni."
        )

    def build_user_prompt(self, config: CPTConfig) -> str:
        n_stimuli = config.total_stimuli_count()
        distractors = [
            c for c in config.alphabet.upper()
            if c != config.target_letter.upper()
        ]

        return (
            f"Genera una sequenza CPT con questi parametri:\n"
            f"- target_letter: '{config.target_letter.upper()}'\n"
            f"- numero totale stimoli: {n_stimuli}\n"
            f"- rapporto target: {config.target_ratio} ({int(n_stimuli * config.target_ratio)} target circa)\n"
            f"- distrattori disponibili: {', '.join(distractors[:10])}...\n"
            f"- ISI minimo: {config.isi_min_ms} ms\n"
            f"- ISI massimo: {config.isi_max_ms} ms\n\n"
            f"Vincoli CRITICI:\n"
            f"1. MAI più di 3 target consecutivi\n"
            f"2. Distribuzione target pseudo-casuale (no pattern regolari tipo ogni 5 stimoli)\n"
            f"3. ISI variabili tra {config.isi_min_ms} e {config.isi_max_ms} ms\n"
            f"4. I distrattori devono essere scelti variamente (non solo 2-3 lettere)\n\n"
            f"Esempio di output atteso (piccola sequenza):\n"
            f'{{"target_letter":"X","stimuli":['
            f'{{"stimulus":"A","is_target":false,"isi_ms":1500}},'
            f'{{"stimulus":"X","is_target":true,"isi_ms":2000}},'
            f'{{"stimulus":"K","is_target":false,"isi_ms":1200}},'
            f'{{"stimulus":"M","is_target":false,"isi_ms":3500}}'
            f"]}}"
        )

    async def generate(self, config: CPTConfig) -> CPTSequence:
        """
        Override: per il CPT generiamo proceduralmente la sequenza.
        Gli LLM sono inefficaci nel generare sequenze casuali con vincoli numerici.
        """
        n_stimuli = config.total_stimuli_count()
        n_targets = int(n_stimuli * config.target_ratio)
        target = config.target_letter.upper()

        distractors = [
            c for c in config.alphabet.upper()
            if c != target
        ]

        # Posizioni dei target pseudo-casuali con vincolo max 3 consecutivi
        target_positions = self._generate_target_positions(n_stimuli, n_targets)

        stimuli = []
        for i in range(n_stimuli):
            is_target = i in target_positions
            letter = target if is_target else random.choice(distractors)
            isi = random.randint(config.isi_min_ms, config.isi_max_ms)

            stimuli.append(CPTStimulus(
                stimulus=letter,
                is_target=is_target,
                isi_ms=isi,
            ))

        return CPTSequence(target_letter=target, stimuli=stimuli)

    def _generate_target_positions(self, n_total: int, n_targets: int) -> set:
        """Genera posizioni pseudo-casuali per i target con vincoli."""
        positions = set()
        attempts = 0
        max_attempts = n_targets * 10

        while len(positions) < n_targets and attempts < max_attempts:
            pos = random.randint(0, n_total - 1)
            # Controllo: non più di 3 consecutivi
            if self._would_create_run(positions, pos):
                attempts += 1
                continue
            positions.add(pos)
            attempts += 1

        return positions

    def _would_create_run(self, positions: set, new_pos: int) -> bool:
        """Verifica se aggiungere new_pos creerebbe una run di 4+."""
        # Conta quanti target consecutivi si formerebbero attorno a new_pos
        run = 1
        # Espandi a sinistra
        i = new_pos - 1
        while i in positions:
            run += 1
            i -= 1
        # Espandi a destra
        i = new_pos + 1
        while i in positions:
            run += 1
            i += 1
        return run > 3
