"""独立纯逻辑测试；不加载 BGE、不访问数据库、不调用 Qwen。"""
import json
from pathlib import Path
from evals.benchmark_v1.bind_gold import bind_one, bind_questions
from evals.benchmark_v1.evaluate import summarize
from evals.benchmark_v1.validate import validate


def q():
    return {'id':'X1','split':'dev','task_type':'answerable',
            'quality_tier':'explicit','category':'faq','knowledge_bases':['A'],
            'question':'怎么启动终端？','evidence':[{'source':'a.pdf','page':7,'quote':'启动终端 Ctrl+Alt+T'}],
            'gold_evidence_groups':[]}


def test_binder_matches_same_pdf_page_and_kb():
    hits=[{'id':'ok','content':'启动终端 Ctrl+Alt+T','metadata':{'source':'a.pdf','page':6}},
          {'id':'wrong-page','content':'启动终端 Ctrl+Alt+T','metadata':{'source':'a.pdf','page':7}},
          {'id':'wrong-file','content':'启动终端 Ctrl+Alt+T','metadata':{'source':'b.pdf','page':6}}]
    r=bind_questions([q()],{'A':hits})[0]
    assert r['binding_status']=='bound'
    assert r['gold_evidence_groups'][0]['chunk_ids']==['ok']


def test_unmatched_not_counted_as_zero():
    r=bind_one(q(),[])
    assert r['binding_status']=='partial_or_missing'
    assert r['gold_evidence_groups']==[]


def test_multi_fact_and_groups():
    item=q()
    item['evidence'] += [{'source':'a.pdf','page':8,'quote':'默认以图形界面登录','fact':'运行级别5'}]
    hits=[{'id':'c1','content':'启动终端 Ctrl+Alt+T','metadata':{'source':'a.pdf','page':6}},
          {'id':'c2','content':'默认以图形界面登录','metadata':{'source':'a.pdf','page':7}}]
    r=bind_one(item,hits)
    assert len(r['gold_evidence_groups'])==2
    assert all(g['chunk_ids'] for g in r['gold_evidence_groups'])


def test_negative_no_gold():
    a=q();a['task_type']='negative';a['evidence']=[]
    assert bind_one(a,[])['binding_status']=='not_applicable'


def test_alternative_evidence_binds_with_or_semantics():
    item = q()
    primary = dict(item['evidence'][0])
    alternative = {'source': 'b.pdf', 'page': 78, 'quote': 'Crtl+Alt+T 来打开终端。'}
    item['evidence'][0]['alternatives'] = [alternative, dict(alternative)]
    hits = [
        {'id': 'alternative', 'content': 'Crtl+Alt+T\n来打开终端。',
         'metadata': {'source': r'C:\manuals\b.pdf', 'page': 77}},
        {'id': 'wrong-page', 'content': alternative['quote'],
         'metadata': {'source': 'b.pdf', 'page': 78}},
        {'id': 'wrong-source', 'content': alternative['quote'],
         'metadata': {'source': 'a.pdf', 'page': 77}},
        {'id': 'invalid-page', 'content': alternative['quote'],
         'metadata': {'source': 'b.pdf', 'page': None}},
    ]
    result = bind_one(item, hits)
    assert result['binding_status'] == 'bound'
    assert result['gold_evidence_groups'] == [
        {**primary, 'fact': '来源原文证据', 'chunk_ids': ['alternative']}
    ]
    hits.append({'id': 'primary', 'content': primary['quote'],
                 'metadata': {'source': 'a.pdf', 'page': 6}})
    assert bind_one(item, hits)['gold_evidence_groups'][0]['chunk_ids'] == ['alternative', 'primary']


def test_alternative_evidence_preserves_required_facts():
    from evals.retrieval.retrieval_eval import score_question

    item = q()
    item['evidence'][0]['alternatives'] = [
        {'source': 'a.pdf', 'page': 78, 'quote': 'Crtl+Alt+T'}
    ]
    item['evidence'].append({'source': 'a.pdf', 'page': 8, 'quote': '默认以图形界面登录'})
    hits = [{'id': 'terminal', 'content': 'Crtl+Alt+T',
             'metadata': {'source': 'a.pdf', 'page': 77}}]
    incomplete = bind_one(item, hits)
    assert incomplete['binding_status'] == 'partial_or_missing'
    assert incomplete['gold_evidence_groups'] == []
    assert incomplete['unmatched_evidence'] == [
        {**item['evidence'][1], 'fact': '来源原文证据'}
    ]
    hits.append({'id': 'login', 'content': '默认以图形界面登录',
                 'metadata': {'source': 'a.pdf', 'page': 7}})
    bound = bind_one(item, hits)
    assert bound['binding_status'] == 'bound'
    assert len(bound['gold_evidence_groups']) == 2
    metrics = score_question(bound, [
        {'chunk_id': 'terminal', 'source': 'a.pdf', 'page': 78, 'knowledge_base_name': 'A'}
    ], 3)
    assert metrics['fact_coverage'] == 0.5
    assert metrics['fact_all'] is False


def test_summary_displays_denominators():
    base={'method':'hybrid','task_type':'answerable','category':'faq','quality_tier':'explicit',
          'retrieval_ms':5,'expand_ms':0,'context_chunks':3,'context_chars':100}
    bound={**base,'binding_status':'bound',
           'base_metrics':{'fact_coverage':1.0,'fact_all':True},
           'final_metrics':{'fact_coverage':1.0,'fact_all':True,'fact_mrr':0.5}}
    missed={**base,'binding_status':'partial_or_missing','base_metrics':{},'final_metrics':{}}
    stats=summarize([bound,missed])['methods']['hybrid']
    assert stats['final_fact_coverage']=={'value':1.0,'n':1}
    assert stats['unbound_answerable_questions']==1


def test_dataset_integrity():
    path=Path(__file__).resolve().parents[1]/'data'/'enterprise_all.jsonl'
    rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    report=validate(rows)
    assert report['total']>=300
    assert report['errors']==[]
    assert report['splits']['dev']>200 and report['splits']['eval']>40
