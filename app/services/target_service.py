"""
Target management service.

Handles creation with two-stage matching (normalization + LLM),
listing, and CRUD operations. No user association — targets are
global resources accessible to all.

Matching pipeline:
1. Fast normalization match (exact match on normalized name).
2. LLM semantic match (AI-powered entity resolution).
3. Create new target if no match found.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.normalization import normalize_target_name, display_name_from_input
from app.core.exceptions import NotFoundException
from app.models.target import Target
from app.models.enums import TargetType, ScanDepth

logger = logging.getLogger("media_intel.target_service")


class TargetService:
    """
    Target CRUD with two-stage matching.

    Stage 1 — Normalization:
        'John Doe', 'john doe', 'JOHN DOE' all resolve to the same target.

    Stage 2 — LLM Matching:
        'Apple' matches 'Apple Inc', 'MSFT' matches 'Microsoft Corporation'.
        Only triggered if normalization finds no match.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_or_get_target(
        self,
        name: str,
        target_type: TargetType = TargetType.person,
        description: Optional[str] = None,
    ) -> tuple[Target, bool, dict]:
        """
        Create a new target or return an existing matched one.

        Two-stage matching pipeline:
        1. Normalization: exact match on normalized_name.
        2. LLM: semantic match against existing targets (if enabled).
        3. Create new target if no match found.

        Args:
            name: Raw target name from user input.
            target_type: Classification of the target.
            description: Optional context.

        Returns:
            Tuple of (Target, is_new, match_info).
            match_info contains: matched_by, confidence, reasoning.
        """
        display = display_name_from_input(name)
        normalized = normalize_target_name(name)

        if not normalized:
            from app.core.exceptions import ValidationException
            raise ValidationException("Target name is empty after normalization")

        match_info = {}

        # ── Stage 1: Normalization match (fast, free) ──
        result = await self.db.execute(
            select(Target).where(
                Target.normalized_name == normalized,
                Target.is_active == True,
            )
        )
        existing_target = result.scalar_one_or_none()

        if existing_target:
            match_info = {"matched_by": "normalization"}
            logger.info(
                f"Target matched by normalization: '{display}' → "
                f"'{existing_target.display_name}' (id={existing_target.id})",
                extra={"action": "target_match_norm", "target_id": str(existing_target.id)},
            )
            return existing_target, False, match_info

        # ── Stage 2: LLM semantic match (smart, costs tokens) ──
        if self.settings.ENABLE_LLM_TARGET_MATCHING and self.settings.OPENAI_API_KEY:
            llm_match, llm_info = await self._llm_match_target(
                name=display,
                target_type=target_type,
                description=description,
            )
            if llm_match:
                match_info = {
                    "matched_by": "llm",
                    "confidence": llm_info.get("confidence", 0),
                    "reasoning": llm_info.get("reasoning", ""),
                }
                logger.info(
                    f"Target matched by LLM: '{display}' → "
                    f"'{llm_match.display_name}' "
                    f"(confidence={llm_info.get('confidence', 0):.0%})",
                    extra={
                        "action": "target_match_llm",
                        "target_id": str(llm_match.id),
                        "confidence": llm_info.get("confidence", 0),
                    },
                )
                return llm_match, False, match_info

        # ── Stage 3: Create new target ──
        target = Target(
            display_name=display,
            normalized_name=normalized,
            target_type=target_type,
            description=description,
            is_active=True,
        )
        self.db.add(target)
        await self.db.commit()
        await self.db.refresh(target)

        match_info = {"matched_by": None}
        logger.info(
            f"New target created: '{display}' → '{normalized}' (id={target.id})",
            extra={"action": "target_create", "target_id": str(target.id)},
        )
        return target, True, match_info

    async def get_target_by_id(self, target_id: UUID) -> Target:
        """
        Get a target by UUID.

        Args:
            target_id: The target's UUID.

        Returns:
            The Target object.

        Raises:
            NotFoundException: If not found.
        """
        result = await self.db.execute(
            select(Target).where(Target.id == target_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise NotFoundException("Target", str(target_id))
        return target

    async def list_targets(
        self,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True,
    ) -> tuple[list[Target], int]:
        """
        List all targets with pagination.

        Args:
            limit: Maximum number of targets to return.
            offset: Number of targets to skip.
            active_only: If True, only return active targets.

        Returns:
            Tuple of (list of Target objects, total count).
        """
        query = select(Target)
        count_query = select(func.count(Target.id))

        if active_only:
            query = query.where(Target.is_active == True)
            count_query = count_query.where(Target.is_active == True)

        query = query.order_by(Target.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        targets = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return targets, total

    async def update_target(
        self,
        target_id: UUID,
        display_name: Optional[str] = None,
        target_type: Optional[TargetType] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Target:
        """
        Update a target's fields.

        If display_name changes, normalized_name is recomputed and
        checked for uniqueness.

        Args:
            target_id: Target UUID.
            display_name: New display name (optional).
            target_type: New type (optional).
            description: New description (optional).
            is_active: New active status (optional).

        Returns:
            The updated Target object.

        Raises:
            NotFoundException: If target doesn't exist.
            DuplicateException: If new normalized name already exists.
        """
        target = await self.get_target_by_id(target_id)

        if display_name is not None:
            clean_display = display_name_from_input(display_name)
            new_normalized = normalize_target_name(display_name)

            if new_normalized != target.normalized_name:
                existing = await self.db.execute(
                    select(Target).where(Target.normalized_name == new_normalized)
                )
                if existing.scalar_one_or_none():
                    from app.core.exceptions import DuplicateException
                    raise DuplicateException(
                        message=f"A target with normalized name '{new_normalized}' already exists",
                    )

            target.display_name = clean_display
            target.normalized_name = new_normalized

        if target_type is not None:
            target.target_type = target_type
        if description is not None:
            target.description = description
        if is_active is not None:
            target.is_active = is_active

        await self.db.commit()
        await self.db.refresh(target)

        logger.info(
            f"Target updated: {target.display_name}",
            extra={"action": "target_update", "target_id": str(target.id)},
        )
        return target

    async def delete_target(self, target_id: UUID) -> Target:
        """
        Soft-delete a target by setting is_active to False.

        Args:
            target_id: Target UUID.

        Returns:
            The deactivated Target object.
        """
        target = await self.get_target_by_id(target_id)
        target.is_active = False
        await self.db.commit()
        await self.db.refresh(target)

        logger.info(
            f"Target deactivated: {target.display_name}",
            extra={"action": "target_delete", "target_id": str(target.id)},
        )
        return target

    async def _llm_match_target(
        self,
        name: str,
        target_type: TargetType,
        description: Optional[str] = None,
    ) -> tuple[Optional[Target], dict]:
        """
        Use LLM to match a target name against existing targets.

        Pre-filters candidates by word overlap to reduce cost,
        then sends top candidates to LLM for semantic matching.

        Args:
            name: The new target name.
            target_type: The new target's type.
            description: Optional description for context.

        Returns:
            Tuple of (matched Target or None, info dict).
        """
        result = await self.db.execute(
            select(Target).where(Target.is_active == True)
        )
        all_targets = list(result.scalars().all())

        if not all_targets:
            return None, {}

        candidates = self._prefilter_candidates(name, all_targets)

        if not candidates:
            return None, {}

        candidate_list = []
        for t in candidates[:self.settings.TARGET_MATCH_MAX_CANDIDATES]:
            candidate_list.append({
                "id": str(t.id),
                "name": t.display_name,
                "type": t.target_type.value,
                "description": (t.description or "")[:200],
            })

        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
            from app.agents.utils import extract_json

            model = ChatOpenAI(
                model=self.settings.LLM_MODEL,
                temperature=0,
                openai_api_key=self.settings.OPENAI_API_KEY,
            )

            system_prompt = (
                "You are an entity matching assistant. You determine whether a NEW target "
                "refers to the same real-world entity as any EXISTING target in a database.\n\n"
                "Rules:\n"
                "- Match if they clearly refer to the same entity "
                "(e.g., 'Apple' = 'Apple Inc', 'MSFT' = 'Microsoft Corporation', "
                "'Elon' = 'Elon Musk' if type is person)\n"
                "- Do NOT match different entities "
                "(e.g., 'Apple' the tech company ≠ 'Apple Records')\n"
                "- Consider the target_type and description for disambiguation\n"
                "- Be conservative — only match if genuinely confident\n"
                "- Return ONLY valid JSON, no markdown"
            )

            user_prompt = (
                f'NEW TARGET:\n'
                f'  Name: "{name}"\n'
                f'  Type: {target_type.value}\n'
                f'  Description: {description or "not provided"}\n\n'
                f'EXISTING TARGETS:\n'
                f'{json.dumps(candidate_list, indent=2)}\n\n'
                f'Does the new target match any existing target?\n\n'
                f'Return JSON:\n'
                f'{{\n'
                f'  "matched": true or false,\n'
                f'  "matched_target_id": "uuid string or null",\n'
                f'  "matched_target_name": "name or null",\n'
                f'  "confidence": 0.0 to 1.0,\n'
                f'  "reasoning": "brief explanation"\n'
                f'}}'
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await model.ainvoke(messages)
            result_data = extract_json(
                response.content if hasattr(response, "content") else ""
            )

            if not result_data or not isinstance(result_data, dict):
                logger.warning("LLM target matching returned invalid response")
                return None, {}

            if (
                result_data.get("matched")
                and result_data.get("confidence", 0) >= self.settings.TARGET_MATCH_THRESHOLD
            ):
                matched_id = result_data.get("matched_target_id")
                if matched_id:
                    for t in candidates:
                        if str(t.id) == matched_id:
                            return t, {
                                "confidence": result_data["confidence"],
                                "reasoning": result_data.get("reasoning", ""),
                                "matched_name": result_data.get("matched_target_name"),
                            }

            return None, {
                "confidence": result_data.get("confidence", 0),
                "reasoning": result_data.get("reasoning", "No confident match found"),
            }

        except Exception as e:
            logger.warning(f"LLM target matching failed: {e}")
            return None, {}

    def _prefilter_candidates(
        self, name: str, targets: list[Target]
    ) -> list[Target]:
        """Pre-filter targets by word overlap to reduce LLM calls."""
        if len(targets) <= self.settings.TARGET_MATCH_MAX_CANDIDATES:
            return targets

        name_lower = name.lower()
        name_words = set(w for w in name_lower.split() if len(w) > 2)

        scored = []
        for t in targets:
            target_words = set(
                w for w in t.display_name.lower().split() if len(w) > 2
            )
            norm_words = set(
                w for w in t.normalized_name.split() if len(w) > 2
            )
            all_target_words = target_words | norm_words
            overlap = len(name_words & all_target_words)
            substring_match = any(
                nw in t.display_name.lower() or t.display_name.lower() in name_lower
                for nw in name_words if len(nw) > 3
            )
            if overlap > 0 or substring_match:
                scored.append((overlap + (1 if substring_match else 0), t))

        scored.sort(key=lambda x: x[0], reverse=True)
        candidates = [t for _, t in scored]

        if not candidates:
            return targets[:self.settings.TARGET_MATCH_MAX_CANDIDATES]

        return candidates[:self.settings.TARGET_MATCH_MAX_CANDIDATES]
