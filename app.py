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
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"

    full_prompt = TRANSLATION_PROMPT_TEMPLATE.format(english_text=text_to_translate)
    
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192, # Increased token limit to handle larger content
        }
    }

    max_retries = 5
    delay = 1

    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'})
            response.raise_for_status()
            
            result = response.json()
            
            # Check for the 'candidates' key and that it's not empty
            if 'candidates' in result and result['candidates']:
                # Check for content and parts within the first candidate
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                    return candidate['content']['parts'][0]['text'].strip()
            
            # If the expected structure is not found, log the reason
            finish_reason = result.get('candidates', [{}])[0].get('finishReason', 'UNKNOWN')
            st.error(f"Translation failed. Finish Reason: {finish_reason}. Full response: {result}")
            return f"Error: Translation stopped ({finish_reason})."

        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:
                st.warning(f"Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
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
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_sample.to_excel(writer, index=False, sheet_name='translations')
    
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
st.markdown("This app uses Gemini Pro to translate English HTML content from an Excel file into Portuguese, preserving all formatting and specified terms.")

# --- Load API Key from Secrets ---
# For deployment on Streamlit Cloud, the API key is stored in secrets.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("GEMINI_API_KEY not found in Streamlit secrets.")
    st.info("Please add your Gemini API key to your Streamlit Cloud secrets. For local testing, you can create a .streamlit/secrets.toml file.")
    st.stop()


st.sidebar.header("Instructions")
st.sidebar.info("Upload an Excel file with 'key' and 'english_string' columns to begin the translation.")

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
        
        if 'key' not in df.columns or 'english_string' not in df.columns:
            st.error("Error: The uploaded Excel file must contain 'key' and 'english_string' columns.")
        else:
            st.success("File uploaded successfully! Here's a preview:")
            st.dataframe(df.head())

            if st.button("Translate to Portuguese"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_rows = len(df)
                
                df['portuguese_string'] = ''

                for index, row in df.iterrows():
                    english_text = row['english_string']
                    
                    status_text.text(f"Translating row {index + 1}/{total_rows}...")

                    if isinstance(english_text, str) and english_text.strip():
                        translated_text = get_gemini_translation(api_key, english_text)
                        df.at[index, 'portuguese_string'] = translated_text
                    else:
                        df.at[index, 'portuguese_string'] = ''

                    progress_bar.progress((index + 1) / total_rows)
                
                status_text.success("Translation complete!")
                
                st.markdown("---")
                st.subheader("Translated Content")
                st.dataframe(df)
                
                st.markdown(get_download_link(df), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
