import pytest
from app.services.extractor import Extractor

def test_extractor_bracket_citation():
    extractor = Extractor()
    paragraphs = [
        {
            "text": "This is a simple sentence. The model achieved 95% accuracy on the test set [4]. Here is another sentence without citations.",
            "page_number": 2
        }
    ]
    
    pairs = extractor.extract(paragraphs)
    
    assert len(pairs) == 1
    assert pairs[0].citation_marker == "[4]"
    assert pairs[0].page_number == 2
    assert "The model achieved 95% accuracy" in pairs[0].text

def test_extractor_author_year_citation():
    extractor = Extractor()
    paragraphs = [
        {
            "text": "Deep learning has revolutionized NLP (Smith et al., 2020). However, challenges remain.",
            "page_number": 5
        }
    ]
    
    pairs = extractor.extract(paragraphs)
    
    assert len(pairs) == 1
    assert pairs[0].citation_marker == "(Smith et al., 2020)"
    assert pairs[0].page_number == 5

def test_extractor_multiple_citations_in_one_sentence():
    extractor = Extractor()
    paragraphs = [
        {
            "text": "Multiple studies show this effect [1] and [2].",
            "page_number": 1
        }
    ]
    
    pairs = extractor.extract(paragraphs)
    
    assert len(pairs) == 2
    assert pairs[0].citation_marker == "[1]"
    assert pairs[1].citation_marker == "[2]"
    # Both pairs should map to the same claim sentence
    assert pairs[0].text == pairs[1].text

def test_extractor_no_citations():
    extractor = Extractor()
    paragraphs = [
        {
            "text": "This paragraph has absolutely no citations. It is just a plain text paragraph.",
            "page_number": 1
        }
    ]
    
    pairs = extractor.extract(paragraphs)
    assert len(pairs) == 0
