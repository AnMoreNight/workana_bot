"""
Parser for extracting job data from HTML elements
"""
import re
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from config.selectors import SELECTORS
from parsers.date_parser import parse_relative_date, extract_job_id_from_url


def parse_budget(budget_text: str) -> Dict[str, Optional[str]]:
    """
    Parse budget text to extract min, max, and type
    Examples:
    - "USD 50 - 100" -> {min: 50, max: 100, type: "fixed"}
    - "Over USD 45 / hour" -> {min: 45, max: None, type: "hourly"}
    - "Less than USD 50" -> {min: None, max: 50, type: "fixed"}
    """
    if not budget_text:
        return {'min': None, 'max': None, 'type': None}
    
    budget_text = budget_text.strip()
    budget_type = None
    min_val = None
    max_val = None
    
    # Check if hourly
    if '/ hour' in budget_text.lower() or 'hourly' in budget_text.lower():
        budget_type = 'hourly'
    else:
        budget_type = 'fixed'
    
    # Extract numbers (remove commas)
    numbers = re.findall(r'[\d,]+', budget_text.replace(',', ''))
    numbers = [int(n.replace(',', '')) for n in numbers]
    
    if 'over' in budget_text.lower() or 'more than' in budget_text.lower():
        if numbers:
            min_val = numbers[0]
    elif 'less than' in budget_text.lower() or 'under' in budget_text.lower():
        if numbers:
            max_val = numbers[0]
    elif len(numbers) >= 2:
        min_val = numbers[0]
        max_val = numbers[1]
    elif len(numbers) == 1:
        min_val = numbers[0]
    
    return {
        'min': min_val,
        'max': max_val,
        'type': budget_type
    }


