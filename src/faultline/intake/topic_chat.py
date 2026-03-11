from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from faultline.llm.backend import StructuredReasoner
from faultline.models import (
    ChatIntakeSession,
    ChatIntakeTurn,
    PortfolioPosition,
    ResearchBrief,
    TopicPrompt,
    WatchlistEntry,
)

REQUIRED_FIELDS = [
    "analysis_goal",
    "geographic_scope",
    "time_horizon",
    "target_universe",
]


@dataclass(frozen=True)
class BriefQuestion:
    question_id: str
    field_name: str
    prompt: str
    reason: str


class _BriefDraft(ResearchBrief):
    interpretation: str = ""


class TopicChatIntake:
    def __init__(self, *, reasoner: StructuredReasoner | None = None) -> None:
        self.reasoner = reasoner or StructuredReasoner()

    def start_session(
        self,
        topic: str,
        *,
        thesis: str | None = None,
        portfolio_positions: list[PortfolioPosition | dict] | None = None,
        watchlist: list[WatchlistEntry | dict] | None = None,
    ) -> ChatIntakeSession:
        prompt = TopicPrompt(topic=topic.strip(), thesis=thesis.strip() if thesis else None)
        fallback = self._heuristic_brief(prompt)
        fallback.positions = [
            item if isinstance(item, PortfolioPosition) else PortfolioPosition.model_validate(item)
            for item in (portfolio_positions or [])
        ]
        fallback.watchlist = [
            item if isinstance(item, WatchlistEntry) else WatchlistEntry.model_validate(item)
            for item in (watchlist or [])
        ]
        candidate, _diagnostics = self.reasoner.refine_model(
            system_prompt=(
                "Convert the user topic into a research brief for a market-linked deep dive. "
                "Keep missing fields blank. Use concise, literal values. "
                "Do not mark the brief ready unless the user's prompt already makes the field explicit."
            ),
            user_payload={
                "topic": prompt.topic,
                "thesis": prompt.thesis,
                "portfolio_positions": [item.model_dump(mode="json") for item in fallback.positions],
                "watchlist": [item.model_dump(mode="json") for item in fallback.watchlist],
            },
            model_class=_BriefDraft,
            fallback=_BriefDraft.model_validate(fallback.model_dump()),
        )
        brief = ResearchBrief.model_validate(candidate.model_dump())
        interpretation = candidate.interpretation or self.describe_brief(brief)
        return self._finalize_session(
            ChatIntakeSession(
                topic_prompt=prompt,
                brief=brief,
                interpretation=interpretation,
            )
        )

    def answer_question(
        self,
        session: ChatIntakeSession | dict[str, Any],
        answer: str,
    ) -> ChatIntakeSession:
        current = session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
        if not current.current_question_id or not current.current_field:
            return current

        normalized = answer.strip()
        current.turns.append(
            ChatIntakeTurn(
                question_id=current.current_question_id,
                system_question=current.current_question or "",
                user_answer=normalized,
                field_updated=current.current_field,
                confidence=0.78 if normalized else 0.0,
                reason=f"Updated {current.current_field} from user clarification.",
            )
        )
        self._apply_answer(current.brief, current.current_field, normalized)
        current.interpretation = self.describe_brief(current.brief)
        return self._finalize_session(current)

    def is_ready(self, session: ChatIntakeSession | dict[str, Any]) -> bool:
        current = session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
        return current.status == "ready"

    def next_question(self, session: ChatIntakeSession | dict[str, Any]) -> BriefQuestion | None:
        current = session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
        brief = current.brief
        if not brief.analysis_goal:
            return BriefQuestion(
                question_id="analysis_goal",
                field_name="analysis_goal",
                prompt="What should this deep dive optimize for: macro transmission, sector rotation, or listed companies and symbols?",
                reason="The analysis goal determines how the topic is translated into evidence and outputs.",
            )
        if not brief.geographic_scope:
            return BriefQuestion(
                question_id="geographic_scope",
                field_name="geographic_scope",
                prompt="Which regions or markets matter most for this topic?",
                reason="The workflow needs a concrete geographic scope before retrieval starts.",
            )
        if not brief.time_horizon:
            return BriefQuestion(
                question_id="time_horizon",
                field_name="time_horizon",
                prompt="What time horizon should this analysis focus on: days, weeks, or months?",
                reason="Timing changes both the evidence window and the scenario framing.",
            )
        if not brief.target_universe:
            return BriefQuestion(
                question_id="target_universe",
                field_name="target_universe",
                prompt="Should the output stay at macro and sectors, or identify specific listed companies, ETFs, and symbols?",
                reason="The target universe sets how far the market mapping should go.",
            )
        if (brief.positions or brief.watchlist) and brief.portfolio_focus == "broader_market":
            return BriefQuestion(
                question_id="portfolio_focus",
                field_name="portfolio_focus",
                prompt="Should I shape this deep dive around your positions/watchlist, or keep it broad market first?",
                reason="Exposure-aware output is optional and should be explicit when portfolio context exists.",
            )
        return None

    def build_retrieval_questions(self, brief: ResearchBrief | dict[str, Any]) -> list[str]:
        current = brief if isinstance(brief, ResearchBrief) else ResearchBrief.model_validate(brief)
        geography = current.geographic_scope or "global markets"
        horizon = current.time_horizon or "next several weeks"
        target = current.target_universe or "public markets"
        system = current.system_under_study or current.normalized_topic or current.original_topic
        questions = [
            (f"What are the latest confirmed developments on {system} affecting {geography} over the {horizon}?"),
            (
                f"Which first-order transmission channels from {system} matter most for {geography}, "
                "including energy, shipping, inflation, rates, and supply chains where relevant?"
            ),
            (
                f"Which sectors, ETFs, listed companies, or symbols in {target} are most likely to benefit or suffer "
                f"from {system}, and what evidence supports each link?"
            ),
        ]
        if current.analysis_goal == "macro_transmission":
            questions.append(
                f"What second-order macro effects from {system} could emerge in {geography} beyond the obvious first-order shock?"
            )
        if current.portfolio_focus != "broader_market" and (current.positions or current.watchlist):
            watched = [item.symbol for item in [*current.positions, *current.watchlist][:6]]
            questions.append(f"How does {system} affect these listed exposures: {', '.join(watched)}?")
        return questions

    def default_window(self) -> tuple[datetime, datetime]:
        end_at = datetime.now(UTC)
        return end_at - timedelta(days=7), end_at

    def describe_brief(self, brief: ResearchBrief | dict[str, Any]) -> str:
        current = brief if isinstance(brief, ResearchBrief) else ResearchBrief.model_validate(brief)
        topic = current.system_under_study or current.normalized_topic or current.original_topic
        goal = current.analysis_goal or "an unresolved deep-dive objective"
        geography = current.geographic_scope or "an unspecified market scope"
        horizon = current.time_horizon or "an unspecified time horizon"
        target = current.target_universe or "an unspecified target universe"
        return f"Deep dive on {topic} focused on {goal}, scoped to {geography}, over {horizon}, targeting {target}."

    def _finalize_session(self, session: ChatIntakeSession) -> ChatIntakeSession:
        session.brief.missing_fields = [field for field in REQUIRED_FIELDS if not getattr(session.brief, field, "")]
        follow_up = self.next_question(session)
        session.status = "ready" if follow_up is None else "exploring"
        session.current_question_id = follow_up.question_id if follow_up else None
        session.current_question = follow_up.prompt if follow_up else None
        session.current_field = follow_up.field_name if follow_up else None
        session.interpretation = self.describe_brief(session.brief)
        return session

    def _heuristic_brief(self, prompt: TopicPrompt) -> ResearchBrief:
        text = " ".join(part for part in [prompt.topic, prompt.thesis or ""] if part).strip()
        normalized_topic = self._normalize_topic(text)
        system_under_study = normalized_topic or prompt.topic.strip()
        analysis_goal = self._detect_analysis_goal(text)
        geographic_scope = self._detect_geography(text)
        time_horizon = self._detect_horizon(text)
        target_universe = self._detect_target_universe(text)
        assumptions: list[str] = []
        if target_universe and "listed" not in text.lower() and "symbol" not in text.lower():
            assumptions.append("Defaulted the target universe to public markets based on project posture.")
        return ResearchBrief(
            original_topic=prompt.topic,
            normalized_topic=normalized_topic,
            system_under_study=system_under_study,
            analysis_goal=analysis_goal,
            geographic_scope=geographic_scope,
            time_horizon=time_horizon,
            target_universe=target_universe,
            assumptions=assumptions,
        )

    def _apply_answer(self, brief: ResearchBrief, field_name: str, answer: str) -> None:
        if field_name == "analysis_goal":
            brief.analysis_goal = self._canonical_analysis_goal(answer)
            return
        if field_name == "geographic_scope":
            brief.geographic_scope = answer
            return
        if field_name == "time_horizon":
            brief.time_horizon = self._canonical_horizon(answer)
            return
        if field_name == "target_universe":
            brief.target_universe = self._canonical_target_universe(answer)
            return
        if field_name == "portfolio_focus":
            lowered = answer.lower()
            if "watch" in lowered:
                brief.portfolio_focus = "watchlist"
            elif "position" in lowered or "portfolio" in lowered:
                brief.portfolio_focus = "portfolio"
            else:
                brief.portfolio_focus = "broader_market"

    def _normalize_topic(self, text: str) -> str:
        cleaned = re.sub(r"^(deep dive on|analyze|analyse|given|about)\s+", "", text.strip(), flags=re.I)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.")
        return cleaned

    def _detect_analysis_goal(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["inflation", "rates", "gdp", "econom", "macro"]):
            return "macro_transmission"
        if any(token in lowered for token in ["sector", "industry", "rotation", "theme"]):
            return "sector_rotation"
        if any(token in lowered for token in ["company", "companies", "listed", "symbol", "stock", "etf"]):
            return "listed_companies"
        return ""

    def _canonical_analysis_goal(self, answer: str) -> str:
        lowered = answer.lower()
        if "sector" in lowered:
            return "sector_rotation"
        if any(token in lowered for token in ["company", "symbol", "stock", "listed", "etf"]):
            return "listed_companies"
        return "macro_transmission"

    def _detect_geography(self, text: str) -> str:
        lowered = text.lower()
        geography_map = {
            "global": "Global",
            "world": "Global",
            "europe": "Europe",
            "european": "Europe",
            "united states": "United States",
            "us ": "United States",
            "u.s.": "United States",
            "china": "China",
            "middle east": "Middle East",
            "asia": "Asia",
        }
        for token, label in geography_map.items():
            if token in lowered:
                return label
        return ""

    def _detect_horizon(self, text: str) -> str:
        lowered = text.lower()
        if "day" in lowered:
            return "days"
        if "week" in lowered:
            return "weeks"
        month_match = re.search(r"(\d+)\s*month", lowered)
        if month_match:
            return f"{month_match.group(1)} months"
        if "month" in lowered:
            return "months"
        if "year" in lowered:
            return "12 months"
        return ""

    def _canonical_horizon(self, answer: str) -> str:
        lowered = answer.lower()
        if "day" in lowered:
            return "days"
        if "week" in lowered:
            return "weeks"
        month_match = re.search(r"(\d+)\s*month", lowered)
        if month_match:
            return f"{month_match.group(1)} months"
        if "month" in lowered:
            return "months"
        return answer.strip()

    def _detect_target_universe(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["watchlist", "portfolio", "position"]):
            return "watchlist_and_public_markets"
        if any(token in lowered for token in ["company", "companies", "listed", "symbol", "stock", "etf"]):
            return "listed_companies_and_etfs"
        if any(token in lowered for token in ["sector", "industry", "theme"]):
            return "sectors_and_themes"
        return ""

    def _canonical_target_universe(self, answer: str) -> str:
        lowered = answer.lower()
        if "sector" in lowered or "theme" in lowered:
            return "sectors_and_themes"
        if "watch" in lowered:
            return "watchlist_and_public_markets"
        if any(token in lowered for token in ["macro", "broad market"]):
            return "public_markets"
        return "listed_companies_and_etfs"
