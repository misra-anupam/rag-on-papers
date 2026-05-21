from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from modules.module8_eval.retrieval_metrics import run_retrieval_and_rerank


def evaluate_strategy(test_set: list[dict], strategy: str) -> dict:
    from modules.module7_agent.crew import run_query

    rows = []
    for item in test_set:
        chunks = run_retrieval_and_rerank(item['query'], strategy=strategy)
        answer = run_query(item['query'])
        rows.append({
            'question':     item['query'],
            'answer':       answer,
            'contexts':     [c.payload.get('text', '') for c in chunks],
            'ground_truth': item.get('expected_answer', ''),
        })

    dataset = Dataset.from_list(rows)
    result  = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return dict(result)
