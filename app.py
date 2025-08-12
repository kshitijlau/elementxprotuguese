import streamlit as st
import pandas as pd
import base64
import time
import io
import requests  # Using requests library for simplicity in API calls

# --- Configuration & Constants ---

# This is the final, optimized prompt we developed.
# It's crucial for getting the correct translation behavior from the model.
TRANSLATION_PROMPT_TEMPLATE = """
**Role:** You are an expert technical translator and a native Brazilian Portuguese speaker. Your goal is to translate English HTML content into fluent, natural-sounding Brazilian Portuguese.

**Task:** Translate the user-provided English HTML content to Portuguese while strictly following all the rules below. Your output must be only the translated HTML string.

**Rules:**
1.  **Preserve HTML Integrity:**
    * You MUST NOT translate, alter, add, or remove any HTML tags (e.g., `<p>`, `<span style="...">`, `<a href="...">`, `<strong>`).
    * You MUST preserve all HTML attributes exactly as they are (e.g., `class="..."`, `style="..."`, `id="..."`, `href="..."`).
    * You MUST preserve all HTML entities (e.g., `&nbsp;`).
    * The HTML structure of your output must be absolutely identical to the input.

2.  **Do Not Translate (DNT) Terms:**
    * The following brand and product names MUST remain in English: `Mercer`, `Mercer Talent Enterprise`, `Element X`.

3.  **Do Not Translate Emails or URLs:**
    * Any email address (e.g., `mte.surveys@mercer.com`) or URL must remain unchanged.

4.  **Translate Only Content:**
    * Only translate the human-readable text content that is not part of an HTML tag or a DNT term.

**Examples:**

**Example 1: Simple text with styling**
* **English Input:** `<p><strong><span style="font-family: Arial, Helvetica, sans-serif; font-size: 14px;">I feel good about myself and believe others like me for who I am.</span></strong></p>`
* **Portuguese Output:** `<p><strong><span style="font-family: Arial, Helvetica, sans-serif; font-size: 14px;">Sinto-me bem comigo mesmo(a) e acredito que os outros gostam de mim por quem eu sou.</span></strong></p>`

**Example 2: Complex paragraph with DNT and a complicated email link**
* **English Input:** `<p><span style="font-family: Arial, Helvetica, sans-serif; font-size: 14px;">If you have any questions regarding this <strong>Element X</strong> questionnaire, please write to us at <a href="mailto:mte.surveys@mercer.com" rel="noreferrer noopener" target="_blank" class="fui-Link ___1rxvrpe f2hkw1w">mte.surveys@mercer.com</a> for assistance.&nbsp;</span></p>`
* **Portuguese Output:** `<p><span style="font-family: Arial, Helvetica, sans-serif; font-size: 14px;">Se tiver alguma dúvida sobre este questionário <strong>Element X</strong>, escreva para nós em <a href="mailto:mte.surveys@mercer.com" rel="noreferrer noopener" target="_blank" class="fui-Link ___1rxvrpe f2hkw1w">mte.surveys@mercer.com</a> para obter assistência.&nbsp;</span></p>`

**Example 3: Untagged survey options**
* **English Input:** `NeverRarelySometimesVery OftenAlways`
* **Portuguese Output:** `NuncaRaramenteÀs vezesMuito FrequentementeSempre`

---
{english_text}
"""

# --- Gemini API Call Function ---

