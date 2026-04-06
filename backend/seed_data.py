import json
import os

from sqlalchemy.orm import Session

from models import Experiment


EXPERIMENTS_DIR = os.path.join("..", "experiments")


def seed_experiments_from_json(db: Session):
    if not os.path.isdir(EXPERIMENTS_DIR):
        return

    for filename in os.listdir(EXPERIMENTS_DIR):
        if not filename.endswith(".json"):
            continue

        path = os.path.join(EXPERIMENTS_DIR, filename)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        slug = filename.replace(".json", "")
        existing = db.query(Experiment).filter(Experiment.slug == slug).first()
        if existing:
            existing.title = payload.get("title", slug)
            existing.objective = payload.get("objective", "")
            existing.steps = payload.get("steps", [])
            existing.rubric = {}
            continue

        experiment = Experiment(
            slug=slug,
            title=payload.get("title", slug),
            objective=payload.get("objective", ""),
            steps=payload.get("steps", []),
            rubric={},
        )
        db.add(experiment)

    db.commit()


def initialize_seed_data(db: Session):
    seed_experiments_from_json(db)
