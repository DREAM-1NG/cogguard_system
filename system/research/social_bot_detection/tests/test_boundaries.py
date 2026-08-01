from pathlib import Path


def test_research_package_does_not_import_external_nlpcc_code():
    root = Path(__file__).parents[1]
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "G:\\Research\\BotDetection\\NLPCC\\code" not in source
    assert "sys.path.insert" not in source
