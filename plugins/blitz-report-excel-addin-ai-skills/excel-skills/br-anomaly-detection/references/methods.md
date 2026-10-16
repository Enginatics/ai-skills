# Anomaly methods — Office.js / JavaScript reference

Read when scoring in Step 2. All deterministic; runs in-workbook so data stays in the sheet.

## TOC
1. Robust z-score (median + MAD) and IQR fences
2. Mahalanobis distance (+ chi-square cutoff)
3. Benford's Law (first-digit chi-square)
4. Duplicate / near-duplicate scan

---

## 1. Robust z (median + MAD) and IQR
```js
const median = a => { const s=[...a].sort((x,y)=>x-y), m=s.length>>1;
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; };

function robustZ(values){                  // values: number[]
  const med = median(values);
  const mad = median(values.map(v=>Math.abs(v-med))) || 1e-9;
  // 0.6745 scales MAD to be comparable to a standard deviation
  return values.map(v => 0.6745*(v-med)/mad);   // |z| > 3.5 => flag
}

function iqrFences(values){
  const s=[...values].sort((x,y)=>x-y);
  const q=p=>{const i=(s.length-1)*p, lo=Math.floor(i); return s[lo]+(s[Math.ceil(i)]-s[lo])*(i-lo);};
  const q1=q(.25), q3=q(.75), iqr=q3-q1;
  return {low:q1-1.5*iqr, high:q3+1.5*iqr};    // outside => flag
}
```

## 2. Mahalanobis distance
```js
// X: n x d (raw numeric features). Standardise first (see br-clustering scaler) for stability.
function mahalanobis(X){
  const n=X.length, d=X[0].length;
  const mean=Array(d).fill(0);
  X.forEach(r=>r.forEach((v,j)=>mean[j]+=v/n));
  // covariance
  const cov=Array.from({length:d},()=>Array(d).fill(0));
  X.forEach(r=>{for(let i=0;i<d;i++)for(let j=0;j<d;j++)cov[i][j]+=(r[i]-mean[i])*(r[j]-mean[j])/(n-1);});
  const inv=invert(cov);
  return X.map(r=>{
    const dev=r.map((v,j)=>v-mean[j]);
    let s=0; for(let i=0;i<d;i++)for(let j=0;j<d;j++) s+=dev[i]*inv[i][j]*dev[j];
    return Math.sqrt(Math.max(s,0));          // distance; square it to compare to chi-square
  });
}
// Gauss-Jordan inverse (small d only)
function invert(M){
  const n=M.length, A=M.map((r,i)=>[...r,...Array.from({length:n},(_,j)=>i===j?1:0)]);
  for(let c=0;c<n;c++){
    let p=c; while(p<n && Math.abs(A[p][c])<1e-12) p++;
    if(p===n) throw new Error("singular covariance — drop a collinear column");
    [A[c],A[p]]=[A[p],A[c]];
    const piv=A[c][c]; for(let j=0;j<2*n;j++) A[c][j]/=piv;
    for(let r=0;r<n;r++){ if(r===c) continue; const f=A[r][c];
      for(let j=0;j<2*n;j++) A[r][j]-=f*A[c][j]; }
  }
  return A.map(r=>r.slice(n));
}
// Chi-square 0.99 cutoffs for squared distance by d (df): 1:6.63 2:9.21 3:11.34 4:13.28 5:15.09 6:16.81
```

## 3. Benford's Law (first significant digit)
```js
const BENFORD=[.301,.176,.125,.097,.079,.067,.058,.051,.046]; // P(d) for d=1..9
function benford(values){
  const obs=Array(9).fill(0); let n=0;
  for(const v of values){ const a=Math.abs(v); if(a<1) continue;
    const d=+String(a).replace('.','').replace(/^0+/,'')[0]; if(d>=1){obs[d-1]++;n++;} }
  const expCount=BENFORD.map(p=>p*n);
  let chi2=0; for(let i=0;i<9;i++) chi2+=(obs[i]-expCount[i])**2/expCount[i];
  // df=8, 0.05 crit = 15.51, 0.01 = 20.09  -> exceed => distribution is suspicious
  const obsFreq=obs.map(c=>c/n);
  return {n, chi2, obsFreq, expFreq:BENFORD,
          overRep:obsFreq.map((f,i)=>f>BENFORD[i]*1.2?i+1:null).filter(Boolean)};
}
```
Only meaningful for n ≥ ~300 amounts spanning several orders of magnitude.

## 4. Duplicate / near-duplicate scan
```js
// rows: [{key, vendor, amount, date(ms), invNo}]
function findDuplicates(rows, dayWindow=5){
  const byVA=new Map();
  for(const r of rows){ const k=r.vendor+"|"+r.amount.toFixed(2);
    (byVA.get(k)||byVA.set(k,[]).get(k)).push(r); }
  const flags=[];
  for(const [,grp] of byVA){ if(grp.length<2) continue;
    grp.sort((a,b)=>a.date-b.date);
    for(let i=1;i<grp.length;i++){
      const dt=Math.abs(grp[i].date-grp[i-1].date)/86400000;
      if(dt<=dayWindow || grp[i].invNo===grp[i-1].invNo)
        flags.push({key:grp[i].key,
          reason:`possible duplicate of ${grp[i-1].invNo} (same vendor+amount, ${dt.toFixed(0)}d apart)`});
    }
  }
  return flags;
}
```
