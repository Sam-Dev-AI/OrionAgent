import os   
import csv
import json
import re
import requests
from datetime import datetime
from orionagent import Agent, Gemini, tool

# 1. API KEY CONFIGURATION
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

# 2. DEFINE INDUSTRIAL CUSTOM TOOLS
@tool
def scrape_website(url: str):
    """Deep-scrapes a website to extract real business intelligence and contact info.
    
    Args:
        url: The target website URL (must start with http/https).
    """
    import trafilatura
    from bs4 import BeautifulSoup
    
    if not url.startswith("http"):
        url = "https://" + url
        
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "OrionAgent/1.0"})
        response.raise_for_status()
        
        # 1. Extract Clean Text with Trafilatura
        downloaded = response.text
        text_content = trafilatura.extract(downloaded) or "No text content found."
        
        # 2. Extract Metadata with BeautifulSoup
        soup = BeautifulSoup(downloaded, 'html.parser')
        title = soup.title.string if soup.title else "No Title"
        meta_desc = ""
        if soup.find("meta", attrs={"name": "description"}):
            meta_desc = soup.find("meta", attrs={"name": "description"})["content"]
            
        # 3. Extract Emails & Phones with Regex
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        
        emails = list(set(re.findall(email_pattern, downloaded)))
        phones = list(set(re.findall(phone_pattern, downloaded)))
        
        result = {
            "url": url,
            "title": title.strip(),
            "description": meta_desc.strip(),
            "emails": emails[:5],   # Top 5 unique emails
            "phones": phones[:5],   # Top 5 unique phones
            "body_snippet": text_content[:1500] + "...", # First 1500 chars for LLM context
            "scraped_at": datetime.now().isoformat()
        }
        
        return f"REAL SCRAPE SUCCESS for {url}:\n{json.dumps(result, indent=2)}"
        
    except Exception as e:
        return f"Scraper Error for {url}: {str(e)}"

@tool
def save_leads_to_csv(leads_json: str, filename: str = "leads_export.csv"):
    """Saves specialized business leads into an Excel-compatible CSV file.
    
    Args:
        leads_json: A JSON string containing lead data to save.
        filename: The output filename (default: leads_export.csv).
    """
    try:
        # LLMs sometimes output with markdown blocks, clean it first
        clean_json = re.sub(r'```json\n|\n```|```', '', leads_json).strip()
        data = json.loads(clean_json)
        
        if not isinstance(data, list):
            data = [data]
            
        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerows(data)
            
        return f"Successfully saved {len(data)} leads to {os.path.abspath(filename)}"
    except Exception as e:
        return f"Error saving leads: {str(e)}"

def main():
    # 3. INITIALIZE THE CORE ENGINE (Using Gemini 2.5 Flash)
    llm = Gemini(model_name="gemini-2.5-flash", token_count=True, debug=True)

    # 4. DEFINE THE 'VANGUARD' AGENT
    agent = Agent(
        name="Vanguard-Industrial",
        role="Lead Generation & Business Intelligence Specialist",
        system_instruction=(
            "You are an industrial-grade intelligence agent. Your mission is to find, "
            "analyze, and organize business leads with surgical precision.\n"
            "1. Use 'scrape_website' to gather REAL intelligence from target URLs.\n"
            "2. Extract the business name, contacts, and niche from the scraped body.\n"
            "3. Use 'save_leads_to_csv' to persist findings for the client.\n"
            "Be extremely tool-reliant and data-driven."
        ),
        model=llm,
        memory="long_term",
        use_default_tools=True,
        tools=[scrape_website, save_leads_to_csv],
        verbose=True,
        debug=True,
    )

    print("\n" + "="*60)
    print("ORIONAGENT: REAL-WORLD SCRAPING & LEAD MANAGEMENT")
    print("="*60)
    print("COMMANDS: Type 'exit' to quit.\n")

    # 5. START INTERACTIVE CHAT
    welcome_msg = (
        "System Online. Vanguard-Industrial ready. "
        "Try: 'Scrape https://www.google.com and save the info to my leads file.'"
    )
    agent.chat(welcome_msg)

if __name__ == "__main__":
    main()
