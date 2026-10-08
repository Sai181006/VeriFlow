import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const { SKILL_DIR, TMP_DIR, FINAL_PPTX, RUNTIME_PYTHON } = process.env;
if (![SKILL_DIR,TMP_DIR,FINAL_PPTX,RUNTIME_PYTHON].every(p=>path.isAbsolute(p??''))) throw new Error('Absolute runtime paths required');
const repo=path.resolve(TMP_DIR,'..','..');
const {finalizePresentation,resolvePresentationFont}=await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const FONT=resolvePresentationFont({fontFamily:'Segoe UI'});
const MONO=resolvePresentationFont({fontFamily:'Consolas'});
const K={bg:'#F7F7F3',ink:'#132739',navy:'#0B1E2B',teal:'#0A7C77',tealPale:'#E2F0EB',rust:'#AD5838',rustPale:'#F7E9DF',gray:'#536774',rule:'#B8C8C7',white:'#FFFFFF',green:'#24765A',stone:'#EDEFEA'};
const W=1280,H=720;
const p=Presentation.create({slideSize:{width:W,height:H}});
const slides=[];

function tx(s,v,x,y,w,h,n=22,color=K.ink,bold=false,family=FONT){
 const q=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 q.text=v;q.text.style={typeface:family,fontSize:n,color,bold,autoFit:'none'};return q;
}
function box(s,x,y,w,h,fill=K.bg,stroke=K.rule,lw=1){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:stroke,width:lw}})}
function ln(s,x1,y1,x2,y2,color=K.rule,width=2){return s.shapes.add({geometry:'line',position:{left:x1,top:y1,width:x2-x1,height:y2-y1},fill:'none',line:{style:'solid',fill:color,width}})}
function connect(s,a,b,from='right',to='left',color=K.rule,width=2){return s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,line:{style:'solid',fill:color,width}})}
function slide(kicker,title,n){
 const s=p.slides.add();slides.push(s);s.background.fill=K.bg;
 tx(s,kicker.toUpperCase(),62,29,840,27,15,K.teal,true);
 tx(s,String(n).padStart(2,'0'),1164,28,55,25,15,K.gray);
 tx(s,title,62,78,1160,93,38,K.ink,true);
 return s;
}
function source(s,v){tx(s,v,62,670,1090,25,14,K.gray)}
function note(s,v){s.speakerNotes.textFrame.setText(v)}
function label(s,v,x,y,w,n=19,color=K.ink,bold=false){return tx(s,v,x,y,w,50,n,color,bold)}
function node(s,v,x,y,w,h,accent=K.teal,n=21,mono=false){
 const b=box(s,x,y,w,h,K.white,accent,2);
 tx(s,v,x+15,y+12,w-30,h-18,n,K.ink,true,mono?MONO:FONT);
 return b;
}
function table(s,vals,x,y,w,h,widths){
 const t=s.tables.add({rows:vals.length,columns:vals[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values:vals});
 t.styleOptions={headerRow:true,bandedRows:false};
 t.borders.assign({style:'solid',fill:K.rule,width:0.8});
 for(let r=0;r<vals.length;r++)for(let c=0;c<vals[0].length;c++){
  const q=t.getCell(r,c);q.fill=r===0?K.navy:(r%2?K.white:K.stone);
  q.text.style={typeface:FONT,fontSize:r===0?19:19,color:r===0?K.white:K.ink,bold:r===0,autoFit:'none'};
 }
 return t;
}

// 1. A research-talk cover with one original generated visual.
{
 const s=p.slides.add();slides.push(s);s.background.fill=K.navy;
 const hero=await fs.readFile(path.join(repo,'presentations','assets','cover-research.png'));
 s.images.add({blob:new Uint8Array(hero),contentType:'image/png',alt:'Abstract data tables connected by teal and amber migration traces',fit:'cover',position:{left:0,top:0,width:W,height:H}});
 tx(s,'VERIFLOW  /  RESEARCH BRIEF',72,57,720,32,17,'#C4E7E2',true);
 tx(s,'When does a lossy\nschema migration\npreserve pipeline behavior?',72,188,755,271,51,K.white,true);
 tx(s,'A guarded, migration-time analysis for typed CSV pipelines',72,509,740,70,25,'#D5EAE5');
 tx(s,'October 2026',72,644,450,30,17,'#C4D5D4');
 note(s,'Working research title: Guarded Preservation of Row-Wise Pipeline Behavior During Schema Migration. Scope: deterministic VeriFlow CSV pipeline, one explicit schema change, well-typed legacy rows available at migration time. Cover art was generated specifically for this project with the built-in image generation tool. Full technical source: docs/paper-draft.md.');
}

// 2. Define the moving parts and the actual problem.
{
 const s=slide('Problem / what changes','A schema-level “lossy” label cannot answer the pipeline question',2);
 tx(s,'Old row',77,191,245,34,19,K.gray,true);
 tx(s,'Explicit migration F',477,191,298,34,19,K.gray,true);
 tx(s,'Migrated row F(s)',878,191,319,34,19,K.gray,true);
 const a=node(s,'name: Ada\nscore: 40.7 (decimal)',74,232,292,111,K.teal,22,true);
 const b=node(s,'score → int\ntruncate toward zero',479,232,300,111,K.rust,22,true);
 const c=node(s,'name: Ada\nscore: 40 (int)',889,232,296,111,K.teal,22,true);
 connect(s,a,b,'right','left',K.rule,3);connect(s,b,c,'right','left',K.rule,3);
 tx(s,'The pipeline may validate, derive, filter, and select values.',76,420,1124,54,28,K.ink,true);
 tx(s,'Behavior means: emitted typed values, filtered row, requirement failure with message, or expression error.',76,491,1115,70,24,K.ink);
 ln(s,76,593,1190,593,K.rule,1.5);
 tx(s,'Research question',76,611,220,35,17,K.teal,true);
 tx(s,'For which old rows does migration keep this observation unchanged?',296,606,876,47,25,K.ink,true);
 source(s,'Setting: one explicit schema change; the old row is still available while migration runs.');
 note(s,'VeriFlow has a typed CSV pipeline language with let, require, keep, and select, and an explicit evolution plan. The previous record-level evolution label is too coarse for a pipeline-specific behavior question. We define Obs to include selected typed values, filtering, validation failure and its message, and expression error. Sources: docs/paper-research-context.md and docs/impact-method.md.');
}

// 3. A concrete case with correct row versus analysis status distinction.
{
 const s=slide('Motivating example','One migration preserves ≥ 40 but changes > 40 at 40.7',3);
 tx(s,'Decimal 40.7',73,184,360,58,35,K.ink,true,MONO);
 tx(s,'→',454,184,74,58,39,K.rust,true);
 tx(s,'Integer 40',527,184,352,58,35,K.ink,true,MONO);
 tx(s,'truncation',916,194,266,45,22,K.gray);
 ln(s,73,274,1191,274,K.rule,2);
 tx(s,'keep score ≥ 40',83,305,400,50,26,K.ink,true,MONO);
 tx(s,'true → true',534,305,294,50,27,K.teal,true,MONO);
 tx(s,'PRESERVED',943,307,247,42,22,K.green,true);
 ln(s,73,373,1191,373,K.rule,1);
 tx(s,'keep score > 40',83,399,400,50,26,K.ink,true,MONO);
 tx(s,'true → false',534,399,316,50,27,K.rust,true,MONO);
 tx(s,'CONDITIONAL',943,402,240,42,22,K.rust,true);
 ln(s,73,473,1191,473,K.rule,2);
 tx(s,'Guard for the strict condition',81,513,500,40,19,K.gray,true);
 tx(s,'G(s): score ≤ 40  OR  score ≥ 41',81,554,1005,56,29,K.ink,true,MONO);
 source(s,'The row 40.7 changes; the checker’s overall result is conditional because the guard excludes 40 < score < 41.');
 note(s,'The decimal-to-integer conversion truncates toward zero. For positive integer threshold k, x >= k and x < k are invariant on finite decimals. For the atomic x > k or x <= k, the unsafe open interval is k < x < k+1. The row 40.7 changes the strict predicate, yet the analysis status is conditional because G excludes the unsafe interval. No generality is claimed for arbitrary expressions. Proof: docs/paper-draft.md; implementation: veriflow/impact.py.');
}

// 4. Visible, cited research positioning with the closest pipeline paper.
{
 const s=slide('Related work / precise opening','Prior work covers schema evolution and pipeline robustness',4);
 table(s,[
  ['Work','Established contribution','The question evaluated in VeriFlow'],
  ['Curino et al., PRISM (2008)','Schema impact, migration, query rewriting','Value-dependent row-pipeline behavior'],
  ['Fan et al. (2012)','Selected-information preservation','Executable guards for validation and filtering'],
  ['Kramer et al. (2025)','Operator robustness under schema edits','Typed conversion rules with replay and CSV guard coverage']
 ],64,193,1152,334,[270,418,464]);
 tx(s,'Candidate novelty',68,552,390,35,21,K.teal,true);
 tx(s,'A scoped executable contract: sufficient guard + replayed witness + measured admission on legacy CSV.',68,589,1118,65,25,K.ink,true);
 source(s,'Sources: Curino et al. 2008; Fan et al. 2012; Kramer et al. 2025. Full links in speaker notes.');
 note(s,'Primary papers: PRISM https://www.vldb.org/pvldb/vol1/1453939.pdf ; Fan, Geerts, Zheng https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf ; Kramer, Restat, Störl https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/QDB/QDB25_4.pdf . Additional close work: Mediator https://arxiv.org/abs/1710.07660 ; Conditional Equivalence https://www.microsoft.com/en-us/research/publication/conditional-equivalence/ ; BiDEL/InVerDa https://arxiv.org/abs/1608.05564 . The comparison is a scoped research positioning, not a claim that earlier work has no pipeline awareness or conditional analysis. Independent expert review is pending.');
}

// 5. Two execution traces, then the equation.
{
 const s=slide('Guarantee / two executions','A proved guard makes the two observations equal',5);
 tx(s,'Original execution',72,186,354,33,20,K.gray,true);
 const a=node(s,'old row s',72,236,233,72,K.teal,21,true);
 const b=node(s,'legacy pipeline P',454,236,283,72,K.teal,21);
 const c=node(s,'Obs₁',922,236,218,72,K.teal,24,true);
 connect(s,a,b,'right','left',K.teal,2.5);connect(s,b,c,'right','left',K.teal,2.5);
 tx(s,'Migrated execution',72,345,354,33,20,K.gray,true);
 const d=node(s,'old row s',72,395,233,72,K.rust,21,true);
 const e=node(s,'F then adapter A',370,395,300,72,K.rust,21);
 const f=node(s,'legacy pipeline P',735,395,262,72,K.rust,21);
 const g=node(s,'Obs₂',1060,395,145,72,K.rust,20,true);
 connect(s,d,e,'right','left',K.rust,2.5);connect(s,e,f,'right','left',K.rust,2.5);connect(s,f,g,'right','left',K.rust,2.5);
 tx(s,'If G(s) holds and F(s) is defined:',73,520,554,38,21,K.gray,true);
 tx(s,'Obs(P,s) = Obs(P,A(F(s)))',73,563,945,57,31,K.ink,true,MONO);
 source(s,'G checks the old row during migration. This does not certify arbitrary new-only rows.');
 note(s,'Formal claim: for every well-typed old row s in the defined forward mapping domain, if sufficient guard G(s) holds then the typed observation from P(s) equals that from P(A(F(s))). A is a partial adapter and the actual adapted execution still runs the legacy pipeline P; it is not a separately compiled new-schema pipeline. G requires the old row, so this is migration-time only. See docs/impact-method.md and docs/paper-draft.md.');
}

// 6. Checker decision graph with direct status semantics.
{
 const s=slide('Method / analysis and execution','The checker returns proof, guard, replayed break, or unknown',6);
 const a=node(s,'Trace used fields\nlet · require · keep · select',72,199,327,106,K.teal,22);
 const b=node(s,'Apply supported rules\nexact values · thresholds',475,199,327,106,K.teal,22);
 const c=node(s,'Replay candidates\nthrough both VM paths',878,199,327,106,K.rust,22);
 connect(s,a,b,'right','left',K.rule,2.5);connect(s,b,c,'right','left',K.rule,2.5);
 ln(s,74,370,1205,370,K.rule,2);
 tx(s,'PRESERVED',80,404,248,35,20,K.green,true);
 tx(s,'G = true for the supported domain',80,442,250,70,19,K.ink);
 tx(s,'CONDITIONAL',357,404,252,35,20,K.rust,true);
 tx(s,'An executable G guarantees the claim',357,442,249,70,19,K.ink);
 tx(s,'BREAKING',645,404,252,35,20,K.rust,true);
 tx(s,'A valid collision replays a changed observation',645,442,251,81,19,K.ink);
 tx(s,'UNKNOWN',939,404,244,35,20,K.gray,true);
 tx(s,'No supported proof or replayed collision',939,442,244,80,19,K.ink);
 box(s,73,574,1132,67,K.tealPale,K.teal,1);
 tx(s,'Readiness report: guard-admitted rows / well-typed input rows, before migrated CSV execution.',92,591,1095,46,21,K.ink,true);
 source(s,'A witness search is bounded; finding none is never reported as proof.');
 note(s,'The checker follows dependencies transitively through executed let, require, keep, select. Supported sound rules include exact reconstruction and positive-integer threshold predicates under decimal-to-int truncation. Guarded evolved CSV execution checks G before lossy conversion and records rejected rows. Breaking requires a replayed pair of valid old rows mapping to the same new row with different old observations. Unknown means neither proof nor validated collision. See veriflow/impact.py, veriflow/reporting.py, docs/impact-method.md.');
}

// 7. Evidence with denominators and honest limits.
{
 const s=slide('Evidence / reproducible pilot','Three record-lossy pipelines are proved preserved',7);
 tx(s,'3 public datasets  ·  5,926 distinct source rows  ·  10 injected cases',72,178,1135,45,24,K.rust,true);
 tx(s,'Strict-predicate guard admission on each dataset',73,248,750,33,21,K.gray,true);
 const data=[['Abalone',2782,4177],['Iris',99,150],['Red Wine Quality',1214,1599]];
 for(let i=0;i<data.length;i++){
  const [name,pass,total]=data[i], y=310+i*79,ratio=pass/total;
  tx(s,name,73,y,278,43,22,K.ink,true);
  box(s,350,y+7,580,25,K.stone,K.stone,0);
  box(s,350,y+7,580*ratio,25,K.teal,K.teal,0);
  tx(s,`${pass.toLocaleString()} / ${total.toLocaleString()}  (${(ratio*100).toFixed(1)}%)`,960,y,270,39,19,K.ink,true);
 }
 ln(s,72,565,1204,565,K.rule,1.5);
 tx(s,'3 preserved',73,581,250,41,25,K.green,true);
 tx(s,'1 unknown',354,581,226,41,25,K.gray,true);
 tx(s,'8 / 8 negative controls',613,581,302,41,22,K.ink,true);
 tx(s,'4 / 4 CSV parity checks',913,581,300,41,22,K.ink,true);
 source(s,'No observed guard-admitted violation in this pilot. Mappings are synthetic; proof rests on the rule premises.');
 note(s,'Data: UCI Abalone 4,177 rows, Iris 150 rows, Red Wine Quality 1,599 rows, totaling 5,926 distinct source rows reused across ten injected migration cases. All dataset schema mappings are synthetic. Three non-strict record-lossy numeric cases are proved preserved. The Iris split case remains unknown. Strict-predicate guard admissions are 2,782/4,177, 99/150, 1,214/1,599; percentages shown are arithmetic rounded to one decimal. Eight declared negative controls and four end-to-end CSV parity cases passed. No admitted row changed typed observation in this finite pilot. Evidence: evaluation/results.json, evaluation/negative-controls.json, evaluation/csv-parity.json, evaluation/README.md. UCI pages: https://archive.ics.uci.edu/dataset/1/abalone , https://archive.ics.uci.edu/dataset/53/iris , https://archive.ics.uci.edu/dataset/186/wine+quality .');
}

// 8. Close with candidate contribution and the boundary that matters.
{
 const s=slide('Conclusion / current scope','The result is useful at migration time, within a defined fragment',8);
 tx(s,'Candidate contribution',72,194,655,39,22,K.teal,true);
 tx(s,'Proof rules + executable row guards + replayed failure evidence + measured guard coverage',72,239,1096,100,31,K.ink,true);
 ln(s,72,374,1208,374,K.rule,1.5);
 tx(s,'What is established',73,404,470,36,21,K.green,true);
 tx(s,'For supported one-step mappings on well-typed legacy rows, an admitted guard preserves the defined typed observation.',73,446,492,123,24,K.ink);
 tx(s,'What remains open',659,404,470,36,21,K.rust,true);
 tx(s,'Standalone new-schema rewriting, new-only row guards, general split/merge proofs, and real migration histories.',659,446,517,123,24,K.ink);
 tx(s,'Next research gate: independent proof and novelty review before submission.',73,603,1119,46,24,K.ink,true);
 source(s,'Full method, evaluation sources, and paper references are in the speaker notes.');
 note(s,'The current proposition is a narrow executable migration-time behavior contract, not a general schema-evolution solution. The old row must be available to evaluate G. An independent domain reader has not yet reviewed the proof/novelty, and no actual organizational migration history is included. Standalone new-schema rewrite, guards for arbitrary future new-only rows, general split/merge, arbitrary expressions, and multi-version chains remain research gaps. See docs/paper-draft.md, docs/council-review-2026-10-08.md, docs/paper-research-tasks.md.');
}

await fs.mkdir(TMP_DIR,{recursive:true});
await fs.mkdir(path.dirname(FINAL_PPTX),{recursive:true});
const draft=path.join(TMP_DIR,'veriflow-redesign-candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(draft);
for(let i=0;i<slides.length;i++){
 const im=await slides[i].export({format:'png',scale:1});
 await fs.writeFile(path.join(TMP_DIR,`redesign-slide-${i+1}.png`),new Uint8Array(await im.arrayBuffer()));
}
if(process.env.PREVIEW_ONLY==='1') process.exit(0);
const receipt=path.join(TMP_DIR,'validation',`${path.basename(FINAL_PPTX)}.validation.json`);
await fs.mkdir(path.dirname(receipt),{recursive:true});
const result=await finalizePresentation({
 explicitTotalSlideCount:8,requiredNativeTableOwnerSlides:[4],requiredNativeChartOwnerSlides:[],
 workspaceDir:repo,candidatePath:draft,finalPath:FINAL_PPTX,pythonExecutable:RUNTIME_PYTHON,
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','4'],
 fontPolicy:{basis:'design',families:[FONT,MONO]},verifyArtifactToolImport:true,receiptPath:receipt,
});
console.log(JSON.stringify({final:FINAL_PPTX,result}));
