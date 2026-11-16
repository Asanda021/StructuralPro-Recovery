from collections import Counter

import pymupdf

from core.drawings import pdf_vector_type_labels as labels


# Dimensionless lettering for fabricated pages.
LETTERING = {
    'C': (((.66, .17), (.5, 0), (.16, 0), (0, .17), (0, .83),
           (.16, 1), (.5, 1), (.66, .83)),),
    'B': (((0, .5), (0, 0), (.47, 0), (.64, .125), (.64, .375), (.47, .5), (0, .5)),
          ((0, .5), (.47, .5), (.64, .625), (.64, .875), (.47, 1), (0, 1), (0, .5))),
    'F': (((0, 1), (0, 0), (.64, 0)), ((0, .47), (.5, .47))),
    'T': (((.34, 0), (.34, 1)), ((0, 0), (.68, 0))),
    '-': (((0, .5), (.34, .5)),),
    '1': (((0, .17), (.22, 0), (.22, 1)),),
    '¹': (((0, .17), (.22, 0), (.22, 1)), ((0, 1), (.44, 1))),
    '2': (((0, .17), (.16, 0), (.48, 0), (.64, .17), (.64, .34),
           (.48, .5), (.16, .5), (0, .67), (0, 1), (.64, 1)),),
    '3': (((0, .17), (.16, 0), (.48, 0), (.64, .17), (.64, .33), (.48, .5), (.32, .5)),
          ((.48, .5), (.64, .67), (.64, .83), (.48, 1), (.16, 1), (0, .83))),
    '0': (((.15, 0), (.48, 0), (.64, .18), (.64, .82), (.48, 1),
           (.15, 1), (0, .82), (0, .18), (.15, 0)),),
    'I': (((.24, 0), (.24, 1)), ((0, 0), (.48, 0)), ((0, 1), (.48, 1))),
    'l': (((0, 0), (0, 1)),),
}


def _mark(page, word, origin, height, *, together=False, reverse=False):
    x, y = origin
    shape = page.new_shape()
    for char in word:
        for chain in LETTERING[char]:
            points = [(x + a * height, y + b * height) for a, b in chain]
            shape.draw_polyline(points[::-1] if reverse else points)
            if not together:
                shape.finish(closePath=False)
        x += (max(a for chain in LETTERING[char] for a, _ in chain) + .2) * height
    if together:
        shape.finish(closePath=False)
    shape.commit()


def _scan(page, **kwargs):
    return labels.recover_page_vector_type_words(page, document_id='example', page_number=1, **kwargs)


def test_template_words_on_an_open_page_keep_distinct_original_operator_ids():
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=300)
        for index, word in enumerate(('C1', 'C2', 'C3', 'B1', 'B2', 'F-1', 'T-1')):
            _mark(page, word, (23 + 65 * index, 72), 13,
                  together=index == 3, reverse=index % 2 == 0)
        drawings = page.get_drawings()
        before = _scan(page, paths=drawings)
        page.set_rotation(90)
        after = _scan(page)
    assert before['status'] == 'VECTOR_STROKE_WORDS_INDEXED'
    assert before['all_vector_strokes_examined'] is True
    assert before['physical_member_count'] is None
    assert before['type_word_witnesses'] == after['type_word_witnesses']
    entries = before['type_word_witnesses']
    assert {entry['source_token'] for entry in entries} == {'C1', 'C2', 'C3', 'B1', 'B2', 'F-1', 'T-1'}
    assert {entry['type_tag'] for entry in entries} == {'C1', 'C2', 'C3', 'B1', 'B2', 'F1', 'T1'}
    assert all(entry['status'] == 'ISOLATED_TYPE_WORD_POSITION_CANDIDATE' for entry in entries)
    assert all(entry['physical_member_verified'] is False and entry['quantity_approved'] is False
               and entry['financially_payable'] is False for entry in entries)
    all_operators = Counter(operator for entry in entries for operator in entry['source_operator_ids'])
    assert all_operators and set(all_operators.values()) == {1}
    assert all(operator.startswith('example:p1:d') and ':s' in operator for operator in all_operators)
    entry = next(entry for entry in entries if entry['type_tag'] == 'B1')
    assert len(entry['source_path_indices']) == 1
    assert len(entry['source_operator_ids']) == 14


