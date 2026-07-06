import os
import time
import re
import logging
import pandas as pd
import subprocess
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Auto install deps
def install_deps():
    core_deps = {
        'selenium': 'selenium==4.15.2',
        'beautifulsoup4': 'beautifulsoup4',
        'pandas': 'pandas',
        'fake_useragent': 'fake-useragent',
        'webdriver-manager': 'webdriver-manager',
        'openpyxl': 'openpyxl'
    }
    for name, pkg in core_deps.items():
        try:
            __import__(name)
            print(f"✓ {name} ready")
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])

install_deps()

# Reload if needed
try:
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from bs4 import BeautifulSoup
except:
    print("Restart after deps install")
    exit()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.wait = None
        self.driver = None
        
    def setup_driver(self, headless=True):
        options = Options()
        options.add_argument(f'--user-agent={self.ua.random}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        if headless:
            options.add_argument('--headless=new')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
        logger.info("Driver ready")
    
    def login(self):
        logger.info("Open Chrome - login to LinkedIn manually, then press Enter here...")
        self.setup_driver(headless=False)
        self.driver.get('https://www.linkedin.com/feed/')
        input("After login, press Enter to continue...")
        logger.info("Logged in")
        return True
    
    def scrape_company_leads(self, company_url, max_profiles=20):
        leads = []
        self.driver.get(company_url)
        time.sleep(5)
        
        # Try multiple people tab selectors
        people_selectors = [
            "//a[contains(@href,'/people/')]",
            "//a[contains(@aria-label,'People')]",
            "//button[contains(text(),'People')]",
            "//a[contains(text(),'People')]"
        ]
        
        people_tab = None
        for selector in people_selectors:
            try:
                people_tab = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                people_tab.click()
                logger.info("People tab clicked")
                time.sleep(5)
                break
            except:
                continue
        
        if not people_tab:
            logger.warning("People tab not found - scraping current page")
        
        # Scroll and scrape
        profiles_scraped = 0
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while profiles_scraped < max_profiles:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(3)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logger.info("End of page reached")
                break
            last_height = new_height
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            cards = soup.find_all('div', {'class': re.compile(r'repeater|entity-result|card')})
            
            for card in cards:
                if profiles_scraped >= max_profiles:
                    break
                try:
                    # Robust name/title/link extraction
                    name = card.find('span', string=re.compile(r'.{2,}')) or card.get_text()[:50].strip()
                    if len(name) < 2:
                        continue
                    
                    link = card.find('a', href=re.compile(r'/in/'))
                    if link:
                        profile_url = 'https://www.linkedin.com' + link['href']
                        title = card.get_text().split('\n')[1] if '\n' in card.get_text() else ''
                        
                        leads.append({
                            'name': name.strip(),
                            'title': title.strip(),
                            'profile_url': profile_url,
                            'company': company_url.split('/')[-1].title()
                        })
                        profiles_scraped += 1
                except:
                    continue
            
            logger.info(f"Found {profiles_scraped} profiles...")
        
        self.driver.quit()
        logger.info(f"Scraping complete: {len(leads)} leads")
        return pd.DataFrame(leads)
    
    def generate_emails(self, df):
        emails = []
        for _, row in df.iterrows():
            name = row['name'].lower()
            company = row['company'].lower().replace(' ', '')
            patterns = [
                name.replace(' ', '.') + f'@{company}.com',
                name[0] + name.split()[-1] + f'@{company}.com',
            ]
            emails.append(patterns[0])
        df['email'] = emails
        return df

def main():
    print("🚀 ULTIMATE LINKEDIN LEAD GENERATOR v2.0")
    print("1. Auto installs deps")
    print("2. Manual login (safer)")
    print("3. Robust scraping")
    
    scraper = LinkedInScraper()
    
    if not scraper.login():
        return
    
    company_url = input("\nEnter company URL: ").strip() or "https://www.linkedin.com/company/google"
    
    logger.info("Starting scrape...")
    leads = scraper.scrape_company_leads(company_url)
    
    if not leads.empty:
        leads = scraper.generate_emails(leads)
        filename = f"linkedin_leads_{int(time.time())}.xlsx"
        leads.to_excel(filename, index=False)
        print(f"\n✅ SUCCESS! {len(leads)} leads saved to {filename}")
        print(leads[['name', 'title', 'email', 'profile_url']])
    else:
        print("No leads found - try different company")

if __name__ == "__main__":
    main()
