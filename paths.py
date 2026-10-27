import os

REPO = os.path.dirname(os.path.abspath(__file__))

DATASET = os.path.join(REPO, "dataset")
GENERATOR = os.path.join(DATASET, "generator")
OUT = os.path.join(DATASET, "out")
OUT_RU = os.path.join(DATASET, "out_ru")
REPORTS = os.path.join(REPO, "reports")
TOOLS = os.path.join(REPO, "tools")

def results(name):
    return os.path.join(REPORTS, name)

def dataset_type(*parts):
    return os.path.join(OUT, *parts)
