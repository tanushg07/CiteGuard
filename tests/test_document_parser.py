import pytest
from unittest.mock import MagicMock, patch
from app.services.document_parser import DocumentParser

@patch("app.services.document_parser.fitz.open")
def test_document_parser_success(mock_fitz_open):
    # Setup mock PDF document
    mock_doc = MagicMock()
    mock_fitz_open.return_value = mock_doc
    
    # We will mock it as having 1 page
    mock_doc.__len__.return_value = 1
    
    mock_page = MagicMock()
    # Return 2 blocks of text (block_type=0) and 1 image block (block_type=1)
    # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
    mock_page.get_text.return_value = [
        (0, 0, 100, 100, "This is the first paragraph which is quite long enough.\nAnd has a newline.", 0, 0),
        (0, 100, 100, 200, "Too short", 1, 0),  # Should be ignored (length < 20)
        (0, 200, 100, 300, "<image_data>", 2, 1), # Should be ignored (type 1)
        (0, 300, 100, 400, "This is another valid paragraph on the same page.", 3, 0)
    ]
    mock_doc.load_page.return_value = mock_page

    parser = DocumentParser("dummy.pdf")
    paragraphs = parser.parse()

    assert len(paragraphs) == 2
    assert paragraphs[0]["page_number"] == 1
    assert paragraphs[0]["text"] == "This is the first paragraph which is quite long enough. And has a newline."
    
    assert paragraphs[1]["page_number"] == 1
    assert paragraphs[1]["text"] == "This is another valid paragraph on the same page."

@patch("app.services.document_parser.fitz.open")
def test_document_parser_file_not_found(mock_fitz_open):
    mock_fitz_open.side_effect = Exception("File not found")
    
    parser = DocumentParser("missing.pdf")
    with pytest.raises(RuntimeError, match="Failed to parse PDF missing.pdf"):
        parser.parse()
