import logging
import re
from time import time

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)
from collections import Counter


def read_pdf_file(pdf_path):
    """
    Reads a PDF file at the given pdf_path and extracts text from each page of the file. The function then cleans and processes
    the text, categorizing it into "Headings" and "Paragraphs" based on the number of words. Finally, it returns a list of
    dictionaries containing the categorized text content.
    :param pdf_path:
    :return:
    """
    text = ""
    pages = []
    t = time()
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        num_pages = len(reader.pages)
        logger.info(f"PDF file pages: {num_pages}")
        for page in reader.pages:
            page_content = page.extract_text()
            pages.append(page_content)
    cleaned_list = []
    for text in pages:
        # Remove newline characters
        text = text.replace('\n', ' ')
        # Remove the form feed character
        text = (text.replace('\x0c', ' ')).strip()
        text = (text.replace('\xad', ' ')).strip()
        words = word_counter(text)
        if words == 0:
            continue
        elif words < 25:
            cleaned_list.append({"tag": "Heading", "number": None, "content": text})
        else:
            cleaned_list.append({"tag": "Paragraph", "number": None, "content": text})
    logger.info(f'PDF text extraction: {time() - t} sec')
    return cleaned_list


def word_counter(text):
    """
    Takes a string text as input and counts the frequency of each word in the text.
    The function then returns the total number of words in the text.
    :param text:
    :return:
    """
    text = str(text)
    text = re.sub(r'[^\w\s]', '', text.lower())
    words = text.split()
    word_count = Counter(words)
    total_words = sum(word_count.values())
    return total_words


from docx import Document


def read_docx_file(file_path):
    """
    Reads a DOCX file at the given file_path and extracts text from the file, removing unwanted characters such as newline
    characters, soft hyphens, and form feed characters. The function then returns the extracted text as a single string.
    :param file_path:
    :return:
    """
    try:
        doc = Document(file_path)
        full_text = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.replace('\n', ' ').replace('\xad', '').replace('\x0c',
                                                                                 '')  # Remove unwanted characters
            full_text.append(text)
        return ' '.join(full_text)  # Join paragraphs with spaces instead of newline characters
    except Exception as e:
        logger.info("An error occurred:", str(e))
        return None


def read_text_file(file_path):
    """
    Reads a text file at the given file_path and returns the contents of the file as a single string.
    The function handles exceptions such as file not found errors and logs an error message if an exception occurs.
    :param file_path:
    :return:
    """
    try:
        with open(file_path, 'r') as file:
            text = file.read()
        return text
    except FileNotFoundError:
        logger.info(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        logger.info(f"Error: {e}")
        return None
