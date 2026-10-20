"""RRF 结果身份隔离、等价证据/多事实指标测试，不访问模型或 Chroma。"""
import pytest
from rag.rrf_fusion import rrf_fuse
from evals.retrieval.retrieval_eval import score_question, aggregate, search_one


def _row(cid, kb='A', **extra):
    return {'chroma_id':cid,'content':cid,'metadata':{'knowledge_base':kb},**extra}


def _result(cid, kb='A'):
    return {'chunk_id':cid,'knowledge_base_name':kb,'source':'x.pdf','page':1}


def test_rrf_scores_union_by_id_and_promotes_agreement():
    b=[_row('a',bm25_score=9),_row('b',bm25_score=6),_row('c',bm25_score=1)]
    d=[_row('b',score=0.1),_row('x',score=0.2),_row('a',score=0.3)]
    out=rrf_fuse([b,d],top_k=10)
    assert [x['chroma_id'] for x in out][:2]==['b','a']
    assert len(out)==4
    assert out[0]['bm25_rank']==2 and out[0]['dense_rank']==1
    assert out[0]['rrf_score'] == pytest.approx(1/62 + 1/61)
    assert out[0]['semantic_distance'] == 0.1


def test_same_text_different_chunks_are_not_merged():
    a={'chroma_id':'a','content':'相同文本','metadata':{'knowledge_base':'A'},'bm25_score':1}
    b={'chroma_id':'b','content':'相同文本','metadata':{'knowledge_base':'B'},'score':0.1}
    out=rrf_fuse([[a],[b]], top_k=5)
    assert {x['chroma_id'] for x in out} == {'a','b'}


def test_duplicate_within_one_ranking_not_double_counted():
    out=rrf_fuse([[_row('a'), _row('a')]], top_k=3)
    assert len(out)==1
    assert out[0]['rrf_score']==pytest.approx(1/61)


def test_missing_chroma_id_is_rejected():
    with pytest.raises(ValueError):
        rrf_fuse([[{'content':'文本'}]], top_k=2)


def test_fact_alternatives_are_or_not_and():
    q={'id':'FD-008','task_type':'answerable','knowledge_bases':['A'],
       'evidence':[], 'gold_chunk_ids':None,
       'gold_evidence_groups':[{'fact':'快捷键','chunk_ids':['page35-a','page35-b','page78']}]}
    out=score_question(q,[_result('page78')],3)
    assert out['fact_hit'] and out['fact_all'] and out['fact_coverage']==1.0
    assert out['fact_mrr']==1.0
    assert 'strict_chunk_recall' not in out


def test_multifact_requires_all_and_and_mrr():
    q={'task_type':'answerable','knowledge_bases':['A'],'evidence':[],
       'gold_evidence_groups':[{'fact':'2','chunk_ids':['c2']},{'fact':'5','chunk_ids':['c5','c5b']}]}
    rows=[_result('noise'), _result('c2'), _result('c5b')]
    at2=score_question(q,rows,2)
    assert at2['fact_coverage']==0.5 and not at2['fact_all']
    assert at2['fact_mrr']==pytest.approx(0.25)
    at3=score_question(q,rows,3)
    assert at3['fact_all'] and at3['fact_coverage']==1
    assert at3['fact_mrr']==pytest.approx((1/2+1/3)/2)


def test_aggregates_count_only_labeled_cases():
    annotated={'task_type':'answerable','knowledge_bases':['A'],'evidence':[],
        'gold_evidence_groups':[{'fact':'x','chunk_ids':['a']}]}
    unlabeled={'task_type':'answerable','knowledge_bases':['A'],'evidence':[]}
    details=[{'method':'rrf','task_type':'answerable','latency_ms':4,'question':annotated,'results':[_result('a')]},
             {'method':'rrf','task_type':'answerable','latency_ms':6,'question':unlabeled,'results':[_result('a')]}]
    s=aggregate(details,[3])[0]
    assert s['fact_coverage_count']==1
    assert s['fact_coverage']==1.0
