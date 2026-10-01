import hdbscan
import numpy as np

from app.db.session import SessionLocal
from app.models.masked_record import MaskedRecord
from app.services.embeddings import get_embeddings_batch


def run_exploratory_clustering(min_cluster_size: int = 3):
    db = SessionLocal()
    try:
        records = db.query(MaskedRecord).all()
        texts = [r.masked_text for r in records]

        print(f"Embedding {len(texts)} records...")
        embeddings = get_embeddings_batch(texts)
        embeddings_np = np.array(embeddings)

        print("Clustering...")
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=2,
            min_samples=1,
            metric="euclidean",
            cluster_selection_epsilon=0.3,  # allows merging moderately-distant points
        )
        labels = clusterer.fit_predict(embeddings_np)

        # Group texts by cluster label for inspection
        clusters: dict[int, list[str]] = {}
        for label, text in zip(labels, texts):
            clusters.setdefault(label, []).append(text)

        for label in sorted(clusters.keys()):
            members = clusters[label]
            name = "NOISE (no clear cluster)" if label == -1 else f"Cluster {label}"
            print(f"\n{'=' * 70}")
            print(f"{name} — {len(members)} posts")
            print("=" * 70)
            for text in members[:5]:  # show up to 5 examples per cluster
                preview = text[:120].replace("\n", " ")
                print(f"  - {preview}...")

    finally:
        db.close()


if __name__ == "__main__":
    run_exploratory_clustering()