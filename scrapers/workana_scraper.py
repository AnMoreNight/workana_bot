"""
Selenium-based scraper for Workana job listings
"""
import time
import random
from typing import List, Dict, Optional, Set
from datetime import datetime
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import (
    BASE_URL, JOBS_URL, DEFAULT_CATEGORY, DEFAULT_LANGUAGE,
    HEADLESS, IMPLICIT_WAIT, PAGE_LOAD_TIMEOUT, EXPLICIT_WAIT_TIMEOUT,
    DELAY_BETWEEN_REQUESTS, RANDOM_DELAY_RANGE, MAX_PAGES, STOP_ON_KNOWN_JOB,
    USER_AGENT, CHROME_OPTIONS
)
from config.selectors import SELECTORS
from parsers.job_parser import parse_job_element, parse_job_element_from_html


class WorkanaScraper:
    """Selenium-based scraper for Workana job listings"""
    
    def __init__(self, headless: bool = None):
        self.headless = headless if headless is not None else HEADLESS
        self.driver = None
        self.wait = None
        self.base_url = BASE_URL
    
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        chrome_options = Options()
        
        # Add options
        for option in CHROME_OPTIONS:
            chrome_options.add_argument(option)
        
        # User agent
        chrome_options.add_argument(f'user-agent={USER_AGENT}')
        
        # Disable automation flags
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Performance optimizations - block images to load faster
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Block images
            "profile.default_content_setting_values.notifications": 2  # Block notifications
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        self.driver.implicitly_wait(IMPLICIT_WAIT)
        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        # Initialize wait
        self.wait = WebDriverWait(self.driver, EXPLICIT_WAIT_TIMEOUT)
        
        # Execute script to hide webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def build_jobs_url(self, category: str = None, language: str = None, page: int = 1) -> str:
        """Build jobs URL with parameters"""
        category = category or DEFAULT_CATEGORY
        language = language or DEFAULT_LANGUAGE
        
        # URL-encode the language parameter (handles commas and special chars)
        language_encoded = quote(language, safe='')
        
        url = f"{JOBS_URL}?category={category}&language={language_encoded}&publication=1d"
        if page > 1:
            url += f"&page={page}"
        
        return url
    
    def load_page(self, url: str) -> bool:
        """Load a page and wait for jobs to appear"""
        try:
            self.driver.get(url)
            
            # Wait for jobs container to load (more efficient wait)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS['job_container']))
            )
            
            # Wait briefly for dynamic content (reduced from 2s to 0.5s)
            time.sleep(0.5)
            
            return True
        except TimeoutException:
            print(f"Timeout loading page: {url}")
            return False
        except Exception as e:
            print(f"Error loading page {url}: {e}")
            return False
    
    def scroll_page(self):
        """Scroll page to trigger lazy loading if needed (optimized)"""
        try:
            # Quick scroll to bottom and back (reduced delays)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.3)  # Reduced from 1s
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.2)  # Reduced from 1s
        except:
            pass
    
    def get_job_elements(self) -> List:
        """Get all job elements from current page"""
        try:
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, SELECTORS['job_item'])
            return job_elements
        except Exception as e:
            print(f"Error getting job elements: {e}")
            return []
    
    def get_total_pages(self) -> Optional[int]:
        """Get total number of pages from pagination"""
        try:
            pagination = self.driver.find_element(By.CSS_SELECTOR, SELECTORS['pagination'])
            page_links = pagination.find_elements(By.CSS_SELECTOR, SELECTORS['pagination_pages'])
            
            if not page_links:
                return 1
            
            # Get the last page number
            page_numbers = []
            for link in page_links:
                try:
                    text = link.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                except:
                    continue
            
            return max(page_numbers) if page_numbers else 1
        except:
            return 1
    
    def scrape_page(self, existing_job_ids: Set[str] = None, skip_scroll: bool = False) -> tuple[List[Dict], bool]:
        """
        Scrape jobs from current page
        Returns: (list of job data, should_stop flag)
        """
        if existing_job_ids is None:
            existing_job_ids = set()
        
        jobs = []
        should_stop = False
        
        # Scroll only if needed (skip on first page load as it's already loaded)
        if not skip_scroll:
            self.scroll_page()
        
        # Get job elements
        job_elements = self.get_job_elements()
        
        if not job_elements:
            print("No job elements found on page")
            return jobs, should_stop
        
        print(f"Found {len(job_elements)} jobs on page")
        
        # Parse each job (extract HTML immediately to avoid stale element issues)
        for i, job_element in enumerate(job_elements):
            try:
                # Get HTML immediately to avoid stale element reference
                try:
                    job_html = job_element.get_attribute('outerHTML')
                except:
                    # If element is stale, re-find it
                    job_elements_refresh = self.get_job_elements()
                    if i < len(job_elements_refresh):
                        job_element = job_elements_refresh[i]
                        job_html = job_element.get_attribute('outerHTML')
                    else:
                        continue
                
                # Parse using HTML string instead of WebElement
                job_data = parse_job_element_from_html(job_html, self.base_url)
                
                # Skip if no ID
                if not job_data.get('id'):
                    continue
                
                # Build composite key for comparison: id + client_name
                job_key = f"{job_data.get('id')}|{job_data.get('client_name') or ''}"

                # Check if we should stop (if STOP_ON_KNOWN_JOB is enabled)
                if STOP_ON_KNOWN_JOB and job_key in existing_job_ids:
                    print(f"Found known job {job_data['id']} (client: {job_data.get('client_name') or 'N/A'}), stopping scrape")
                    should_stop = True
                    break
                
                jobs.append(job_data)
                
            except Exception as e:
                print(f"Error parsing job element {i+1}: {e}")
                continue
        
        return jobs, should_stop
    
    def scrape(self, category: str = None, language: str = None, 
               existing_job_ids: Set[str] = None, max_pages: int = None) -> List[Dict]:
        """
        Scrape jobs from Workana
        Returns list of all scraped jobs
        """
        if existing_job_ids is None:
            existing_job_ids = set()
        
        if max_pages is None:
            max_pages = MAX_PAGES
        
        all_jobs = []
        page = 1
        
        try:
            # Load first page
            url = self.build_jobs_url(category, language, page)
            print(f"Loading page {page}: {url}")
            
            if not self.load_page(url):
                return all_jobs
            
            # Get total pages
            total_pages = self.get_total_pages()
            print(f"Total pages: {total_pages}")
            
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            # Scrape pages
            while page <= total_pages:
                print(f"\nScraping page {page}/{total_pages}")
                
                # Scrape current page (skip scroll on first page as it's already loaded)
                skip_scroll = (page == 1)
                jobs, should_stop = self.scrape_page(existing_job_ids, skip_scroll=skip_scroll)
                all_jobs.extend(jobs)
                
                print(f"Scraped {len(jobs)} jobs from page {page}")
                
                # Stop if we found a known job
                if should_stop:
                    print("Stopping scrape: found known job")
                    break
                
                # Move to next page
                page += 1
                if page > total_pages:
                    break
                
                # Delay between pages (optimized)
                delay = DELAY_BETWEEN_REQUESTS + random.uniform(*RANDOM_DELAY_RANGE)
                if delay > 0.5:  # Only print if delay is significant
                    print(f"Waiting {delay:.1f} seconds before next page...")
                time.sleep(delay)
                
                # Load next page
                url = self.build_jobs_url(category, language, page)
                if not self.load_page(url):
                    print(f"Failed to load page {page}, stopping")
                    break
        
        except Exception as e:
            print(f"Error during scraping: {e}")
        
        return all_jobs
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None

