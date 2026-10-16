const slug=s=>s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
if(window.marked){marked.use({gfm:true,renderer:{html:t=>esc(typeof t==='string'?t:t.text)}});
document.querySelectorAll('pre.md').forEach(p=>{const d=document.createElement('div');d.className='prose';d.innerHTML=marked.parse(p.textContent);p.replaceWith(d)});
const src=document.querySelector('[data-src]');
document.querySelectorAll('.prose a[href]').forEach(a=>{const h=a.getAttribute('href');if(/^([a-z]+:|#|\/)/i.test(h))return;
const id='file-'+slug(h.replace(/^\.\//,''));if(document.getElementById(id))a.href='#'+id;else if(src)a.href=src.dataset.src+h});
document.querySelectorAll('.prose table').forEach(t=>{const w=document.createElement('div');w.className='tw';t.parentNode.insertBefore(w,t);w.appendChild(t)})}
document.querySelectorAll('pre').forEach(p=>{const b=document.createElement('button');b.className='copy';b.textContent='Copy';
b.onclick=()=>navigator.clipboard.writeText(p.querySelector('code').innerText).then(()=>{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1500)});p.appendChild(b)});
const q=document.getElementById('q');if(q){let cat='';const chips=document.querySelectorAll('.chip');
const apply=()=>{const t=q.value.toLowerCase();document.querySelectorAll('section[data-cat]').forEach(s=>{let n=0;
s.querySelectorAll('.card').forEach(c=>{const ok=(!cat||s.dataset.cat===cat)&&c.textContent.toLowerCase().includes(t);c.classList.toggle('hidden',!ok);n+=ok});
s.classList.toggle('hidden',!n)})};
q.addEventListener('input',apply);chips.forEach(c=>c.onclick=()=>{cat=c.getAttribute('aria-pressed')==='true'?'':c.dataset.cat;
chips.forEach(x=>x.setAttribute('aria-pressed',x.dataset.cat===cat&&cat?'true':'false'));apply()})}
