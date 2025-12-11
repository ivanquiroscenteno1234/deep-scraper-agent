from bs4 import BeautifulSoup
import re

def simplify_dom(html_content: str) -> str:
    """
    Simplifies the HTML DOM to only include interactive elements and essential structure.
    This reduces the token count for the LLM and removes noise.
    
    Keeps:
    - input (with type, name, id, placeholder, value)
    - button (with text, id, type)
    - select (with name, id)
    - a (with href, text - only if they look like buttons or nav)
    - labels
    """
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Remove script, style, meta, head, svg, path, etc.
    for tag in soup(['script', 'style', 'meta', 'head', 'svg', 'path', 'noscript', 'iframe', 'link']):
        tag.decompose()
        
    # Remove hidden inputs
    for tag in soup.find_all('input', type='hidden'):
        tag.decompose()
        
    # Helper to clean attributes
    def clean_attrs(tag):
        allowed_attrs = ['id', 'name', 'type', 'placeholder', 'value', 'aria-label', 'role', 'class']
        attrs = dict(tag.attrs)
        tag.attrs = {k: v for k, v in attrs.items() if k in allowed_attrs}
        # Simplify classes - keep only meaningful ones if needed, or just remove for now to save space
        # For now, we keep unique classes just in case
        if 'class' in tag.attrs:
            tag.attrs['class'] = ' '.join(tag.attrs['class'])
        
    # Interactable tags we care about
    interactables = soup.find_all(['input', 'button', 'select', 'textarea', 'a', 'label'])
    
    # Process interactables
    simplified_html = ""
    
    for tag in interactables:
        clean_attrs(tag)
        
        # specific handling for 'a' tags - only keep if they have text
        if tag.name == 'a':
            text = tag.get_text(strip=True)
            if not text:
                continue
        
        # Add to output
        simplified_html += str(tag) + "\n"
        
    # Also keep some structural context if possible (like headers to identify sections)
    # But for a strict interactable list, the above loop is good.
    # Let's try to preserve a BIT of structure by traversing and keeping only what matters?
    
    # BETTER APPROACH: Traverse and prune non-interactables?
    # No, extracting a flat list of interactables is often better for "Action Selection" agents
    # as long as we have the screenshot for visual context.
    
    return simplified_html

def get_interactive_map(page) -> str:
    """
    Returns a simplified representation of the page's interactive elements using Playwright.
    """
    # We can inject JS to get a better list with bounding boxes if needed later.
    # For now, we'll use BS4 on the content.
    content = page.content()
    return simplify_dom(content)