def parse_job_element(job_element, base_url: str = "https://www.workana.com") -> Dict:
    """
    Parse a single job element and extract all available data
    Returns dictionary with job data
    """
    job_data = {}
    
    try:
        # Title and URL
        try:
            title_elem = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_title'])
            job_data['title'] = safe_get_text(title_elem)
            url_path = safe_get_attribute(title_elem, 'href')
            if url_path:
                if url_path.startswith('http'):
                    job_data['url'] = url_path
                else:
                    job_data['url'] = base_url + url_path
                job_data['id'] = extract_job_id_from_url(job_data['url'])
            else:
                job_data['url'] = None
                job_data['id'] = None
        except NoSuchElementException:
            job_data['title'] = None
            job_data['url'] = None
            job_data['id'] = None
        
        # Date
        try:
            date_elem = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_date'])
            date_text = safe_get_text(date_elem)
            job_data['posted_date_relative'] = date_text.replace('Published: ', '').strip() if date_text else None
            job_data['posted_date_timestamp'] = parse_relative_date(job_data['posted_date_relative']) if job_data['posted_date_relative'] else None
        except NoSuchElementException:
            job_data['posted_date_relative'] = None
            job_data['posted_date_timestamp'] = None
        
        # Bids count
        try:
            bids_elem = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_bids'])
            bids_text = safe_get_text(bids_elem)
            if bids_text:
                match = re.search(r'(\d+)', bids_text)
                job_data['bids_count'] = int(match.group(1)) if match else None
            else:
                job_data['bids_count'] = None
        except NoSuchElementException:
            job_data['bids_count'] = None
        
        # Description
        try:
            desc_elem = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_description'])
            job_data['description'] = safe_get_text(desc_elem)
        except NoSuchElementException:
            job_data['description'] = None
        
        # Budget
        try:
            budget_elem = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_budget'])
            budget_text = safe_get_text(budget_elem)
            job_data['budget'] = budget_text
            budget_parsed = parse_budget(budget_text)
            job_data['budget_min'] = budget_parsed['min']
            job_data['budget_max'] = budget_parsed['max']
            job_data['budget_type'] = budget_parsed['type']
        except NoSuchElementException:
            job_data['budget'] = None
            job_data['budget_min'] = None
            job_data['budget_max'] = None
            job_data['budget_type'] = None
        
        # Skills
        try:
            skill_elems = job_element.find_elements(By.CSS_SELECTOR, SELECTORS['job_skills'])
            job_data['skills'] = [safe_get_text(skill) for skill in skill_elems if safe_get_text(skill)]
        except:
            job_data['skills'] = []
        
        # Featured/Max project
        try:
            featured_badge = job_element.find_element(By.CSS_SELECTOR, SELECTORS['job_featured_badge'])
            job_data['is_max_project'] = True
        except NoSuchElementException:
            job_data['is_max_project'] = False
        
        # Check if featured (has project-item-featured class)
        classes = safe_get_attribute(job_element, 'class', '')
        job_data['is_featured'] = 'project-item-featured' in (classes or '')
        
        # Client information
        try:
            client_section = job_element.find_element(By.CSS_SELECTOR, 'div.project-author')
            
            # Client name
            try:
                name_elem = client_section.find_element(By.CSS_SELECTOR, SELECTORS['client_name'])
                job_data['client_name'] = safe_get_text(name_elem)
            except NoSuchElementException:
                job_data['client_name'] = None
            
            # Client country - get text from anchor tag inside country-name span
            try:
                # Primary: span.country > span.country-name > a
                country_elem = client_section.find_element(By.CSS_SELECTOR, SELECTORS['client_country'])
                job_data['client_country'] = safe_get_text(country_elem)
            except NoSuchElementException:
                # Fallback 1: try span.country-name > a directly
                try:
                    country_elem = client_section.find_element(By.CSS_SELECTOR, 'span.country-name > a')
                    job_data['client_country'] = safe_get_text(country_elem)
                except NoSuchElementException:
                    # Fallback 2: try span.country > a
                    try:
                        country_elem = client_section.find_element(By.CSS_SELECTOR, 'span.country > a')
                        job_data['client_country'] = safe_get_text(country_elem)
                    except NoSuchElementException:
                        job_data['client_country'] = None
            
            # Client rating - get from title attribute of stars-bg element
            try:
                # Try the stars-bg element which has the title attribute
                rating_elem = client_section.find_element(By.CSS_SELECTOR, SELECTORS['client_rating'])
                job_data['client_rating'] = extract_rating(rating_elem)
            except NoSuchElementException:
                # Fallback: try profile-stars and look for stars-bg inside
                try:
                    profile_stars = client_section.find_element(By.CSS_SELECTOR, 'span.rating > span.profile-stars')
                    stars_bg = profile_stars.find_element(By.CSS_SELECTOR, 'span.stars-bg')
                    job_data['client_rating'] = extract_rating(stars_bg)
                except NoSuchElementException:
                    job_data['client_rating'] = None
            
            # Payment verified
            try:
                verified_elem = client_section.find_element(By.CSS_SELECTOR, SELECTORS['client_payment_verified'])
                job_data['client_payment_verified'] = True
            except NoSuchElementException:
                job_data['client_payment_verified'] = False
            
            # Last reply
            try:
                reply_elem = client_section.find_element(By.CSS_SELECTOR, SELECTORS['client_last_reply'])
                reply_text = safe_get_text(reply_elem)
                # Extract just the time part (after "Last reply:")
                if reply_text:
                    parts = reply_text.split(':', 1)
                    job_data['client_last_reply'] = parts[-1].strip() if len(parts) > 1 else reply_text
                else:
                    job_data['client_last_reply'] = None
            except NoSuchElementException:
                job_data['client_last_reply'] = None
                
        except NoSuchElementException:
            job_data['client_name'] = None
            job_data['client_country'] = None
            job_data['client_rating'] = None
            job_data['client_payment_verified'] = False
            job_data['client_last_reply'] = None
    
    except Exception as e:
        # Log error but continue
        print(f"Error parsing job element: {e}")
    
    return job_data


