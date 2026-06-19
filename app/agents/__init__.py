"""
Agents package — multi-agent architecture for media intelligence.

Agent Architecture:
- SearchAgent: Discovers articles via Firecrawl search + MCP tools.
- ScrapeAgent: Fetches full content from URLs via Firecrawl REST API.
- AnalysisAgent: LLM-powered sentiment, security, and risk analysis.
- ScanOrchestrator: Coordinates the full scan pipeline across agents.

Each agent is independent and stateless — the orchestrator manages
the data flow between them.
"""

from app.agents.orchestrator import ScanOrchestrator

__all__ = ["ScanOrchestrator"]
