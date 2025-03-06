import streamlit as st
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import shutil
import json
import pandas as pd
from docx import Document
import openai


# Người dùng nhập OpenAI API Key
api_key = st.text_input("🔑 Nhập OpenAI API Key:", type="password")
if not api_key:
    st.warning("Vui lòng nhập OpenAI API Key để sử dụng ứng dụng.")
    st.stop()

# Cấu hình OpenAI client
client = openai.OpenAI(api_key=api_key)

# Theo dõi số request và chi phí
total_requests = 0
total_cost = 0.0

# Định giá OpenAI API
PRICE_PER_1K_TOKENS = {
    "gpt-3.5-turbo": 0.002,  # $0.002 per 1K tokens
    "gpt-4-turbo": 0.01       # $0.01 per 1K tokens
}

def extract_text_from_pdf(pdf_path):
    """Trích xuất văn bản từ file PDF."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.error(f"Lỗi khi xử lý PDF: {e}")
        return None
    return text

# Biến theo dõi số lần request và chi phí sử dụng OpenAI API
total_requests = 0
total_cost = 0.0

# Định giá OpenAI API (có thể thay đổi nếu OpenAI cập nhật giá)
PRICE_PER_1K_TOKENS = {
    "gpt-3.5-turbo": 0.0005,  # $0.002 per 1K tokens
    "gpt-4-turbo": 0.01       # $0.01 per 1K tokens
}
def clean_json_response(response_text):
    """Làm sạch phản hồi GPT để loại bỏ các ký tự không mong muốn trước khi phân tích JSON."""
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    return response_text.strip()
# Biến theo dõi số lần request và tổng chi phí sử dụng OpenAI API
total_requests = 0
total_cost = 0.0

# Định giá OpenAI API (có thể thay đổi nếu OpenAI cập nhật giá)
PRICE_PER_1K_TOKENS = {
    "gpt-3.5-turbo": 0.0005,  # $0.002 per 1K tokens
    "gpt-4-turbo": 0.01       # $0.01 per 1K tokens
}

def extract_info_with_gpt(text):
    """Sử dụng GPT-3.5 Turbo để trích xuất thông tin từ văn bản và tính toán chi phí."""
    global total_requests, total_cost  # Sử dụng biến toàn cục để theo dõi số request và chi phí

    prompt = f"""
    Trích xuất thông tin sau từ văn bản CV và trả về dưới dạng JSON có cấu trúc hợp lệ:
    {{
        "Name": "",
        "Email": "",
        "Phone": "",
        "Skills": [],
        "Experience": [],
        "Education": [],
        "Certifications": [],
        "Languages": []
    }}
    
    CV text:
    {text}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an expert in extracting information from CVs (resume) and images with 10 years of experience in getting the exact information needed to recruit suitable positions for the company"
            "Context: I will provide you with resumes of candidates (can be 1 or more resumes) or image files containing text"
            "Your task is to extract information from the resumes and images I provide (I have taken the text from the resume and the image will be provided to you below) you return the output as a json file"
            "Some of the most important information required of each candidate: Name, Email, Phone number, Skills, Experience (including: position, timeline, responsibilities), Education (including: degree, institution, timeline, GPA), Certifications, Languages,... In addition, I can also provide you with documents related to identification and visa, you must also get important information in there."
            "Task: extract the following information from the CV text and return it as JSON"
            "output: json file format"
            "*** note here I can provide you with the text, but in that text will be a synthesis of many resumes of different candidates"
            "REMEMBER : the output only json format"},
            {"role": "user", "content": prompt}
        ]
    )

    # Cập nhật số lần request
    total_requests += 1

    # Lấy số token sử dụng từ response
    if hasattr(response, "usage"):
        tokens_used = response.usage.total_tokens  # Tổng số token tiêu tốn
        cost = (tokens_used / 1000) * PRICE_PER_1K_TOKENS["gpt-3.5-turbo"]  # Chi phí request
        total_cost += cost  # Cộng dồn vào tổng chi phí
    else:
        tokens_used = 0
        cost = 0.0

    # Trích xuất nội dung phản hồi
    extracted_text = response.choices[0].message.content.strip()
    cleaned_text = clean_json_response(extracted_text)

    return json.loads(cleaned_text)

def display_summary():
    """Hiển thị tổng số request và tổng chi phí sau khi hoàn tất."""
    st.write(f"🔄 **Tổng số request API:** {total_requests}")
    st.write(f"💰 **Tổng chi phí OpenAI API:** ${total_cost:.4f}")


def save_to_json(data_list, output_path):
    """Lưu dữ liệu dưới dạng JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data_list, f, ensure_ascii=False, indent=4)

def create_word_file(text_list, output_path):
    """Tạo file Word chứa nội dung trích xuất."""
    try:
        doc = Document()
        for idx, (filename, text) in enumerate(text_list):
            doc.add_heading(f"File {idx + 1}: {filename}", level=1)
            doc.add_paragraph(text)
            doc.add_page_break()
        doc.save(output_path)
        return True
    except Exception as e:
        st.error(f"Lỗi khi tạo file Word: {e}")
        return False

def main():
    st.title("📄 PDF to JSON Converter")
    st.write("🔹 Tải lên tối đa **200 file PDF**, trích xuất văn bản, chuyển đổi sang **Word & JSON**.")

    uploaded_files = st.file_uploader("📤 Chọn file PDF", type=["pdf"], accept_multiple_files=True)
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)

    # Chỉ hiển thị nút khi có tệp tải lên
    if uploaded_files:
        st.success(f"✅ Đã tải lên {len(uploaded_files)} file PDF. Nhấn **'Bắt đầu chuyển đổi'** để xử lý.")

        if st.button("🚀 Bắt đầu chuyển đổi PDF sang JSON"):
            with st.spinner("⏳ Đang xử lý... Vui lòng chờ giây lát."):
                extracted_data = []
                extracted_texts = []

                for uploaded_file in uploaded_files:
                    temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    text = extract_text_from_pdf(temp_file_path)
                    if text:
                        extracted_texts.append((uploaded_file.name, text))
                        extracted_info = extract_info_with_gpt(text)
                        extracted_info["Filename"] = uploaded_file.name
                        extracted_data.append(extracted_info)
                    os.remove(temp_file_path)

                word_output = os.path.join(temp_dir, "extracted_texts.docx")
                if create_word_file(extracted_texts, word_output):
                    with open(word_output, "rb") as file:
                        st.download_button("📥 Tải file Word", file, file_name="extracted_texts.docx")

                json_output = os.path.join(temp_dir, "extracted_data.json")
                save_to_json(extracted_data, json_output)
                with open(json_output, "rb") as file:
                    st.download_button("📥 Tải file JSON", file, file_name="extracted_data.json")

            # Hiển thị số request & tổng chi phí sau khi xử lý xong
            st.write(f"🔄 Tổng số request API: **{total_requests}**")
            st.write(f"💰 Tổng chi phí OpenAI API: **${total_cost:.4f}**")

    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
