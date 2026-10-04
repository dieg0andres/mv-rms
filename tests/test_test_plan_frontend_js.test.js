const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync('static/rms/test_plan.js','utf8');
function page(retained = false) {
  const handlers = {}, formHandlers = {};
  const status = {textContent:'No new save confirmed.'};
  const form = {dataset:{retained:String(retained)},querySelector:()=>status,addEventListener:(event,fn)=>formHandlers[event]=fn};
  vm.runInNewContext(source,{document:{querySelector:()=>form},window:{addEventListener:(event,fn)=>handlers[event]=fn}});
  return {handlers,formHandlers,status};
}
test('no warning for clean form; input and retained proposals warn on navigation',()=>{
  for (const retained of [false,true]) {
    const p = page(retained);let prevented=0;
    const event={preventDefault:()=>prevented++};p.handlers.beforeunload(event);
    assert.equal(prevented,retained?1:0);
    p.formHandlers.input();p.handlers.beforeunload(event);assert.equal(prevented,retained?2:1);
  }
});
test('native submission preserves proposal and key, prevents duplicate, and never claims saved',()=>{
  const p=page(true);let prevented=0;
  p.formHandlers.submit({preventDefault:()=>prevented++});assert.equal(prevented,0);
  assert.match(p.status.textContent,/awaiting server confirmation/);
  p.handlers.beforeunload({preventDefault:()=>prevented++});assert.equal(prevented,0);
  p.formHandlers.submit({preventDefault:()=>prevented++});assert.equal(prevented,1);
  assert.doesNotMatch(p.status.textContent,/Draft saved|Saved\./);
});
test('back navigation restores submission ability and unsaved warning',()=>{
  const p=page(true);p.formHandlers.submit({preventDefault:()=>{}});p.handlers.pageshow();
  assert.equal(p.status.textContent,'No new save confirmed.');
  let prevented=0;p.handlers.beforeunload({preventDefault:()=>prevented++});assert.equal(prevented,1);
  p.formHandlers.submit({preventDefault:()=>prevented++});assert.equal(prevented,1);
});
test('no form requires no persistence or request APIs',()=>{
  vm.runInNewContext(source,{document:{querySelector:()=>null}});
  for(const forbidden of ['fetch(', 'localStorage', 'sessionStorage', 'innerHTML', 'eval(']) assert.ok(!source.includes(forbidden));
});
// Small DOM fixture to exercise native add/move/remove path handling without
// claiming a real-browser acceptance run.
class Element {
  constructor(tag,attrs={},children=[]) { this.tagName=tag.toUpperCase();this.attrs={...attrs};this.children=[];this.textContent='';this.value='';for(const child of children)this.append(child); }
  get dataset(){ const out={};for(const [key,value] of Object.entries(this.attrs))if(key.startsWith('data-'))out[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=value;return out; }
  getAttribute(key){return this.attrs[key] ?? null;} setAttribute(key,value){this.attrs[key]=value;} hasAttribute(key){return key in this.attrs;}
  matches(selector){ if(selector==='*')return true;if(selector[0]==='[')return this.hasAttribute(selector.slice(1,-1));return this.tagName===selector.toUpperCase(); }
  closest(selector){return this.matches(selector)?this:this.parentElement?.closest(selector) || null;}
  append(child){child.remove();child.parentElement=this;this.children.push(child);}
  remove(){if(this.parentElement){const list=this.parentElement.children;list.splice(list.indexOf(this),1);this.parentElement=null;}}
  insertBefore(child,before){child.remove();child.parentElement=this;this.children.splice(this.children.indexOf(before),0,child);}
  get firstElementChild(){return this.children[0]||null;}
  get previousElementSibling(){const list=this.parentElement?.children||[];return list[list.indexOf(this)-1]||null;}
  get nextElementSibling(){const list=this.parentElement?.children||[];return list[list.indexOf(this)+1]||null;}
  querySelectorAll(selector){const result=[];for(const child of this.children){if(child.matches(selector))result.push(child);result.push(...child.querySelectorAll(selector));}return result;}
  querySelector(selector){if(selector.includes(','))return this.querySelectorAll('*').find(e=>['INPUT','TEXTAREA','SELECT'].includes(e.tagName))||null;return this.querySelectorAll(selector)[0]||null;}
  cloneNode(){const copy=new Element(this.tagName,this.attrs,this.children.map(c=>c.cloneNode()));copy.value=this.value;copy.textContent=this.textContent;if(this.content)copy.content=this.content.cloneNode();return copy;}
  focus(){this.focused=true;}
}
function repeatPage(){
  const prefix='/data_requirements';
  const itemPrefix=prefix+'/__row0__';
  const nested=new Element('template',{'data-tp-prototype':'','data-token':'__row1__'});
  nested.content=new Element('fragment',{},[new Element('fieldset',{'data-tp-item':itemPrefix+'/fields/field_schema/__row1__'},[new Element('input',{name:itemPrefix+'/fields/field_schema/__row1__/name'})])]);
  const prototype=new Element('template',{'data-tp-prototype':'','data-token':'__row0__'});
  prototype.content=new Element('fragment',{},[new Element('fieldset',{'data-tp-item':itemPrefix},[
    new Element('legend'),new Element('input',{name:itemPrefix+'/fields/name',id:'tp'+itemPrefix+'/fields/name'}),
    new Element('label',{for:'tp'+itemPrefix+'/fields/name'}),nested,
    new Element('button',{'data-tp-move':'up'}),new Element('button',{'data-tp-move':'down'}),new Element('button',{'data-tp-remove':''})
  ])]);
  const list=new Element('div',{'data-tp-items':''});
  const add=new Element('button',{'data-tp-add':''});
  const array=new Element('fieldset',{'data-tp-array':prefix},[new Element('legend'),list,prototype,add]);
  array.children[0].textContent='Data requirements';
  const form=new Element('form',{'data-retained':'false'},[array]);const handlers={},windows={};
  const status={textContent:''};form.addEventListener=(name,fn)=>handlers[name]=fn;form.querySelector=()=>status;
  vm.runInNewContext(source,{document:{querySelector:()=>form},window:{addEventListener:(name,fn)=>windows[name]=fn}});
  return {list,add,click:target=>handlers.click({target}),windows};
}
test('repeat-item add, reorder and remove preserve text and deterministic names/labels',()=>{
  const p=repeatPage();p.click(p.add);p.click(p.add);
  const [first,second]=p.list.children;first.querySelector('input').value='First author text';second.querySelector('input').value='Second author text';
  p.click(second.querySelectorAll('button')[0]);
  assert.equal(p.list.children[0].querySelector('input').value,'Second author text');
  assert.equal(p.list.children[0].querySelector('input').getAttribute('name'),'/data_requirements/0/fields/name');
  assert.equal(p.list.children[1].querySelector('input').getAttribute('name'),'/data_requirements/1/fields/name');
  for(const item of p.list.children)assert.equal(item.querySelector('label').getAttribute('for'),item.querySelector('input').getAttribute('id'));
  p.click(p.list.children[0].querySelectorAll('button')[2]);
  assert.equal(p.list.children.length,1);assert.equal(p.list.children[0].querySelector('input').value,'First author text');
  assert.equal(p.list.children[0].querySelector('input').getAttribute('name'),'/data_requirements/0/fields/name');
});
test('nested inactive prototypes follow parent reindex without losing their own token',()=>{
  const p=repeatPage();p.click(p.add);p.click(p.add);const second=p.list.children[1];
  p.click(second.querySelectorAll('button')[0]);
  const nested=p.list.children[0].querySelector('template');
  assert.equal(nested.content.querySelector('input').getAttribute('name'),'/data_requirements/0/fields/field_schema/__row1__/name');
  assert.equal(nested.dataset.token,'__row1__');
});
test('retained row errors stay associated with their input after reorder and removal',()=>{
  const p=repeatPage();p.click(p.add);p.click(p.add);
  for(const [index,item] of p.list.children.entries()) {
    const input=item.querySelector('input');input.value='Invented row '+index;
    const errorId=input.getAttribute('id')+'-errors';
    input.setAttribute('aria-describedby',errorId+' tp-shared-help');
    const errors=new Element('ul',{id:errorId});errors.textContent='Invented error '+index;
    item.append(errors);
  }
  const second=p.list.children[1];p.click(second.querySelectorAll('button')[0]);
  function assertOwnError(item,index) {
    const input=item.querySelector('input');
    const errors=item.children.find(child=>child.tagName==='UL');
    assert.equal(input.getAttribute('aria-describedby'),errors.getAttribute('id')+' tp-shared-help');
    assert.equal(errors.getAttribute('id'),'tp/data_requirements/'+index+'/fields/name-errors');
    assert.equal(errors.textContent,'Invented error '+input.value.slice(-1));
  }
  p.list.children.forEach(assertOwnError);
  p.click(p.list.children[0].querySelectorAll('button')[2]);
  assert.equal(p.list.children[0].querySelector('input').value,'Invented row 0');
  assertOwnError(p.list.children[0],0);
});
