from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from propagation.analysis import analyze_events
from propagation.loaders import make_synthetic_events
from propagation.prediction import run_prediction
from propagation.visualization import build_dashboard


if __name__ == "__main__":
    output = ROOT / "outputs" / "demo"
    events = make_synthetic_events()
    summary = analyze_events(events, str(output))
    report = run_prediction(events, str(output), 0.3)
    dashboard = build_dashboard(events, str(output), report)
    print(summary["narrative"])
    print(report)
    print(f"Dashboard: {dashboard}")
