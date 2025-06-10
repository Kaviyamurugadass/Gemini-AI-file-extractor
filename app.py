# geminifile

import google.generativeai as genai
import requests
from config import Settings
import webbrowser
import json
import os
import tkinter as tk  # Import tkinter for file dialog
from tkinter import filedialog # Import filedialog for file selection
import fitz  # PyMuPDF for PDF processing
import base64
from io import BytesIO
import re

def extract_images_from_pdf(pdf_path):
    """Extract images from PDF and convert to base64, maintaining their positions"""
    images_by_page = {}  # Dictionary to store images by page number
    doc = fitz.open(pdf_path)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images()
        page_images = []
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            
            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            image_ext = base_image["ext"]
            
            # Store image with its position information
            page_images.append({
                'index': img_index,
                'page': page_num + 1,
                'base64': image_base64,
                'ext': image_ext
            })
        
        if page_images:
            images_by_page[page_num] = page_images
    
    doc.close()
    return images_by_page

def replace_image_placeholders(content, images_by_page):
    """Replace image placeholders with actual image markdown"""
    for page_num, images in images_by_page.items():
        for img in images:
            placeholder = f"[IMAGE_{img['page']}_{img['index']}]"
            image_markdown = f"![Image from page {img['page']}](data:image/{img['ext']};base64,{img['base64']})"
            content = content.replace(placeholder, image_markdown)
    return content

def main():
    # Create and hide the root window
    root = tk.Tk()
    root.withdraw()

    # Open file dialog
    print("Please select a PDF file...")
    file_path = filedialog.askopenfilename(
        title="Select PDF File",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )

    # Check if user selected a file
    if not file_path:
        print("No file selected. Exiting...")
        return

    # Validate file is PDF
    if not file_path.lower().endswith('.pdf'):
        print("Error: Only PDF files are supported")
        return

    # Extract images from PDF
    print("Extracting images from PDF...")
    images_by_page = extract_images_from_pdf(file_path)
    total_images = sum(len(images) for images in images_by_page.values())
    # print(f"Found {total_images} images in the PDF")

    # Configure the API key
    genai.configure(api_key=Settings.GEMINI_API_KEY)

    # 1. Upload the file with explicit MIME type
    uploaded_file = genai.upload_file(
        file_path,
        mime_type="application/pdf"
    )

    # 2. Use the file in a prompt
    model = genai.GenerativeModel("gemini-1.5-flash")  
    
    # Create image placeholders for the prompt
    image_placeholders = []
    for page_num, images in images_by_page.items():
        for img in images:
            image_placeholders.append(
                f"[IMAGE_{img['page']}_{img['index']}]"
            )

    prompt = (
        "You will be given extracted content from a file. Convert it into clean, logically organized Markdown. "
        "Use proper Markdown syntax for:\n"
        "- Headings (for titles or slide headers)\n"
        "- Bullet points (for lists)\n"
        "- Tables (for tabular data)\n"
        "- Blockquotes (for quotations)\n\n"
        "IMPORTANT: The document contains images. Use the following image placeholders in your markdown "
        "exactly where they should appear in the document:\n\n"
        f"{chr(10).join(image_placeholders)}\n\n"
        "Maintain the exact structure and flow of the original document. "
        "Place the images exactly where they appear in the original document. "
        "Here is the content:\n\n"
    )
    
    response = model.generate_content([uploaded_file, prompt])

    # Replace image placeholders with actual images
    markdown_content = replace_image_placeholders(response.text, images_by_page)

    # 3. Print the response
    print(markdown_content)

    # 4. Upload to Wiki.js
    wiki_js_url = Settings.WIKI_JS_URL.rstrip('/')  # Remove trailing slash
    wiki_js_api_token = Settings.WIKI_JS_API_TOKEN
    wiki_js_default_path = Settings.WIKI_JS_DEFAULT_PATH.lstrip('/')  # Remove leading slash

    # Extract filename from file_path for title and slug
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    page_title = f"{file_name}"
    page_path = f"{wiki_js_default_path}/{file_name.replace(' ', '-').lower()}"

    headers = {
        "Authorization": f"Bearer {wiki_js_api_token}",
        "Content-Type": "application/json",
    }

    # Wiki.js GraphQL mutation for page creation
    # This is a static query template that tells Wiki.js how to create a new page
    # The ! after each type means the field is required

    query = """
    mutation(
        $title: String!,
        $content: String!,
        $path: String!,
        $description: String!,
        $editor: String!,
        $locale: String!,
        $isPublished: Boolean!,
        $isPrivate: Boolean!,
        $tags: [String]!
    ) {
        pages {
            create(
                title: $title
                content: $content
                path: $path
                description: $description
                editor: $editor
                locale: $locale
                isPublished: $isPublished
                isPrivate: $isPrivate
                tags: $tags
            ) {
                responseResult {
                    succeeded
                    slug
                    message
                }
                page {
                    id
                    path
                }
            }
        }
    }
    """

    variables = {
        "title": page_title,
        "content": markdown_content,  # Use the content with replaced images
        "path": page_path,
        "description": f"Auto-generated content from {file_name}",
        "editor": "markdown",
        "locale": "en",
        "isPublished": True,
        "isPrivate": False,
        "tags": ["auto-generated", "gemini-ai"]
    }

    wiki_js_api_endpoint = f"{wiki_js_url}/graphql"

    try:
        wiki_response = requests.post(wiki_js_api_endpoint, json={
            "query": query,
            "variables": variables
        }, headers=headers)
        wiki_response.raise_for_status()

        result = wiki_response.json()
        if "errors" in result:
            print("Error uploading to Wiki.js:", json.dumps(result["errors"], indent=2))
        else:
            page_data = result.get('data', {}).get('pages', {}).get('create', {})
            if page_data.get('responseResult', {}).get('succeeded'):
                page_path = page_data.get('page', {}).get('path', '')
                full_url = f"{wiki_js_url}/{page_path.lstrip('/')}"
                print(f"\nSuccessfully created Wiki.js page!")
                print(f"Opening page in browser: {full_url}")
                webbrowser.open(full_url)
            else:
                print("Failed to create page:", json.dumps(page_data.get('responseResult', {}), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while connecting to Wiki.js: {e}")

if __name__ == "__main__":
    main()
