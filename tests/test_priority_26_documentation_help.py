from core.help.content import topics,topic,search

def test_help_topics_are_complete_and_unique():
    rows=topics()
    assert len(rows)>=5
    assert len({x.key for x in rows})==len(rows)
    assert all(x.title and x.summary and x.steps for x in rows)

def test_help_search_and_topic_lookup():
    assert topic("recovery").title=="پشتیبان و بازیابی"
    assert any(x.key=="reports" for x in search("گزارش"))
    assert len(search(""))==len(topics())
