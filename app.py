# geminifile

import google.generativeai as genai
import requests
from config import Settings
import webbrowser
import json
import os
import tkinter as tk  # Import tkinter for file dialog
from tkinter import filedialog # Import filedialog for file selection

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

    # Gemini API key
    GEMINI_API_KEY = "AIzaSyA9l0lgZPm8OCYvGsCAvzeqdCwdAAy4sWk"

    # Configure the API key
    genai.configure(api_key=GEMINI_API_KEY)

    # 1. Upload the file with explicit MIME type
    uploaded_file = genai.upload_file(
        file_path,
        mime_type="application/pdf"
    )

    # 2. Use the file in a prompt
    model = genai.GenerativeModel("gemini-1.5-flash")  
    prompt = (
        "You will be given extracted content from a file. Convert it into clean, logically organized Markdown. "
        "Use proper Markdown syntax for:\n"
        "- Headings (for titles or slide headers)\n"
        "- Bullet points (for lists)\n"
        "- Tables (for tabular data)\n"
        "- Blockquotes (for quotations)\n"
        "- Inline images (use given base64)\n\n"
        "Avoid repetition. Maintain original structure and flow, but present it clearly and concisely. "
        "Here is the content:\n\n"
    )
    response = model.generate_content([uploaded_file, prompt])

    # 3. Print the response
    print(response.text)

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
        "content": response.text,
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
