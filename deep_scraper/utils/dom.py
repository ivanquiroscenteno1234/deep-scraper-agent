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
    simplified_html_parts = []
    
    for tag in interactables:
        clean_attrs(tag)
        
        # specific handling for 'a' tags - only keep if they have text
        if tag.name == 'a':
            text = tag.get_text(strip=True)
            if not text:
                continue
        
        # Add to output
        simplified_html_parts.append(str(tag))

    if simplified_html_parts:
        simplified_html = "\n".join(simplified_html_parts) + "\n"
    else:
        simplified_html = ""

    # Also keep some structural context if possible (like headers to identify sections)
    # But for a strict interactable list, the above loop is good.
    # Let's try to preserve a BIT of structure by traversing and keeping only what matters?
    
    # BETTER APPROACH: Traverse and prune non-interactables?
    # No, extracting a flat list of interactables is often better for "Action Selection" agents
    # as long as we have the screenshot for visual context.
    
    return simplified_html

def get_interactive_map(page) -> str:
    """
    Returns a simplified representation of the page's interactive elements using Playwright,
    including bounding boxes obtained via JS injection.
    """
    js_script = """
    () => {
        const interactables = Array.from(document.querySelectorAll('input, button, select, textarea, a, label'));
        const elements = [];

        for (const el of interactables) {
            const rect = el.getBoundingClientRect();

            // Skip elements that are not visible (width or height is 0)
            if (rect.width === 0 || rect.height === 0) {
                continue;
            }

            // For 'a' tags, skip if they have no text
            if (el.tagName.toLowerCase() === 'a' && !el.innerText.trim()) {
                continue;
            }

            const attrs = {};
            const allowedAttrs = ['id', 'name', 'type', 'placeholder', 'value', 'aria-label', 'role', 'class', 'href'];
            for (const attr of allowedAttrs) {
                if (el.hasAttribute(attr)) {
                    attrs[attr] = el.getAttribute(attr);
                }
            }

            elements.push({
                tag: el.tagName.toLowerCase(),
                attrs: attrs,
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                text: el.innerText ? el.innerText.trim() : ''
            });
        }
        return elements;
    }
    """

    # The current codebase uses the sync API for Playwright in this context
    # (as seen in the original `page.content()`). Thus evaluate should be called synchronously.
    elements_data = page.evaluate(js_script)

    if not elements_data:
        return ""

    simplified_html_parts = []
    for data in elements_data:
        tag = data['tag']
        attrs_str = " ".join([f'{k}="{v}"' for k, v in data.get('attrs', {}).items()])

        # Build a bounding box attribute string
        bbox_str = f'x="{data["x"]}" y="{data["y"]}" width="{data["width"]}" height="{data["height"]}"'

        # Combine attributes and bbox
        all_attrs = f"{attrs_str} {bbox_str}".strip()

        text = data.get('text', '')

        if tag in ['input']:
            simplified_html_parts.append(f"<{tag} {all_attrs}>")
        else:
            if text:
                simplified_html_parts.append(f"<{tag} {all_attrs}>{text}</{tag}>")
            else:
                simplified_html_parts.append(f"<{tag} {all_attrs}></{tag}>")

    return "\n".join(simplified_html_parts) + "\n"
