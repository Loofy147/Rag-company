from app.core import allowed_extension, can_share_document, chunk_markdown, has_complete_citation_coverage, reciprocal_rank_fusion, retain_valid_citations, safe_display_filename, sanitize_markdown_resource_targets


def test_chunking_preserves_sections():
    chunks = chunk_markdown("# Policy\n\nRetention is seven years.\n\n## Exception\n\nLegal holds pause deletion.", 256, 24)
    assert chunks
    assert any("Policy" in row["section"] for row in chunks)
    assert any("Legal holds" in row["content"] for row in chunks)


def test_empty_and_long_table_chunking():
    assert chunk_markdown("  \n") == []
    source = "# Data\n\n| Key | Value |\n|---|---|\n" + "\n".join(f"| {i} | {'x' * 35} |" for i in range(20))
    chunks = chunk_markdown(source, 256, 20)
    assert chunks and all(len(row["content"]) <= 256 for row in chunks)


def test_reciprocal_rank_fusion():
    rows = reciprocal_rank_fusion([[{"id":"a","score":0.01},{"id":"b","score":100}], [{"id":"b","score":0.1},{"id":"a","score":0.2}]], k=1)
    assert {row["id"] for row in rows} == {"a","b"}
    assert all("rrf_score" in row for row in rows)


def test_invalid_citations_are_removed():
    answer, valid = retain_valid_citations("Supported claim [S1]. Forged [S99].", {"S1"})
    assert valid == ["S1"]
    assert "[S99]" not in answer


def test_all_substantive_units_need_citations():
    assert has_complete_citation_coverage("Supported claim [S1].\n\nAnother claim [S2].", {"S1","S2"})
    assert not has_complete_citation_coverage("Supported claim [S1].\n\nUnsupported claim.", {"S1"})
    assert not has_complete_citation_coverage("- First [S1]\n- Second item", {"S1"})


def test_contributors_cannot_share_outside_assigned_groups():
    assert can_share_document(user_role="reader", user_groups=[], visibility="private", allowed_groups=[])
    assert can_share_document(user_role="contributor", user_groups=["finance"], visibility="groups", allowed_groups=["finance"])
    assert not can_share_document(user_role="contributor", user_groups=["finance"], visibility="groups", allowed_groups=["executive"])
    assert not can_share_document(user_role="contributor", user_groups=["finance"], visibility="workspace", allowed_groups=[])
    assert can_share_document(user_role="admin", user_groups=[], visibility="workspace", allowed_groups=[])


def test_filename_and_extension_validation():
    assert safe_display_filename("../../secret.pdf") == "secret.pdf"
    assert allowed_extension("report.PDF")
    assert not allowed_extension("payload.exe")


def test_markdown_remote_targets_are_removed():
    cleaned = sanitize_markdown_resource_targets("See [policy](https://example.invalid/policy). ![remote](https://example.invalid/img.png)\n<script>alert(1)</script>")
    assert "See policy." in cleaned
    assert "example.invalid" not in cleaned
    assert "alert(1)" not in cleaned
