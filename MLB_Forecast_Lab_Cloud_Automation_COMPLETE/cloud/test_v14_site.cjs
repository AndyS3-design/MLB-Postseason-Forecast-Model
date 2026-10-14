// Check the exact helper functions shipped in the dashboard, including the
// immutable October 14 V13 source record, without starting a browser.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
const begin=html.indexOf('function exactScoreCandidates(g){');
const end=html.indexOf('function renderGame(g){');
assert(begin>=0&&end>begin,'Site distribution helpers not found');
const context={};
vm.runInNewContext(html.slice(begin,end)+';this.helpers={exactScoreCandidates,runTotalLines};',context);
const {exactScoreCandidates,runTotalLines}=context.helpers;
const saved=JSON.parse(fs.readFileSync(path.join(root,'cloud_records/preliminary_revisions/849811_20261014T202744Z.json'),'utf8'));
const mode=exactScoreCandidates(saved)[0];
assert.equal(mode.home,3);
assert.equal(mode.away,2);
assert(Math.abs(mode.probability-0.05233333333)<1e-7);
assert(mode.probability>saved.projected_score.exact_probability);
const rows=runTotalLines(saved);
assert.equal(rows.length,4);
for(const [idx,line,under] of [[0,3.5,.14375],[1,4.5,.207],[2,5.5,.3524166667],[3,6.5,.436]]){
  assert.equal(rows[idx].line,line);
  assert(Math.abs(rows[idx].under-under)<1e-7);
  assert(Math.abs(rows[idx].over+rows[idx].under-1)<1e-7);
}
assert.equal(runTotalLines({total_distribution:{'5':.3,'7':.3}}).length,0);
assert.equal(exactScoreCandidates({score_grid:{cells:Array.from({length:11},(_,h)=>Array.from({length:11},(_,a)=>h===10&&a===0?.5:h===3&&a===2?.2:0))}}).length,0);
const future={modal_exact_scores:[{home:4,away:2,probability:.04},{home:2,away:3,probability:.07}]};
assert.equal(exactScoreCandidates(future)[0].probability,.07);
assert(html.includes('HIGHEST-PROBABILITY EXACT SCORE'));
assert(html.includes('Over / under total runs'));
console.log('V14 UI passed: archived true score mode and all four O/U probabilities');
