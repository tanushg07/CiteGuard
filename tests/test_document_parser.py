from unittest.mock import MagicMock, patch

import pytest

from app.services.document_parser import DocumentParser


@patch("app.services.document_parser.pdfplumber.open")
def test_document_parser_success(mock_pdf_open):
    # Setup mock PDF document
    mock_pdf = MagicMock()
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf
    
    mock_page = MagicMock()
    # Mock text with double newline for paragraph splitting
    mock_page.extract_text.return_value = (
        "This is the first paragraph which is quite long enough.\nAnd has a newline.\n\n"
        "Too short\n\n"
        "This is another valid paragraph on the same page."
    )
    mock_pdf.pages = [mock_page]

    parser = DocumentParser("dummy.pdf")
    paragraphs = parser.parse()["paragraphs"]

    assert len(paragraphs) == 2
    assert paragraphs[0]["page_number"] == 1
    assert paragraphs[0]["text"] == "This is the first paragraph which is quite long enough. And has a newline."
    
    assert paragraphs[1]["page_number"] == 1
    assert paragraphs[1]["text"] == "This is another valid paragraph on the same page."

@patch("app.services.document_parser.pdfplumber.open")
def test_document_parser_file_not_found(mock_pdf_open):
    mock_pdf_open.side_effect = Exception("File not found")
    
    parser = DocumentParser("missing.pdf")
    with pytest.raises(RuntimeError, match="Failed to parse PDF missing.pdf"):
        parser.parse()
