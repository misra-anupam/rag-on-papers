import time

import structlog
from crewai import LLM, Agent, Crew, Process, Task

from modules.module7_agent.tools import multi_hop_retrieve_tool, retrieve_tool
from shared.config import settings
from shared.observability import agent_run_latency

log = structlog.get_logger()

_llm = LLM(
    model="openai/gpt-4o",
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.openrouter_api_key,
)

retrieval_agent = Agent(
    role="Medical Research Retrieval Specialist",
    goal="Find the most relevant, high-quality evidence from the research corpus.",
    backstory=(
        "Expert in medical literature search with deep knowledge of MeSH terms, "
        "study design, and biomedical terminology. Skilled at query rewriting "
        "and identifying when multi-hop reasoning is needed."
    ),
    tools=[retrieve_tool, multi_hop_retrieve_tool],
    llm=_llm,
    verbose=True,
    max_iter=5,
)

analysis_agent = Agent(
    role="Medical Evidence Analyst",
    goal="Critically assess retrieved evidence for relevance, quality, completeness.",
    backstory=(
        "Expert in evidence-based medicine and critical appraisal. "
        "Evaluates study design, sample size, and statistical significance. "
        "Identifies when retrieved evidence is insufficient and requests more."
    ),
    tools=[retrieve_tool],
    llm=_llm,
    verbose=True,
    max_iter=3,
)

synthesis_agent = Agent(
    role="Medical Research Synthesiser",
    goal="Produce accurate, fully-cited answers grounded in retrieved evidence.",
    backstory=(
        "Science communicator skilled at synthesising complex medical literature. "
        "Never makes claims beyond what the evidence supports. "
        "Always cites specific papers with DOI and section."
    ),
    tools=[],
    llm=_llm,
    verbose=True,
)


def run_query(user_query: str) -> str:
    retrieval_task = Task(
        description=(
            f'User question: "{user_query}"\n'
            "Rewrite into an optimal retrieval query. "
            "Select the best strategy (semantic|lexical|hybrid|tag) "
            "and any relevant MeSH term or date filters. "
            "Use multi_hop_retrieve_tool if the question requires "
            "chained reasoning across multiple topics."
        ),
        agent=retrieval_agent,
        expected_output="Retrieved chunks with DOI, section, and text.",
    )

    analysis_task = Task(
        description=(
            "Review all retrieved chunks. "
            "Assess each for relevance, study design, and evidence quality. "
            "If key information is missing, use retrieve_tool to fill gaps. "
            "Produce an annotated evidence summary."
        ),
        agent=analysis_agent,
        expected_output="Evidence summary with quality annotations.",
        context=[retrieval_task],
    )

    synthesis_task = Task(
        description=(
            f'Answer the original question: "{user_query}"\n'
            "Use only the retrieved evidence. "
            "Cite every claim as [DOI, Section]. "
            "If evidence is insufficient, state this explicitly."
        ),
        agent=synthesis_agent,
        expected_output="Final answer with inline citations.",
        context=[retrieval_task, analysis_task],
    )

    crew = Crew(
        agents=[retrieval_agent, analysis_agent, synthesis_agent],
        tasks=[retrieval_task, analysis_task, synthesis_task],
        process=Process.sequential,
        verbose=True,
    )

    t0 = time.perf_counter()
    result = crew.kickoff()
    agent_run_latency.observe(time.perf_counter() - t0)
    log.info("crew_completed", query=user_query, latency=time.perf_counter() - t0)
    return str(result)
