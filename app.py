# geminifile

import google.generativeai as genai

# Replace with your actual Gemini API key
GEMINI_API_KEY = "AIzaSyA9l0lgZPm8OCYvGsCAvzeqdCwdAAy4sWk"

# Configure the API key
genai.configure(api_key=GEMINI_API_KEY)

# Path to your file (e.g., pptx)
file_path = "C:\\Users\\Kaviya\\Downloads\\Text Module.pdf"

# 1. Upload the file with explicit MIME type
uploaded_file = genai.upload_file(
    file_path,
    mime_type="application/pdf"
)

print("Uploaded file URI:", uploaded_file.uri)

# 2. Use the file in a prompt
model = genai.GenerativeModel("gemini-1.5-flash")  # or "gemini-1.5-pro"
prompt = "Can you generate a markdown of this document"
response = model.generate_content([uploaded_file, prompt])

# 3. Print the response
print(response.text)

# (Optional) To delete the file if you don't need it anymore
# genai.delete_file(uploaded_file.name)