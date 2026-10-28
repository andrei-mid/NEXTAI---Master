"""STUB. Owner: @role-5-ai-api. Entity resolution over all agents' signals.

Implement `resolve`:
1. Dedupe: same signal_id -> keep one. The same fact from two sources (same rule_id + same
   data key) -> keep the official one, mention the other source in data["also_seen_in"].
2. Verify each signal refers to THIS company: cui_exact -> keep. name+county -> check
   county == identity.registered_office.county. name_fuzzy / person_name -> check against
   identity names + administrators.
3. Ambiguous matches: lower `confidence` (e.g. x0.5, configurable) and set entity_match.ambiguous=True.
   Clear non-matches are DROPPED and counted in AgentResult.notes.
4. Never change an AgentResult's status: entity resolution can't turn a failure into clean.
Returns new AgentResult objects (inputs are not mutated).
"""

from __future__ import annotations

from verifirm.schema.identity import IdentitySheet
from verifirm.schema.signals import AgentResult


def resolve(identity: IdentitySheet, results: list[AgentResult]) -> list[AgentResult]:
    raise NotImplementedError
