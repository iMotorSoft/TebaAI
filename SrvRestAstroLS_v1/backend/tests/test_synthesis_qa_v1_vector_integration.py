from pathlib import Path


def test_synthesis_batch_invokes_common_vector_backend():
    source = Path(__file__).parents[1] / "scripts" / "library_synthesis_qa_v1_batch.py"
    text = source.read_text()
    assert "get_vector_backend" in text
    assert "vector_evidence" in text
    assert '"source_method": "vector"' in text