def get_gemini_translation(api_key, text_to_translate):
    """
    Calls the Gemini API to translate text using the predefined prompt.
    Includes exponential backoff for retries.
    """
    # The API key is passed as a parameter for security and flexibility.
    # The model name is specified here.
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"

    # Construct the full prompt
    full_prompt = TRANSLATION_PROMPT_TEMPLATE.format(english_text=text_to_translate)
    
    payload = {
        "contents": [{
            "parts": [{"text": full_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2, # Lower temperature for more deterministic, less creative output
            "maxOutputTokens": 4096,
        }
    }

    max_retries = 5
    delay = 1  # Initial delay in seconds

    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
            
            result = response.json()
            
            # Navigate the JSON response to get the translated text
            if 'candidates' in result and result['candidates']:
                if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                    translated_text = result['candidates'][0]['content']['parts'][0]['text']
                    return translated_text.strip()
            
            # Handle cases where the response structure is unexpected
            st.error(f"Unexpected API response structure: {result}")
            return "Error: Unexpected response format."

        except requests.exceptions.HTTPError as http_err:
            # Handle specific HTTP errors, like 429 Too Many Requests
            if response.status_code == 429:
                st.warning(f"Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                st.error(f"HTTP error occurred: {http_err} - {response.text}")
                return f"Error: HTTP {response.status_code}"
        except Exception as e:
            st.error(f"An error occurred while calling the Gemini API: {e}")
            return "Error: API call failed."
            
    st.error("Translation failed after multiple retries.")
    return "Error: Max retries exceeded."


# --- Helper Functions ---

def get_sample_excel():
    """Creates a sample Excel file in memory for download."""
    sample_data = {
        'key': ['welcome_message', 'instruction_1'],
        'english_string': [
            '<p><strong>Welcome to Element X!</strong> Please complete the survey.</p>',
            '<span>Contact us at <a href="mailto:help@mercer.com">help@mercer.com</a> for support.</span>'
        ]
    }
    df_sample = pd.DataFrame(sample_data)
    
    # Use BytesIO to save the file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_sample.to_excel(writer, index=False, sheet_name='translations')
    
    # Rewind the buffer
    output.seek(0)
    return output.getvalue()


def get_download_link(df, filename="translated_data.xlsx"):
    """Generates a download link for a DataFrame."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='translations')
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">Download Translated Excel File</a>'
    return href


# --- Streamlit App UI ---

st.set_page_config(page_title="HTML Content Translator", layout="wide")

st.title("批量HTML内容翻译器 (Bulk HTML Content Translator)")
st.markdown("使用Gemini Pro将Excel文件中的英文HTML内容翻译成葡萄牙语，同时保留所有格式和指定的术语。")
st.markdown("This app uses Gemini Pro to translate English HTML content from an Excel file into Portuguese, preserving all formatting and specified terms.")

# API Key Input
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter your Gemini API Key", type="password")

st.sidebar.markdown("---")

# Sample File Download
st.sidebar.subheader("Don't have a file?")
st.sidebar.download_button(
    label="Download Sample Format",
    data=get_sample_excel(),
    file_name="sample_translation_format.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")

# File Uploader
uploaded_file = st.file_uploader("Upload your Excel file (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Validate columns
        if 'key' not in df.columns or 'english_string' not in df.columns:
            st.error("Error: The uploaded Excel file must contain 'key' and 'english_string' columns.")
        else:
            st.success("File uploaded successfully! Here's a preview:")
            st.dataframe(df.head())

            if st.button("Translate to Portuguese"):
                if not api_key:
                    st.warning("Please enter your Gemini API Key in the sidebar to proceed.")
                else:
                    # Translation process
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    total_rows = len(df)
                    
                    df['portuguese_string'] = '' # Initialize the new column

                    for index, row in df.iterrows():
                        english_text = row['english_string']
                        
                        # Update status
                        status_text.text(f"Translating row {index + 1}/{total_rows}...")

                        # Check for empty or non-string content to avoid unnecessary API calls
                        if isinstance(english_text, str) and english_text.strip():
                            translated_text = get_gemini_translation(api_key, english_text)
                            df.at[index, 'portuguese_string'] = translated_text
                        else:
                            # If the cell is empty or not a string, keep the translation empty
                            df.at[index, 'portuguese_string'] = ''

                        # Update progress bar
                        progress_bar.progress((index + 1) / total_rows)
                    
                    status_text.success("Translation complete!")
                    
                    st.markdown("---")
                    st.subheader("Translated Content")
                    st.dataframe(df)
                    
                    # Provide download link
                    st.markdown(get_download_link(df), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")

