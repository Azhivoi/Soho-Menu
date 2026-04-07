"""
Import existing HTML pages content into CMS
"""

import re
from fastapi import APIRouter, HTTPException
from bs4 import BeautifulSoup
import json

router = APIRouter(prefix="/content/import", tags=["content-import"])

def extract_content_from_html(file_path):
    """Extract content from existing HTML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.text.split(' - ')[0] if title_tag else ''
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_description = meta_desc.get('content', '') if meta_desc else ''
        
        # Extract main content
        content_parts = []
        
        # Find main content area
        main_content = soup.find('main') or soup.find('div', class_='content') or soup.find('div', class_='page-content')
        
        if main_content:
            # Extract text content with structure
            for elem in main_content.find_all(['h1', 'h2', 'h3', 'p', 'div']):
                if elem.name == 'h1':
                    content_parts.append(f'<h1>{elem.get_text(strip=True)}</h1>')
                elif elem.name == 'h2':
                    content_parts.append(f'<h2>{elem.get_text(strip=True)}</h2>')
                elif elem.name == 'h3':
                    content_parts.append(f'<h3>{elem.get_text(strip=True)}</h3>')
                elif elem.name == 'p':
                    text = elem.get_text(strip=True)
                    if text and len(text) > 20:  # Skip empty or very short paragraphs
                        content_parts.append(f'<p>{text}</p>')
                elif elem.get('class') and 'about-text' in elem.get('class'):
                    # Special handling for about page
                    for p in elem.find_all('p'):
                        text = p.get_text(strip=True)
                        if text:
                            content_parts.append(f'<p>{text}</p>')
        
        # If no main content found, try to extract from body
        if not content_parts:
            body = soup.find('body')
            if body:
                # Get all paragraphs
                for p in body.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        content_parts.append(f'<p>{text}</p>')
        
        content = '\n'.join(content_parts[:20])  # Limit to first 20 elements
        
        return {
            'title': title,
            'metaDescription': meta_description,
            'content': content if content else '<p>Содержимое страницы</p>'
        }
    except Exception as e:
        print(f"Error extracting from {file_path}: {e}")
        return None

@router.post("/from-html")
async def import_from_html():
    """Import content from existing HTML pages"""
    
    pages_to_import = {
        'about': '/opt/soho/frontend/about.html',
        'delivery': '/opt/soho/frontend/delivery.html',
        'promotions': '/opt/soho/frontend/promotions.html',
        'support': '/opt/soho/frontend/support.html',
        'offer': '/opt/soho/frontend/offer.html',
        'index': '/opt/soho/frontend/index.html'
    }
    
    imported = []
    errors = []
    
    for page_id, file_path in pages_to_import.items():
        try:
            data = extract_content_from_html(file_path)
            if data:
                imported.append({
                    'id': page_id,
                    **data
                })
            else:
                errors.append(f"Failed to extract {page_id}")
        except Exception as e:
            errors.append(f"{page_id}: {str(e)}")
    
    return {
        "status": "ok",
        "imported": len(imported),
        "pages": imported,
        "errors": errors
}