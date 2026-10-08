import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import sharp from 'sharp';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const { SKILL_DIR, TMP_DIR, FINAL_PPTX, RUNTIME_PYTHON } = process.env;
const workspaceDir = path.resolve(TMP_DIR, '..', '..');
const { finalizePresentation, resolvePresentationFont } = await import(
  pathToFileURL(path.join(SKILL_DIR, 'container_tools/artifact_tool_utils.mjs')).href
);
const font = resolvePresentationFont({ fontFamily: 'Arial' });
const W = 1280, H = 720;
const C = {
  navy: '#14263D', teal: '#087E82', cyan: '#DDF2F0', ink: '#243746',
  muted: '#5B6E7D', pale: '#F4F8F9', line: '#C8D6DA', orange: '#C56825',
  orangePale: '#FCEBDB', green: '#14765D', white: '#FFFFFF', red: '#AF473F'
};
const pres = Presentation.create({ slideSize: { width: W, height: H } });
const allSlides=[];

function text(slide, value, left, top, width, height, size=22, color=C.ink, bold=false) {
  const s = slide.shapes.add({ geometry:'textbox', position:{left,top,width,height}, fill:'none', line:{fill:'none',width:0} });
  s.text = value;
  s.text.style = { typeface:font, fontSize:size, bold, color, autoFit:'none' };
  return s;
}
function rect(slide, left, top, width, height, fill=C.white, stroke=C.line, lineWidth=1.5) {
  return slide.shapes.add({ geometry:'rect', position:{left,top,width,height}, fill, line:{style:'solid',fill:stroke,width:lineWidth} });
}
function line(slide, x1,y1,x2,y2, color=C.line, width=2) {
  return slide.shapes.add({ geometry:'line', position:{left:x1,top:y1,width:x2-x1,height:y2-y1}, fill:'none', line:{style:'solid',fill:color,width} });
}
function base(title, num) {
  const s = pres.slides.add(); s.background.fill=C.white;
  allSlides.push(s);
  text(s,title,70,40,1120,58,38,C.navy,true);
  line(s,70,111,1210,111,C.teal,4);
  text(s,String(num).padStart(2,'0'),1174,666,40,26,16,C.muted,false);
  return s;
}
function notes(slide,body) { slide.speakerNotes.textFrame.setText(body); }
async function icon(slide,name,left,top,size) {
  const svg=await fs.readFile(path.join(workspaceDir,'presentations','assets',name+'.svg'));
  const png=await sharp(svg).resize(240,240).png().toBuffer();
  slide.images.add({blob:new Uint8Array(png),contentType:'image/png',alt:`Google Material Symbols ${name} icon`,fit:'contain',position:{left,top,width:size,height:size}});
}
function node(slide,label,x,y,w,h,fill=C.white,stroke=C.teal,size=21){
  const r=rect(slide,x,y,w,h,fill,stroke,2);
  text(slide,label,x+16,y+13,w-32,h-20,size,C.navy,true);
  return r;
}
function nativeTable(slide,vals,x,y,w,h,widths,headerSize=18,bodySize=17){
  const t=slide.tables.add({rows:vals.length,columns:vals[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values:vals});
  t.styleOptions={headerRow:true,bandedRows:false};
  t.borders.assign({style:'solid',fill:C.line,width:1});
  for(let r=0;r<vals.length;r++) for(let c=0;c<vals[0].length;c++){
    const cell=t.getCell(r,c);
    cell.fill=r===0?C.navy:(r%2===0?C.pale:C.white);
    cell.text.style={typeface:font,fontSize:r===0?headerSize:bodySize,bold:r===0,color:r===0?C.white:C.ink,autoFit:'none'};
  }
  return t;
}

// 1. Title and focus
{
  const s=pres.slides.add(); s.background.fill=C.white;
  allSlides.push(s);
  text(s,'VeriFlow',70,74,700,70,56,C.navy,true);
  text(s,'Pipeline behavior under schema migration',70,157,800,125,45,C.navy,true);
  line(s,70,303,865,303,C.teal,5);
  text(s,'When can a lossy record migration still preserve a pipeline\'s decisions and selected values?',70,337,795,112,28,C.ink);
  text(s,'A migration-time checker for typed CSV pipelines',70,538,770,42,23,C.teal,true);
  text(s,'Research brief  •  October 2026',70,632,700,29,17,C.muted);
  await icon(s,'database',943,188,210);
  notes(s,'VeriFlow already compiles typed CSV pipelines. The research addition is a migration-time impact checker for one explicit schema change and well-typed legacy rows. The old row remains available when checking a guard. Internal source: docs/presentation-brief.md. Icon: Google Material Symbols database, Apache 2.0, https://github.com/google/material-design-icons .');
}

// 2. Problem mind map
{
  const s=base('The problem: record loss is too coarse',2);
  await icon(s,'schema',89,175,90);
  const root=node(s,'Schema change',210,201,245,82,C.cyan,C.teal,24);
  const a=node(s,'Record-level label\n“lossy”',615,153,350,88,C.white,C.orange,22);
  const b=node(s,'Pipeline observation\nmay be preserved',615,304,350,88,C.white,C.teal,22);
  s.shapes.connect(root,a,{kind:'elbow',fromSide:'right',toSide:'left',line:{style:'solid',fill:C.orange,width:2}});
  s.shapes.connect(root,b,{kind:'elbow',fromSide:'right',toSide:'left',line:{style:'solid',fill:C.teal,width:2}});
  text(s,'Record reconstruction and pipeline behavior answer different questions.',70,469,1090,47,27,C.navy,true);
  text(s,'A small sample can reveal a failure; agreement on sampled rows cannot prove safety.',70,528,1080,58,23,C.ink);
  text(s,'Observation includes selected typed values, filtering, validation failures, and expression errors.',70,608,1110,36,18,C.muted);
  notes(s,'Problem statement: the existing VeriFlow evolution label summarizes record loss, while the new checker studies the behavior of a specified pipeline. PRISM already addresses schema impact and legacy query rewriting, so neither is claimed as new. PRISM: https://www.vldb.org/pvldb/vol1/1453939.pdf . Internal source: docs/paper-research-context.md. Icon: Google Material Symbols schema, Apache 2.0, https://github.com/google/material-design-icons .');
}

// 3. Concrete difference
{
  const s=base('One mapping, two pipeline outcomes',3);
  text(s,'Old decimal score = 40.7',78,160,570,50,31,C.navy,true);
  text(s,'Migrated integer score = 40',650,160,540,50,31,C.teal,true);
  nativeTable(s,[
    ['Pipeline condition','Before migration','After migration','Outcome'],
    ['score >= 40','true','true','preserved'],
    ['score > 40','true','false','breaking at 40.7']
  ],75,252,1128,238,[390,235,235,268],20,20);
  text(s,'For an atomic strict threshold, the unsafe gap is 40 < score < 41.',78,528,1110,52,27,C.orange,true);
  text(s,'A guard excludes that gap. The non-strict rule is proved for finite old decimals at positive integer thresholds.',78,591,1115,55,21,C.ink);
  notes(s,'The numeric mapping truncates finite Decimal values toward zero. For integer k >= 1, x >= k and x < k are invariant under truncation. For an atomic x > k or x <= k, truth changes exactly when k < x < k+1; the guard excludes that interval. The illustrative old value 40.7 maps to 40. Proof and exact assumptions: docs/paper-draft.md and docs/impact-method.md.');
}

// 4. Prior work table
{
  const s=base('Prior work and this project’s narrower question',4);
  nativeTable(s,[
    ['Prior work','Established focus','Question examined here'],
    ['PRISM (2008)','Schema impact, migration, query rewriting','Typed pipeline behavior after lossy conversion'],
    ['Fan et al. (2012)','Selected-information preservation','Guards for validation, filtering, and output'],
    ['Mediator (2017)','Application equivalence across schemas','Safe rows in one-step adapted execution'],
    ['Conditional equivalence (2010)','Agreement on a subset of inputs','Migration-time guards and CSV coverage']
  ],70,154,1140,405,[215,455,470],19,19);
  text(s,'These are established ideas. The candidate contribution is their scoped, executable combination for VeriFlow.',73,585,1128,71,22,C.navy,true);
  notes(s,'Sources: PRISM https://www.vldb.org/pvldb/vol1/1453939.pdf ; Fan, Geerts, and Zheng https://www.pure.ed.ac.uk/ws/portalfiles/portal/17752772/paper_viewd.pdf ; Mediator https://arxiv.org/abs/1710.07660 ; Conditional Equivalence https://www.microsoft.com/en-us/research/publication/conditional-equivalence/ . BiDEL/InVerDa also covers bidirectional coexisting schema versions: https://arxiv.org/abs/1608.05564 . The table identifies differences in research focus; it does not establish absence of a feature in all related work. Independent expert review is still required for a final novelty claim.');
}

// 5. Contract diagram
{
  const s=base('The behavior preservation contract',5);
  await icon(s,'rule',1113,143,78);
  text(s,'G(s)  ∧  F(s) defined   ⇒',78,161,1100,58,32,C.teal,true);
  text(s,'Obs(P, s)  =  Obs(P, A(F(s)))',78,226,1120,70,42,C.navy,true);
  line(s,78,310,1190,310,C.line,2);
  text(s,'s',95,356,85,42,25,C.teal,true); text(s,'well-typed old row',208,356,930,42,24,C.ink);
  text(s,'F',95,414,85,42,25,C.teal,true); text(s,'explicit forward migration',208,414,930,42,24,C.ink);
  text(s,'A',95,472,85,42,25,C.teal,true); text(s,'partial adapter used by legacy pipeline P',208,472,930,42,24,C.ink);
  text(s,'Obs',95,530,85,42,25,C.teal,true); text(s,'typed outputs, filter decision, validation message, or expression error',208,530,950,65,24,C.ink);
  text(s,'The guard G is checked while the old row is available.',78,631,1080,37,21,C.orange,true);
  notes(s,'This is the actual migration-time claim, not equivalence of arbitrary new-schema programs. A preserved result uses G=true; a conditional result provides a sufficient executable G. The adapted path is F then partial A then legacy P. The domain is well-typed legacy rows with defined mapping. Exact CSV spelling and malformed rows are out of scope. See docs/impact-method.md. Icon: Google Material Symbols rule, Apache 2.0, https://github.com/google/material-design-icons .');
}

// 6. Method mind map
{
  const s=base('The migration impact checker',6);
  const root=node(s,'Impact check',491,327,300,82,C.cyan,C.teal,26);
  const a=node(s,'Trace executed fields\nlet, require, keep, select',73,169,385,100,C.white,C.teal,20);
  const b=node(s,'Apply sound rules\nexact values and thresholds',820,169,385,100,C.white,C.teal,20);
  const c=node(s,'Guard or replay\nsafe subset or breaking collision',73,476,385,100,C.white,C.orange,20);
  const d=node(s,'Readiness report\nadmitted rows in a legacy CSV',820,476,385,100,C.white,C.green,20);
  for(const [target,from,to,color] of [[a,'left','right',C.teal],[b,'right','left',C.teal],[c,'left','right',C.orange],[d,'right','left',C.green]])
    s.shapes.connect(root,target,{kind:'elbow',fromSide:from,toSide:to,line:{style:'solid',fill:color,width:2}});
  text(s,'Result: preserved  ·  conditional  ·  breaking  ·  unknown',187,615,960,40,23,C.navy,true);
  notes(s,'The checker traces every executed operation including derived let fields. Exact reconstruction and supported threshold rules produce a proof or sufficient guard. Breaking is reported only after a valid collision replays through production execution. A bounded witness search with no collision returns unknown. The evolved runner refuses unknown and records guarded-out rows. The readiness report measures guard coverage on a supplied CSV, which is empirical utility, not part of the proof. See docs/impact-method.md and evaluation/README.md.');
}

// 7. Pilot evidence
{
  const s=base('Pilot results on 5,926 distinct rows',7);
  await icon(s,'query_stats',1118,137,72);
  text(s,'Real rows; injected schema changes. x is each dataset’s mapped decimal field.',73,140,1030,44,21,C.orange,true);
  nativeTable(s,[
    ['Dataset','Rows','x >= k','x > k guard admits'],
    ['Abalone','4,177','preserved','2,782 / 4,177'],
    ['Iris','150','preserved','99 / 150'],
    ['Red Wine Quality','1,599','preserved','1,214 / 1,599']
  ],73,220,1134,292,[286,143,276,429],19,19);
  text(s,'10 cases',76,543,242,53,32,C.navy,true);
  text(s,'3 preserved',329,543,288,53,32,C.green,true);
  text(s,'1 unknown',626,543,263,53,32,C.orange,true);
  text(s,'0 observed guard violations',76,602,900,43,25,C.teal,true);
  text(s,'8 negative controls and 4 CSV parity checks passed. Source: evaluation/results.json, 8 Oct 2026.',76,650,1080,28,16,C.muted);
  notes(s,'There are three public UCI datasets and 5,926 distinct source rows. The ten cases include three safe non-strict numeric cases, nearby strict and selected-value cases, and one unproved split case. All mappings are synthetic/injected. No row admitted by a proof guard changed typed observation in the pilot. Eight predeclared controls and four CSV parity checks passed. The universal guarantee comes from rule premises and proof, not from this finite pilot. Sources: evaluation/README.md, evaluation/results.json, evaluation/negative-controls.json, evaluation/csv-parity.json. UCI source pages: https://archive.ics.uci.edu/dataset/1/abalone , https://archive.ics.uci.edu/dataset/53/iris , https://archive.ics.uci.edu/dataset/186/wine+quality . Icon: Google Material Symbols query_stats, Apache 2.0, https://github.com/google/material-design-icons .');
}

// 8. Candidate novelty and limits
{
  const s=base('Contribution and limits',8);
  await icon(s,'warning',1119,138,72);
  text(s,'Candidate contribution',74,164,590,49,30,C.teal,true);
  text(s,'An executable migration-time behavior contract that combines sound sufficient guards, replayed witnesses, and measured guard coverage for typed row pipelines.',74,226,540,214,28,C.navy,true);
  line(s,655,162,655,517,C.line,2);
  text(s,'Current boundary',704,164,490,49,30,C.orange,true);
  text(s,'One explicit mapping and well-typed legacy rows.\nAdapted execution uses the old pipeline through an adapter.\nNo guarantee for future new-only rows.\nSplit/merge effects outside proved rules remain unknown.\nDataset migrations are synthetic.',704,225,475,301,22,C.ink);
  text(s,'Next: independent proof and novelty review, then a documented real migration history if available.',74,554,1095,72,24,C.navy,true);
  text(s,'Full references and reproducibility details are in the speaker notes.',74,654,1085,28,16,C.muted);
  notes(s,'Candidate novelty is deliberately qualified. PRISM, selected-information preservation, application equivalence, conditional equivalence, and bidirectional adapters are prior art. The current contribution is a narrow implemented combination for migration-time validation/filter/projection. Do not claim automatic query rewriting, standalone new-schema execution, arbitrary future-row guarantees, or an observed organizational schema history. See docs/paper-draft.md, docs/council-review-2026-10-08.md, docs/paper-research-tasks.md. Icon: Google Material Symbols warning, Apache 2.0, https://github.com/google/material-design-icons .');
}

await fs.mkdir(path.dirname(FINAL_PPTX),{recursive:true});
const staging=path.join(workspaceDir,'presentations','.build','validation');
await fs.mkdir(staging,{recursive:true});
const candidatePath=path.join(TMP_DIR,'veriflow-research-candidate.pptx');
await (await PresentationFile.exportPptx(pres)).save(candidatePath);
for(let i=0;i<allSlides.length;i++){
  const data=await allSlides[i].export({format:'png',scale:1});
  await fs.writeFile(path.join(TMP_DIR,`slide-${i+1}.png`),new Uint8Array(await data.arrayBuffer()));
}
if (process.env.PREVIEW_ONLY === '1') process.exit(0);
const result=await finalizePresentation({
  explicitTotalSlideCount:8,
  requiredNativeTableOwnerSlides:[3,4,7],
  requiredNativeChartOwnerSlides:[],
  workspaceDir,
  candidatePath,
  finalPath:FINAL_PPTX,
  pythonExecutable:RUNTIME_PYTHON,
  integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','3','--require-native-table-slide','4','--require-native-table-slide','7'],
  fontPolicy:{basis:'design',families:[font]},
  verifyArtifactToolImport:true,
  receiptPath:path.join(staging,`${path.basename(FINAL_PPTX)}.validation.json`),
});
console.log(JSON.stringify({final:FINAL_PPTX,result}));
