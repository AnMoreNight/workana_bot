"""
Text summarization utility for job descriptions
"""
import re
from typing import Optional


def summarize_text(text: str, max_sentences: int = 3, max_length: int = 300) -> str:
    """
    Summarize text by extracting key sentences
    
    Args:
        text: Text to summarize
        max_sentences: Maximum number of sentences to include
        max_length: Maximum character length
    
    Returns:
        Summarized text
    """
    if not text:
        return ""
    
    # Clean text
    text = text.strip()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # If text is already short, return as is
    if len(text) <= max_length:
        return text
    
    # Split into sentences
    # Simple sentence splitting (period, exclamation, question mark)
    sentences = re.split(r'[.!?]+\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        # Fallback: just truncate
        return text[:max_length] + "..."
    
    # If we have few sentences, return them
    if len(sentences) <= max_sentences:
        summary = '. '.join(sentences)
        if not summary.endswith('.'):
            summary += '.'
        return summary[:max_length] + "..." if len(summary) > max_length else summary
    
    # Take first few sentences (usually most important)
    summary_sentences = sentences[:max_sentences]
    summary = '. '.join(summary_sentences)
    
    # Ensure it ends with period
    if not summary.endswith('.'):
        summary += '.'
    
    # Truncate if still too long
    if len(summary) > max_length:
        # Find last complete sentence within limit
        truncated = summary[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.7:  # If period is reasonably close
            summary = truncated[:last_period + 1]
        else:
            summary = truncated + "..."
    
    return summary


def extract_key_points(text: str, max_points: int = 3) -> list:
    """
    Extract key points/bullet points from text
    
    Args:
        text: Text to analyze
        max_points: Maximum number of key points
    
    Returns:
        List of key points
    """
    if not text:
        return []
    
    key_points = []
    
    # Look for bullet points or numbered lists
    bullet_pattern = r'[-•*]\s+(.+?)(?=\n|$)'
    bullets = re.findall(bullet_pattern, text, re.MULTILINE)
    
    if bullets:
        key_points = [b.strip() for b in bullets[:max_points]]
        return key_points
    
    # Look for numbered lists
    numbered_pattern = r'\d+[.)]\s+(.+?)(?=\n|$)'
    numbered = re.findall(numbered_pattern, text, re.MULTILINE)
    
    if numbered:
        key_points = [n.strip() for n in numbered[:max_points]]
        return key_points
    
    # If no bullets, extract important sentences (those with keywords)
    important_keywords = ['need', 'required', 'must', 'should', 'looking for', 
                         'experience', 'skills', 'develop', 'create', 'build']
    
    sentences = re.split(r'[.!?]+\s+', text)
    important_sentences = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in important_keywords):
            important_sentences.append(sentence.strip())
            if len(important_sentences) >= max_points:
                break
    
    return important_sentences[:max_points]


def summarize_job_description(description: str, include_key_points: bool = True) -> dict:
    """
    Create a comprehensive summary of job description
    
    Args:
        description: Full job description
        include_key_points: Whether to extract key points
    
    Returns:
        Dictionary with 'summary' and optionally 'key_points'
    """
    if not description:
        return {'summary': '', 'key_points': []}
    
    result = {
        'summary': summarize_text(description, max_sentences=3, max_length=250),
        'key_points': []
    }
    
    if include_key_points:
        result['key_points'] = extract_key_points(description, max_points=3)
    
    return result