def test_upright_and_grid_edges_never_turn_a_prefix_into_a_digit():
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'CI', (42, 25), 15)
        _mark(page, 'Cl', (42, 66), 15)
        _mark(page, 'C1', (42, 105), 15)
        # A separate cap touches the last stem and prevents a unique digit reading.
        stem_x = 42 + (.66 + .2 + .22) * 15
        page.draw_line((stem_x - 1.5, 120), (stem_x + 1.5, 120))
        _mark(page, 'C', (42, 160), 15)
        page.draw_line((57, 138), (57, 210))
        page.draw_line((24, 228), (123, 228))
        page.draw_line((55, 228), (55, 243))
        _mark(page, '-1', (65, 228), 15)
        result = _scan(page)
    assert result['type_word_witnesses'] == []
    ambiguous = [row for row in result['rejections'] if row['reason'] == 'AMBIGUOUS_UPRIGHT']
    assert sorted(len(row['source_path_indices']) for row in ambiguous) == [2, 4]
    assert any(row['reason'] == 'UNEXPECTED_GLYPH_STROKE' for row in result['rejections'])
    assert all(row['type_tag'] is None and row['source_operator_ids'] for row in result['rejections'])


def test_ambiguous_strokes_reach_intake_page_count_and_graph_review(tmp_path):
    from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set

    source = tmp_path / 'synthetic-uprights.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        _mark(page, 'CI', (42, 25), 15)
        _mark(page, 'Cl', (42, 66), 15)
        pdf.save(source)
    graph = inspect_pdf_sheet_set([source])['detail_evidence_graph']
    assert graph['pages'][0]['vector_text_ambiguous_count'] == 2
    assert graph['pages'][0]['vector_text_type_count'] == 0
    cases = [node for node in graph['nodes'] if node.get('evidence_quality') == 'AMBIGUOUS_GLYPH']
    assert len(cases) == 2
    for node in cases:
        witness = node['anchors'][0]
        assert node['type_tag'] is None and node['financially_payable'] is False
        assert witness['glyph_ambiguity_reason'] == 'AMBIGUOUS_UPRIGHT'
        assert witness['glyph_interpretations'] == ['C1', 'CI', 'Cl']
        assert witness['source_operator_ids']
    assert not [node for node in graph['nodes'] if node['kind'] == 'INSTANCE_CANDIDATE']


def test_hooked_one_can_have_a_centered_baseline_foot():
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'C¹', (50, 75), 17, reverse=True)
        _mark(page, 'CI', (50, 110), 17, reverse=True)
        result = _scan(page)
    assert [w['type_tag'] for w in result['type_word_witnesses']] == ['C1']
    assert len(result['type_word_witnesses'][0]['source_path_indices']) == 3
    assert any(w['reason'] == 'AMBIGUOUS_UPRIGHT' for w in result['rejections'])


def test_two_prefixes_cannot_use_one_numeric_stroke():
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'C', (30, 50), 14)
        _mark(page, 'B', (30, 50), 14)
        _mark(page, '1', (43, 50), 14)
        result = _scan(page)
    assert result['type_word_witnesses'] == []
    assert sum(row['reason'] == 'AMBIGUOUS_GLYPH_OWNERSHIP' for row in result['rejections']) == 2


def test_possible_longer_type_token_is_not_truncated_to_a_supported_digit():
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'C10', (30, 50), 14)
        _mark(page, '0C1', (30, 90), 14)
        result = _scan(page)
    assert result['type_word_witnesses'] == []
    rows = [w for w in result['rejections'] if w['reason'] == 'POSSIBLE_ADJACENT_GLYPH']
    assert len(rows) == 2
    assert all(len(w['source_path_indices']) == 3 for w in rows)


def test_two_bars_for_one_t_stem_are_one_unresolved_prefix():
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'T-1', (30, 50), 14)
        page.draw_line((30, 50), (30 + .68 * 14, 50))
        result = _scan(page)
    assert result['type_word_witnesses'] == []
    assert [w['reason'] for w in result['rejections']] == ['MULTIPLE_GLYPH_INTERPRETATIONS']
    assert len(result['rejections'][0]['source_path_indices']) == 5


def test_local_work_cap_returns_no_partial_words(monkeypatch):
    monkeypatch.setattr(labels, '_MAX_LOCAL_STROKES', 4)
    with pymupdf.open() as doc:
        page = doc.new_page()
        _mark(page, 'C1', (30, 50), 14)
        _mark(page, 'C', (170, 50), 14)
        for index in range(10):
            _mark(page, '1', (183 + .15 * index, 50), 14)
        result = _scan(page)
    assert result['status'] == 'BLOCKED_VECTOR_STROKE_LOCAL_BUDGET'
    assert result['all_vector_strokes_examined'] is False
    assert result['type_word_witnesses'] == []
