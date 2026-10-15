// Full scoring contract for V20 winner-aligned projection, using saved Oct 14 data.
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'site/index.html'),'utf8');
const begin=html.indexOf('function exactScoreCandidates(g){');
const end=html.indexOf('function renderGame(g){');
assert(begin>=0&&end>begin,'Score presentation helper interval not found');
const sandbox={};
vm.runInNewContext(html.slice(begin,end)+';this.helpers={exactScoreCandidates,winnerAlignedExactScore,runTotalLines};',sandbox);
const {exactScoreCandidates,winnerAlignedExactScore,runTotalLines}=sandbox.helpers;
const archive=path.join(root,'cloud_records/preliminary_revisions/849811_20261014T202744Z.json');
const original=fs.readFileSync(archive);
const g=JSON.parse(original);
assert.equal(g.away_name,'Milwaukee Brewers');
assert.equal(g.home_name,'Los Angeles Dodgers');
assert.equal(g.predicted_home_win,0.46225);
const favorite=winnerAlignedExactScore(g);
assert(favorite,'Archived forecast must support unambiguous winner-aligned mode');
assert.equal(favorite.away,3);
assert.equal(favorite.home,2);
assert(Math.abs(favorite.probability-.04225)<1e-10);
assert(Math.abs(favorite.conditional_probability-.04225/(1-.46225))<1e-10);
const unconditional=exactScoreCandidates(g)[0];
assert.equal(unconditional.away,2);
assert.equal(unconditional.home,3);
assert(Math.abs(unconditional.probability-.05233333333)<1e-7);
assert(favorite.away>favorite.home,'Headline must FAVOR model winning team (Brewers)');
assert(unconditional.away<unconditional.home,'Secondary mode may favor underdog Dodgers');
const over=runTotalLines(g).find(x=>x.line===5.5);
assert(over);
assert(Math.abs(over.over-.6475833333333333)<1e-8);
assert(Math.abs(over.under-.3524166666666667)<1e-8);
assert(html.includes('MODEL WINNER PICK'));
assert(html.includes('MOST LIKELY EXACT SCORE IF PICK WINS'));
assert(html.includes('Over 5.5 runs: '));
assert(html.includes('combined winner + over bet'));
assert(html.includes('overall most frequent exact score'));
assert(!html.includes('MODEL FAVORITE</span>'));

// Current V20 records should use exact scored draws, never an assumed Poisson mode.
const future={predicted_home_win:.78,favorite_aligned_score:
  {home:4,away:2,probability:.068,winner_side:'home',conditional_probability:.068/.78},
  score_grid:{cells:[[.1]]}};
const direct=winnerAlignedExactScore(future);
assert.equal(direct.home,4);
assert.equal(direct.away,2);
assert(Math.abs(direct.conditional_probability-.068/.78)<1e-9);
assert.equal(winnerAlignedExactScore({...future,predicted_home_win:.22}),null,
 'A saved mode belonging to the wrong favorite must not be shown');
assert.equal(winnerAlignedExactScore({predicted_home_win:.75,modal_exact_scores:[
  {home:1,away:2,probability:.4}]}),null,
  'Insufficient top-seven ranking must NOT guess a winner-aligned score');
// 10+ bin is an aggregate, never claim it is an individual most probable score.
const cells=Array.from({length:11},()=>Array(11).fill(0));
cells[3][2]=.26;cells[10][0]=.45;cells[0][1]=.29;
assert.equal(winnerAlignedExactScore({predicted_home_win:.75,score_grid:{cells}}),null,
 'Capped tail could conceal a higher exact score');
assert.equal(fs.readFileSync(archive).compare(original),0,'Never rewrite archival pregame data');
console.log('V20 UI PASSED: Brewers 53.8% winner with Brewers 3-2 aligned score; Dodgers 3-2 full-mode preserved; Over 5.5 64.8%.');
