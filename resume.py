import streamlit as st
from dotenv import load_dotenv
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
import PyPDF2
import docx2txt
import re
import time


load_dotenv()


if not os.environ.get("GOOGLE_API_KEY"):
    st.error("⚠️ GOOGLE_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()


@st.cache_resource
def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        temperature=0.2,  
        max_tokens=4096,
        timeout=60,
        max_retries=3,
    )


def extract_text(file):
    try:
        if file.type == "application/pdf":
            reader = PyPDF2.PdfReader(file)
            text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
            if not text.strip():
                return "Error: Could not extract text from PDF. The PDF might be scanned or image-based."
            return text
        elif file.type in ["text/plain", "application/octet-stream"]:
            return file.read().decode("utf-8")
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return docx2txt.process(file)
        else:
            return f"Unsupported file type: {file.type}"
    except Exception as e:
        return f"Error extracting text: {str(e)}"


prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert ATS (Applicant Tracking System) AI and career coach with extensive HR knowledge.
Your task is to thoroughly analyze a resume against a job description and provide detailed feedback.
Be precise, honest, and actionable in your assessment.
Focus on keyword matching, experience alignment, skills gap analysis, and overall presentation.
"""),
    ("human", """
Resume:
{resume}

Job Description:
{job}

Perform a comprehensive analysis of how well this resume matches the job description.

Return your analysis in this exact format:

Match Score: <score out of 100>

Key Strengths:
• <strength 1>
• <strength 2>
• <strength 3>
• <additional strengths as needed>

Areas for Improvement:
• <improvement 1>
• <improvement 2>
• <improvement 3>
• <additional improvements as needed>

Keywords Missing:
• <missing keyword 1>
• <missing keyword 2>
• <additional missing keywords as needed>

Summary:
<2-3 sentence conclusion with your overall assessment and most important next steps>
""")
])


def extract_section(text, section_name, next_section=None):
    pattern = f"{section_name}:(.*?){next_section}:" if next_section else f"{section_name}:(.*?)$"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        
        lines = text.split('\n')
        section_start = -1
        section_end = -1
        
        for i, line in enumerate(lines):
            if section_name in line:
                section_start = i
            elif section_start != -1 and next_section and next_section in line:
                section_end = i
                break
        
        if section_start != -1:
            if section_end != -1:
                return '\n'.join(lines[section_start+1:section_end]).strip()
            else:
                return '\n'.join(lines[section_start+1:]).strip()
                
    return "❌ Could not extract this section properly."


def extract_score(text):
   
    patterns = [
        r"Match Score:\s*(\d+)",
        r"Score:\s*(\d+)",
        r"(\d+)/100",
        r"(\d+)\s*out of\s*100",
        r"(\d+)\s*\/\s*100"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                score = int(match.group(1))
                if 0 <= score <= 100:
                    return score
            except ValueError:
                continue
    
    return None


st.set_page_config(page_title="Resume Matcher AI", page_icon="🧠", layout="wide")

with st.container():
    st.title("🚀 Resume Matcher AI (Gemini Powered)")
    st.markdown("""
    Upload your resume and paste a job description to get an AI-powered analysis of how well you match the position.
    The system will identify your strengths, areas for improvement, and missing keywords.
    """)

col1, col2 = st.columns(2)

with col1:
    resume_file = st.file_uploader("📄 Upload Your Resume (PDF, TXT, or DOCX)", type=["pdf", "txt", "docx"])
    if resume_file:
        file_details = {"Filename": resume_file.name, "FileType": resume_file.type, "FileSize": f"{resume_file.size/1024:.2f} KB"}
        st.write(file_details)

with col2:
    job_text = st.text_area("📝 Paste Job Description Here", height=250, placeholder="Enter the full job description here...")

analyze_button = st.button("🔍 Analyze Resume Match", type="primary", use_container_width=True)

if analyze_button and resume_file and job_text.strip():
    resume_text = extract_text(resume_file)
    
    if resume_text.startswith("Error:"):
        st.error(resume_text)
    else:
        with st.spinner("⏳ Analyzing your resume against the job description... This may take a moment."):
            try:
                llm = get_llm()
                chain = prompt | llm | StrOutputParser()
                
                
                time.sleep(1)
                
               
                result = chain.invoke({'resume': resume_text, 'job': job_text})
                
                
                score = extract_score(result)
                key_strengths = extract_section(result, "Key Strengths", "Areas for Improvement")
                areas_for_improvement = extract_section(result, "Areas for Improvement", "Keywords Missing")
                missing_keywords = extract_section(result, "Keywords Missing", "Summary")
                summary = extract_section(result, "Summary")
                
                
                progress_bar = st.progress(0)
                for i in range(100):
                    progress_bar.progress(i + 1)
                    time.sleep(0.01)
                
                st.success("✅ Analysis Complete!")
                
                
                st.markdown("## Results")
                
                
                score_col1, score_col2 = st.columns([1, 3])
                with score_col1:
                    if score is not None:
                        st.markdown(f"### 💯 Match Score: {score}/100")
                with score_col2:
                    if score is not None:
                        
                        if score >= 80:
                            color = "green"
                            message = "Excellent match!"
                        elif score >= 60:
                            color = "orange"
                            message = "Good match with room for improvement"
                        else:
                            color = "red"
                            message = "Significant improvements needed"
                        
                        st.markdown(f"""
                        <div style="width:100%; background-color:#f0f0f0; height:20px; border-radius:10px;">
                            <div style="width:{score}%; background-color:{color}; height:20px; border-radius:10px;"></div>
                        </div>
                        <p style="color:{color}; font-weight:bold;">{message}</p>
                        """, unsafe_allow_html=True)
                
                st.divider()
                
                
                with st.expander("🟢 Key Strengths", expanded=True):
                    st.markdown(key_strengths.replace("• ", "* "))
                
                with st.expander("🟡 Areas for Improvement", expanded=True):
                    st.markdown(areas_for_improvement.replace("• ", "* "))
                
                with st.expander("🎯 Keywords Missing", expanded=True):
                    st.markdown(missing_keywords.replace("• ", "* "))
                
                st.subheader("📊 Summary")
                st.info(summary)
                
                
                with st.expander("🧪 Raw AI Response (Debug Mode)", expanded=False):
                    st.code(result)
                
                
                analysis_text = f"""
                RESUME MATCHER AI ANALYSIS
                -------------------------
                
                MATCH SCORE: {score}/100
                
                KEY STRENGTHS:
                {key_strengths}
                
                AREAS FOR IMPROVEMENT:
                {areas_for_improvement}
                
                KEYWORDS MISSING:
                {missing_keywords}
                
                SUMMARY:
                {summary}
                """
                
                st.download_button(
                    label="📥 Download Analysis Report",
                    data=analysis_text,
                    file_name=f"resume_analysis_{resume_file.name.split('.')[0]}.txt",
                    mime="text/plain",
                )
                
                
                st.divider()
                st.subheader("💡 Next Steps")
                st.markdown("""
                1. **Update your resume** with the missing keywords where applicable
                2. **Quantify your achievements** with numbers and metrics
                3. **Tailor your resume** specifically for this job
                4. **Create a targeted cover letter** that addresses the gaps
                """)
                
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
                st.info("Please try again with a different resume format or check your API key.")
elif analyze_button:
    st.warning("⚠️ Please upload both a resume and job description to start the analysis.")
else:
    st.info("📥 Upload your resume and paste a job description, then click 'Analyze Resume Match'.")


st.markdown("""
---
💼 **Resume Matcher AI** - Get insights on how well your resume matches job descriptions
""")