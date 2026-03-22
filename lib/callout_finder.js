"""
callout_finder.js - Robust DOM element finder for callout box placement.

Given a description of what to highlight (e.g., "the Secrets menu item",
"the Generate/Import button"), finds the exact bounding box including
icons, indicators, and adjacent decorative elements.

Returns coordinates that include the FULL visual extent of the UI element,
not just its text node.

Run via: playwright-cli run-code "$(Get-Content lib/callout_finder.js -Raw)"
Pass targets as an argument.
"""
async page => {
  // Accepts an array of target descriptions to find
  // Each target: { text: "Secrets", role: "menuitem|button|link", area: "nav|toolbar|content" }
  const targets = TARGETS_PLACEHOLDER;
  
  const results = {};
  const frames = page.frames();
  
  for (const target of targets) {
    let bestMatch = null;
    
    for (const frame of frames) {
      try {
        const match = await frame.evaluate((t) => {
          // Strategy: find elements matching the target text, then expand
          // the bounding box to include the full "visual unit" (icon + text + container)
          
          // Detect whether an element lives inside a form field row
          function isFormFieldElement(el) {
            let node = el;
            for (let i = 0; i < 8 && node; i++) {
              const cls = (node.className || '').toString().toLowerCase();
              const tag = node.tagName ? node.tagName.toLowerCase() : '';
              if (
                tag === 'input' || tag === 'textarea' ||
                cls.includes('azc-formelement') || cls.includes('azc-input') ||
                cls.includes('msla-input') || cls.includes('fxc-textbox') ||
                cls.includes('fxc-input') || cls.includes('fxs-input')
              ) {
                return true;
              }
              node = node.parentElement;
            }
            return false;
          }

          // Find the bounding box for a form field row: input + adjacent action buttons.
          // Returns a union rect covering the label, input, and any copy/show/regenerate buttons.
          function findFormFieldBounds(el) {
            // Walk up to find the form row container
            let row = el;
            for (let i = 0; i < 10 && row.parentElement; i++) {
              row = row.parentElement;
              const cls = (row.className || '').toString().toLowerCase();
              if (
                cls.includes('azc-formelementcontainer') ||
                cls.includes('fxc-base') ||
                cls.includes('msla-input') ||
                cls.includes('fxs-input-container') ||
                cls.includes('azc-formgroup')
              ) {
                break;
              }
            }

            // Gather all interactive children: inputs, buttons, role=button elements
            const interactiveChildren = row.querySelectorAll(
              'input, textarea, button, [role="button"], .fxc-textbox, .azc-input, [class*="copy"], [class*="action"]'
            );
            if (interactiveChildren.length === 0) return null;

            // Compute the union of all their bounding rects
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let visibleCount = 0;
            for (const child of interactiveChildren) {
              const r = child.getBoundingClientRect();
              if (r.width === 0 || r.height === 0) continue;
              if (r.top > window.innerHeight || r.bottom < 0) continue;
              visibleCount++;
              minX = Math.min(minX, r.left);
              minY = Math.min(minY, r.top);
              maxX = Math.max(maxX, r.right);
              maxY = Math.max(maxY, r.bottom);
            }
            if (visibleCount === 0) return null;

            // Also include any label that sits above or to the left of the field
            const labels = row.querySelectorAll('label, .azc-formLabel, [class*="label"]');
            for (const lbl of labels) {
              const r = lbl.getBoundingClientRect();
              if (r.width === 0 || r.height === 0) continue;
              minX = Math.min(minX, r.left);
              minY = Math.min(minY, r.top);
              maxX = Math.max(maxX, r.right);
              maxY = Math.max(maxY, r.bottom);
            }

            const pad = 4;
            const unionWidth = (maxX - minX) + (pad * 2);
            const unionHeight = (maxY - minY) + (pad * 2);

            // Reject if the result is still unreasonably wide
            if (unionWidth > window.innerWidth * 0.8) return null;

            return {
              x: Math.round(minX - pad),
              y: Math.round(minY - pad),
              width: Math.round(unionWidth),
              height: Math.round(unionHeight),
              element: row.tagName,
              text: row.textContent.trim().substring(0, 50),
            };
          }

          function getVisualBounds(el) {
            // If this element is inside a form field, try the form-field strategy first
            if (isFormFieldElement(el)) {
              const formBounds = findFormFieldBounds(el);
              if (formBounds) return formBounds;
            }

            // Walk up to find the smallest interactive/visual container
            // that represents the full UI element (not just the text span)
            let current = el;
            const textRect = el.getBoundingClientRect();
            let bestContainer = el;
            let bestRect = textRect;
            
            // Walk up ancestors looking for the interactive container
            for (let i = 0; i < 5 && current.parentElement; i++) {
              current = current.parentElement;
              const tag = current.tagName.toLowerCase();
              const role = current.getAttribute('role') || '';
              const cls = (current.className || '').toString().toLowerCase();
              
              // Stop at common interactive container patterns
              const isContainer = (
                tag === 'a' || tag === 'button' || tag === 'li' ||
                role === 'menuitem' || role === 'treeitem' || role === 'button' ||
                role === 'tab' || role === 'option' || role === 'listitem' ||
                cls.includes('menu-item') || cls.includes('listview-item') ||
                cls.includes('nav-item') || cls.includes('toolbar-item') ||
                cls.includes('command') || cls.includes('btn')
              );
              
              if (isContainer) {
                const r = current.getBoundingClientRect();
                // Only use if it's reasonably sized (not the whole page)
                if (r.width > 0 && r.width < 400 && r.height > 0 && r.height < 80) {
                  bestContainer = current;
                  bestRect = r;
                  break;
                }
              }
            }

            // Width sanity check: if the box exceeds 80% of viewport, look for a tighter child
            if (bestRect.width > window.innerWidth * 0.8) {
              const tighterSelectors = [
                '.azc-formControl', '.fxc-base', '.msla-control',
                '.fxs-input-container', '[class*="formControl"]', '[class*="input-container"]'
              ];
              for (const sel of tighterSelectors) {
                const tight = bestContainer.querySelector(sel);
                if (!tight) continue;
                const r = tight.getBoundingClientRect();
                if (r.width > 0 && r.width < window.innerWidth * 0.6 && r.height > 0) {
                  // Add horizontal padding to include adjacent action buttons
                  const padded = {
                    x: r.x,
                    y: r.y,
                    width: r.width + 50,
                    height: r.height,
                  };
                  bestContainer = tight;
                  bestRect = padded;
                  break;
                }
              }
            }
            
            return {
              x: Math.round(bestRect.x),
              y: Math.round(bestRect.y),
              width: Math.round(bestRect.width),
              height: Math.round(bestRect.height),
              element: bestContainer.tagName,
              text: bestContainer.textContent.trim().substring(0, 50),
            };
          }
          
          // Find all elements whose text content matches
          const candidates = [];
          const all = document.querySelectorAll('*');
          for (const el of all) {
            // Check direct text content (not children's text)
            const directText = Array.from(el.childNodes)
              .filter(n => n.nodeType === 3)
              .map(n => n.textContent.trim())
              .join(' ');
            const fullText = el.textContent.trim();
            
            if (!fullText.includes(t.text)) continue;
            
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            if (rect.top < 0 || rect.top > window.innerHeight) continue;
            
            // Score based on how specific the match is
            let score = 0;
            if (directText.includes(t.text)) score += 10;  // direct text match
            if (directText === t.text) score += 20;  // exact match
            if (rect.height < 40) score += 5;  // small elements preferred
            
            // Area filtering
            if (t.area === 'nav' && rect.x < 300) score += 10;
            if (t.area === 'toolbar' && rect.y < 200 && rect.x > 250) score += 10;
            if (t.area === 'content' && rect.x > 250 && rect.y > 150) score += 10;
            
            // Role filtering
            const role = el.getAttribute('role') || '';
            const tag = el.tagName.toLowerCase();
            if (t.role === 'menuitem' && (role === 'menuitem' || role === 'treeitem' || tag === 'li')) score += 15;
            if (t.role === 'button' && (role === 'button' || tag === 'button' || tag === 'a')) score += 15;
            if (t.role === 'link' && (tag === 'a' || role === 'link')) score += 15;

            // Form field awareness: if target is inside an input or labeled field,
            // prefer it so the form-field bounds strategy is used in getVisualBounds
            if (t.role === 'field' || t.role === 'input') {
              if (isFormFieldElement(el)) score += 15;
            }
            if (tag === 'input' || tag === 'textarea') score += 5;
            if (isFormFieldElement(el) && (t.area === 'content' || !t.area)) {
              score += 3;  // slight preference for form-field elements in content area
            }
            
            candidates.push({ el, score, rect });
          }
          
          if (candidates.length === 0) return null;
          
          // Sort by score descending
          candidates.sort((a, b) => b.score - a.score);
          
          // Get the visual bounds of the best match
          return getVisualBounds(candidates[0].el);
          
        }, target);
        
        if (match && (!bestMatch || match.width > 0)) {
          bestMatch = match;
        }
      } catch(e) { /* frame error */ }
    }
    
    if (bestMatch) {
      results[target.id || target.text] = bestMatch;
    }
  }
  
  return results;
}
