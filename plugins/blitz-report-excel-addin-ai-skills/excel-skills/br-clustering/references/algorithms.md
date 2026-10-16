# Clustering algorithms — Office.js / JavaScript reference

Read this when fitting in Step 4. These run in the same Office.js script that reads the sheet, so
the data never leaves the workbook. Adapt variable names to the data at hand.

## Table of contents
1. Standardise (z-score)
2. K-Means (k-means++ init, fixed seed)
3. Silhouette score (cluster quality)
4. Choosing k (elbow + silhouette sweep)
5. DBSCAN
6. eps heuristic (k-distance knee)

---

## 1. Standardise (z-score) — always do this first
```js
function standardise(rows) {            // rows: number[][]  (n x d)
  const d = rows[0].length, n = rows.length;
  const mean = Array(d).fill(0), sd = Array(d).fill(0);
  for (const r of rows) for (let j=0;j<d;j++) mean[j]+=r[j];
  for (let j=0;j<d;j++) mean[j]/=n;
  for (const r of rows) for (let j=0;j<d;j++) sd[j]+=(r[j]-mean[j])**2;
  for (let j=0;j<d;j++) sd[j]=Math.sqrt(sd[j]/n)||1;   // avoid /0 on constant cols
  return { z: rows.map(r=>r.map((v,j)=>(v-mean[j])/sd[j])), mean, sd };
}
```

## 2. K-Means (k-means++ seeding, deterministic)
```js
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);
  t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
const dist2=(a,b)=>a.reduce((s,v,j)=>s+(v-b[j])**2,0);

function kmeans(X, k, seed=42, maxIter=100){
  const rnd=mulberry32(seed), n=X.length;
  // k-means++ init
  const centroids=[X[Math.floor(rnd()*n)].slice()];
  while(centroids.length<k){
    const d=X.map(p=>Math.min(...centroids.map(c=>dist2(p,c))));
    const sum=d.reduce((a,b)=>a+b,0); let t=rnd()*sum, i=0;
    while(t>0 && i<n-1){t-=d[i];i++;} centroids.push(X[i].slice());
  }
  let labels=new Array(n).fill(0);
  for(let it=0;it<maxIter;it++){
    let moved=false;
    for(let i=0;i<n;i++){
      let best=0,bd=Infinity;
      for(let c=0;c<k;c++){const dd=dist2(X[i],centroids[c]);if(dd<bd){bd=dd;best=c;}}
      if(labels[i]!==best){labels[i]=best;moved=true;}
    }
    const sums=centroids.map(c=>c.map(()=>0)), cnt=new Array(k).fill(0);
    for(let i=0;i<n;i++){cnt[labels[i]]++;X[i].forEach((v,j)=>sums[labels[i]][j]+=v);}
    for(let c=0;c<k;c++) if(cnt[c]) centroids[c]=sums[c].map(v=>v/cnt[c]);
    if(!moved) break;
  }
  // inertia for the elbow
  const inertia=X.reduce((s,p,i)=>s+dist2(p,centroids[labels[i]]),0);
  return {labels, centroids, inertia};
}
```

## 3. Silhouette score (mean over all points; range -1..1)
```js
function silhouette(X, labels, k){
  const n=X.length, byC=Array.from({length:k},()=>[]);
  labels.forEach((c,i)=>byC[c].push(i));
  let total=0;
  for(let i=0;i<n;i++){
    const same=byC[labels[i]];
    const a = same.length>1 ? same.filter(j=>j!==i)
        .reduce((s,j)=>s+Math.sqrt(dist2(X[i],X[j])),0)/(same.length-1) : 0;
    let b=Infinity;
    for(let c=0;c<k;c++){ if(c===labels[i]||!byC[c].length) continue;
      const mean=byC[c].reduce((s,j)=>s+Math.sqrt(dist2(X[i],X[j])),0)/byC[c].length;
      if(mean<b) b=mean; }
    total += (b-a)/Math.max(a,b||1);
  }
  return total/n;
}
```

## 4. Choosing k — sweep, then read elbow + silhouette together
```js
const sweep=[];
for(let k=2;k<=8;k++){
  const km=kmeans(Xz,k);
  sweep.push({k, sil:silhouette(Xz,km.labels,k), inertia:km.inertia, km});
}
// DON'T just pick max silhouette — it rewards the fewest/broadest clusters and merges real segments.
// 1) Find the elbow: the k after which inertia stops dropping sharply
//    (largest drop in the *rate* of inertia decrease).
// 2) Prefer that k; use silhouette as a tie-breaker + quality read-out.
// 3) If the user asked for a specific number of segments, use it regardless.
// Always print the whole sweep (k, silhouette, inertia) so the user can override.
// Example: k=2 sil .62 inertia 278 | k=3 sil .57 inertia 115  -> elbow at k=3 is the right answer,
// even though k=2 has the higher silhouette.
```

## 5. DBSCAN
```js
function dbscan(X, eps, minPts){
  const n=X.length, labels=new Array(n).fill(undefined); // undefined=unvisited, -1=noise
  const region=i=>{const out=[];for(let j=0;j<n;j++) if(Math.sqrt(dist2(X[i],X[j]))<=eps) out.push(j);return out;};
  let c=-1;
  for(let i=0;i<n;i++){
    if(labels[i]!==undefined) continue;
    let nb=region(i);
    if(nb.length<minPts){labels[i]=-1;continue;}
    c++; labels[i]=c;
    const seeds=nb.filter(j=>j!==i);
    for(let s=0;s<seeds.length;s++){
      const q=seeds[s];
      if(labels[q]===-1) labels[q]=c;
      if(labels[q]!==undefined) continue;
      labels[q]=c;
      const qn=region(q);
      if(qn.length>=minPts) for(const x of qn) if(!seeds.includes(x)) seeds.push(x);
    }
  }
  return labels; // cluster ids 0..c, and -1 = noise/outlier
}
```

## 6. eps heuristic (k-distance knee)
```js
// minPts = 2 * #features (round up). eps = the "knee" of the sorted k-distance curve.
function suggestEps(X, minPts){
  const n=X.length, kd=[];
  for(let i=0;i<n;i++){
    const ds=X.map((p,j)=>j===i?Infinity:Math.sqrt(dist2(X[i],p))).sort((a,b)=>a-b);
    kd.push(ds[minPts-1]);
  }
  kd.sort((a,b)=>a-b);
  // simple knee: point of max distance from the chord between first and last
  const x0=0,y0=kd[0],x1=n-1,y1=kd[n-1];
  let knee=0,bd=-1;
  for(let i=0;i<n;i++){
    const num=Math.abs((y1-y0)*i-(x1-x0)*kd[i]+x1*y0-y1*x0);
    if(num>bd){bd=num;knee=i;}
  }
  return kd[knee];
}
```
Always report the chosen `eps`/`minPts` and the noise count so the user can audit the fit.
