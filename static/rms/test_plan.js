/* Native explicit form submission. No provider calls, storage, or client rules. */
(() => {
  const form = document.querySelector('[data-test-plan-form]');
  if (!form) return;
  let dirty = form.dataset.retained === 'true';
  let submitting = false;
  const status = form.querySelector('[data-tp-status]');
  const announce = text => { if (status) status.textContent = text; };
  const mark = () => { dirty = true; };
  form.addEventListener('input', mark);
  form.addEventListener('change', mark);
  window.addEventListener('beforeunload', event => {
    if (dirty && !submitting) { event.preventDefault(); event.returnValue = ''; }
  });
  window.addEventListener('pageshow', () => { submitting = false; announce('No new save confirmed.'); });
  const rewrite = (root, oldPrefix, newPrefix) => {
    const visit = element => {
      for (const attribute of ['name', 'id', 'for', 'data-tp-array', 'data-tp-item']) {
        const value = element.getAttribute(attribute);
        if (value && value.includes(oldPrefix)) element.setAttribute(attribute, value.replaceAll(oldPrefix, newPrefix));
      }
      if (element.tagName === 'TEMPLATE') for (const child of element.content.querySelectorAll('*')) visit(child);
    };
    visit(root);
    for (const element of root.querySelectorAll('*')) visit(element);
  };
  const direct = (element, selector) => Array.from(element.children).find(child => child.matches(selector));
  const reindex = array => {
    const list = direct(array, '[data-tp-items]');
    const prefix = array.dataset.tpArray;
    Array.from(list.children).forEach((item, index) => rewrite(item, item.dataset.tpItem, prefix + '/__temporary' + index + '__'));
    Array.from(list.children).forEach((item, index) => {
      rewrite(item, item.dataset.tpItem, prefix + '/' + index);
      direct(item, 'legend').textContent = direct(array, 'legend').textContent + ' item ' + (index + 1);
    });
  };
  form.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    const array = button.closest('[data-tp-array]');
    if (!array) return;
    const list = direct(array, '[data-tp-items]');
    if (button.hasAttribute('data-tp-add')) {
      const template = direct(array, 'template');
      const item = template.content.firstElementChild.cloneNode(true);
      rewrite(item, array.dataset.tpArray + '/' + template.dataset.token, array.dataset.tpArray + '/' + list.children.length);
      list.append(item);
      reindex(array);
      item.querySelector('input:not([type=hidden]),textarea,select')?.focus();
      announce('Item added to unsaved draft.'); mark();
    } else if (button.hasAttribute('data-tp-remove')) {
      button.closest('[data-tp-item]').remove(); reindex(array);
      direct(array, '[data-tp-add]').focus(); announce('Item removed from unsaved draft.'); mark();
    } else if (button.dataset.tpMove) {
      const item = button.closest('[data-tp-item]');
      const neighbor = button.dataset.tpMove === 'up' ? item.previousElementSibling : item.nextElementSibling;
      if (neighbor) { if (button.dataset.tpMove === 'up') list.insertBefore(item, neighbor); else list.insertBefore(neighbor, item); reindex(array); button.focus(); mark(); announce('Item order changed in unsaved draft.'); }
    }
  });
  form.addEventListener('submit', event => {
    if (submitting) { event.preventDefault(); return; }
    submitting = true;
    announce('Submitting draft; awaiting server confirmation.');
    // Keep controls enabled so native submission sends the exact proposal/key.
  });
})();