def parse_job_element_from_html(html: str, base_url: str = "https://www.workana.com") -> Dict:
    """
    Parse a single job element from HTML string (avoids stale element issues)
    Returns dictionary with job data
    """
    job_data = {}
    
    try:
        soup = BeautifulSoup(html, 'lxml')
        
        # Title and URL
        title_elem = soup.select_one(SELECTORS['job_title'])
        if title_elem:
            job_data['title'] = title_elem.get_text(strip=True)
            url_path = title_elem.get('href', '')
            if url_path:
                if url_path.startswith('http'):
                    job_data['url'] = url_path
                else:
                    job_data['url'] = base_url + url_path
                job_data['id'] = extract_job_id_from_url(job_data['url'])
            else:
                job_data['url'] = None
                job_data['id'] = None
        else:
            job_data['title'] = None
            job_data['url'] = None
            job_data['id'] = None
        
        # Date
        date_elem = soup.select_one(SELECTORS['job_date'])
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            job_data['posted_date_relative'] = date_text.replace('Published: ', '').strip() if date_text else None
            job_data['posted_date_timestamp'] = parse_relative_date(job_data['posted_date_relative']) if job_data['posted_date_relative'] else None
        else:
            job_data['posted_date_relative'] = None
            job_data['posted_date_timestamp'] = None
        
        # Bids count
        bids_elem = soup.select_one(SELECTORS['job_bids'])
        if bids_elem:
            bids_text = bids_elem.get_text(strip=True)
            if bids_text:
                match = re.search(r'(\d+)', bids_text)
                job_data['bids_count'] = int(match.group(1)) if match else None
            else:
                job_data['bids_count'] = None
        else:
            job_data['bids_count'] = None
        
        # Description
        desc_elem = soup.select_one(SELECTORS['job_description'])
        if desc_elem:
            job_data['description'] = desc_elem.get_text(strip=True)
        else:
            job_data['description'] = None
        
        # Budget
        budget_elem = soup.select_one(SELECTORS['job_budget'])
        if budget_elem:
            budget_text = budget_elem.get_text(strip=True)
            job_data['budget'] = budget_text
            budget_parsed = parse_budget(budget_text)
            job_data['budget_min'] = budget_parsed['min']
            job_data['budget_max'] = budget_parsed['max']
            job_data['budget_type'] = budget_parsed['type']
        else:
            job_data['budget'] = None
            job_data['budget_min'] = None
            job_data['budget_max'] = None
            job_data['budget_type'] = None
        
        # Skills
        skill_elems = soup.select(SELECTORS['job_skills'])
        job_data['skills'] = [skill.get_text(strip=True) for skill in skill_elems if skill.get_text(strip=True)]
        
        # Featured/Max project
        featured_badge = soup.select_one(SELECTORS['job_featured_badge'])
        job_data['is_max_project'] = featured_badge is not None
        
        # Check if featured (has project-item-featured class)
        main_elem = soup.select_one('.project-item')
        classes = main_elem.get('class', []) if main_elem else []
        job_data['is_featured'] = 'project-item-featured' in classes
        
        # Client information
        client_section = soup.select_one('div.project-author')
        if client_section:
            # Client name
            name_elem = client_section.select_one(SELECTORS['client_name'])
            job_data['client_name'] = name_elem.get_text(strip=True) if name_elem else None
            
            # Client country - get text from anchor tag inside country-name span
            country_elem = client_section.select_one(SELECTORS['client_country'])
            if country_elem:
                job_data['client_country'] = country_elem.get_text(strip=True)
            else:
                # Fallback 1: try span.country-name > a directly
                country_elem = client_section.select_one('span.country-name > a')
                if country_elem:
                    job_data['client_country'] = country_elem.get_text(strip=True)
                else:
                    # Fallback 2: try span.country > a
                    country_elem = client_section.select_one('span.country > a')
                    job_data['client_country'] = country_elem.get_text(strip=True) if country_elem else None
            
            # Client rating - get from title attribute of stars-bg element
            rating_elem = client_section.select_one(SELECTORS['client_rating'])
            if rating_elem:
                title_attr = rating_elem.get('title', '')
                if title_attr:
                    # Extract first number from title like "0.00 of 5.00"
                    match = re.search(r'(\d+\.?\d*)', title_attr)
                    job_data['client_rating'] = float(match.group(1)) if match else None
                else:
                    job_data['client_rating'] = None
            else:
                # Fallback: try to find stars-bg inside profile-stars
                profile_stars = client_section.select_one('span.rating > span.profile-stars')
                if profile_stars:
                    stars_bg = profile_stars.select_one('span.stars-bg')
                    if stars_bg:
                        title_attr = stars_bg.get('title', '')
                        if title_attr:
                            match = re.search(r'(\d+\.?\d*)', title_attr)
                            job_data['client_rating'] = float(match.group(1)) if match else None
                        else:
                            job_data['client_rating'] = None
                    else:
                        job_data['client_rating'] = None
                else:
                    job_data['client_rating'] = None
            
            # Payment verified
            verified_elem = client_section.select_one(SELECTORS['client_payment_verified'])
            job_data['client_payment_verified'] = verified_elem is not None
            
            # Last reply
            reply_elem = client_section.select_one(SELECTORS['client_last_reply'])
            if reply_elem:
                reply_text = reply_elem.get_text(strip=True)
                if reply_text:
                    parts = reply_text.split(':', 1)
                    job_data['client_last_reply'] = parts[-1].strip() if len(parts) > 1 else reply_text
                else:
                    job_data['client_last_reply'] = None
            else:
                job_data['client_last_reply'] = None
        else:
            job_data['client_name'] = None
            job_data['client_country'] = None
            job_data['client_rating'] = None
            job_data['client_payment_verified'] = False
            job_data['client_last_reply'] = None
    
    except Exception as e:
        print(f"Error parsing job HTML: {e}")
    
    return job_data

