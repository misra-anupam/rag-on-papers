import mlflow

from modules.module3_embed.dense import EMBEDDING_DIMS, EMBEDDING_MODEL
from modules.module8_eval.ragas_eval import evaluate_strategy
from modules.module8_eval.retrieval_metrics import mean_mrr, mean_recall_at_k
from shared.config import settings

STRATEGIES = ["semantic", "lexical", "hybrid"]


def run_ablation(test_set: list[dict]) -> None:
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("rag-medical-retrieval")

    for strategy in STRATEGIES:
        with mlflow.start_run(run_name=strategy):
            mlflow.log_params(
                {
                    "strategy": strategy,
                    "embedding_model": EMBEDDING_MODEL,
                    "embedding_dims": EMBEDDING_DIMS,
                    "rrf_k": 60,
                    "mmr_lambda": 0.7,
                    "mmr_top_k": 8,
                }
            )

            ragas_scores = evaluate_strategy(test_set, strategy)
            for metric, score in ragas_scores.items():
                mlflow.log_metric(metric, float(score))

            for k in [10, 100]:
                mlflow.log_metric(
                    f"recall_at_{k}",
                    mean_recall_at_k(test_set, strategy, k),
                )
            mlflow.log_metric("mrr", mean_mrr(test_set, strategy))
