"""
CSS selectors for Workana job listings
"""
SELECTORS = {
    # Container
    'job_container': '#projects',
    'job_item': '.project-item.js-project',
    'job_item_featured': '.project-item.js-project.project-item-featured',
    
    # Job Information
    'job_title': 'h2.h3.project-title > span > a',
    'job_url': 'h2.h3.project-title > span > a',  # href attribute
    'job_date': 'div.project-main-details > span.date',
    'job_bids': 'div.project-main-details > span.bids',
    'job_description': 'div.html-desc.project-details > div > p',
    'job_budget': 'p.budget.h4 > span.values > span',
    'job_skills': 'div.skills > div > a.skill.label.label-info > h3',
    'job_featured_badge': 'span.label.label-max',
    
    # Client Information
    'client_name': 'div.project-author > span.author-info > button',
    'client_country': 'div.project-author > span.country > span.country-name > a',  # Country name is in anchor tag inside country-name span
    'client_rating': 'div.project-author > span.rating > span.profile-stars > span.stars-bg',  # title attribute is on stars-bg
    'client_payment_verified': 'div.project-author > span.payment > span.payment-verified',
    'client_last_reply': 'div.project-author > span.message-created > span',
    
    # Pagination
    'pagination': 'nav.text-center > ul.pagination',
    'pagination_pages': 'ul.pagination > li > a',
    'pagination_current': 'ul.pagination > li.active > a',
    'pagination_next': 'ul.pagination > li:not(.disabled) > a[aria-label="Next"]',
}

