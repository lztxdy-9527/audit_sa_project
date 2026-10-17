"""Read-only verification of one explicit namespace and its declared references."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import types

HISTORY_VERSION='TASK-037-human-initial-judgment-history-1.0'
EXPECTATIONS_VERSION='TASK-037-human-initial-judgment-history-expectations-1.0'
STATUS='HUMAN_INITIAL_JUDGMENT_NAMESPACE_INSPECTED'
SCOPE='DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY'
NOTE='仅核验本次声明命名域的现存成功快照及已声明历史引用；不证明历史从未删失，不批准执行，不认证身份，不开放AI或终判。'
ROOT=Path(__file__).absolute().parents[1]
HISTORY_PATH=Path(__file__).absolute()
STORE_PATH=ROOT/'scripts/store_demo_human_initial_judgment.py'
STORE_SHA256='a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c'
EXPECTED_KEYS=('expectations_version','expected_namespace_relative','expected_declared_scope','expected_entries')
INDEX_KEYS=('event_id','batch_id','record_fingerprint','binding_fingerprint')
VERIFICATION_KEYS=('status','scope','identity','record_fingerprint','manifest_file_sha256','technical_registration',
                   'component_bindings','files','boundaries','snapshots','judgment_result')
BOUNDARIES=('workflow_connected','execution_allowed','next_step_allowed','ai_enabled','identity_authenticated',
            'source_authenticity_proven','audit_conclusion_formed','final_judgment_recorded','global_history_completeness_proven')

class HumanInitialJudgmentHistoryBlocked(Exception):
    def __init__(self,field,reason):
        self.field,self.reason,self.reasons=field,reason,[reason]
        super().__init__(f'{field}: {reason}')

class HumanInitialJudgmentHistoryError(Exception):
    def __init__(self,stage,reason):
        self.stage,self.reason,self.reasons=stage,reason,[reason]
        super().__init__(f'[{stage}] {reason}')

def _block(field,reason):raise HumanInitialJudgmentHistoryBlocked(field,reason)
def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _fp(value):return _sha(_canonical(value))
def _keys(value,keys,field):
    if type(value) is not dict:_block(field,'必须为严格对象')
    for key in keys:
        if key not in value:_block(field+'.'+key,'缺少必需字段')
    if any(type(k) is not str for k in value):_block(field,'对象键必须为字符串')
    for key in sorted(value):
        if key not in keys:_block(field+'.'+key,'未知字段')
def _text(value,field):
    if type(value) is not str or not value.strip():_block(field,'必须为非空原字符串')
    try:value.encode('utf-8')
    except UnicodeError as exc:raise HumanInitialJudgmentHistoryBlocked(field,'必须为合法UTF-8') from exc
def _relative(value,field,leaf=False):
    _text(value,field)
    if '\\' in value or ':' in value or '\x00' in value:_block(field,'不是安全相对路径')
    parts=value.split('/')
    if any(p in ('','.','..') for p in parts) or (leaf and len(parts)!=1):_block(field,'必须为安全叶名' if leaf else '必须为安全项目相对POSIX路径')
def _hex(value,field):
    if type(value) is not str or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):_block(field,'必须完整64位小写十六进制')
def _equal(value,expected,field):
    if _canonical(value)!=_canonical(expected):_block(field,'与本次独立绑定读数不一致')
def _expectations(value):
    _keys(value,EXPECTED_KEYS,'expectations')
    if value['expectations_version']!=EXPECTATIONS_VERSION or type(value['expectations_version']) is not str:
        _block('expectations.expectations_version','版本常量不符')
    _relative(value['expected_namespace_relative'],'expectations.expected_namespace_relative')
    _text(value['expected_declared_scope'],'expectations.expected_declared_scope')
    entries=value['expected_entries']
    if type(entries) is not list:_block('expectations.expected_entries','必须为严格列表')
    previous=None
    for i,item in enumerate(entries):
        field=f'expectations.expected_entries[{i}]';_keys(item,('relative','manifest_file_sha256'),field)
        _relative(item['relative'],field+'.relative',leaf=True);_hex(item['manifest_file_sha256'],field+'.manifest_file_sha256')
        raw=item['relative'].encode('utf-8')
        if previous is not None and raw<=previous:_block(field+'.relative','必须唯一且按UTF-8严格升序')
        previous=raw

def _load_store():
    # Before loading the frozen buffer, check the fixed project's source chain.
    for node in (*reversed(STORE_PATH.parents),STORE_PATH):
        info=node.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:_block('component_bindings.store_file_sha256','固定源码链含链接/reparse')
    raw=STORE_PATH.read_bytes()
    if _sha(raw)!=STORE_SHA256:_block('component_bindings.store_file_sha256','冻结store身份不符')
    module=types.ModuleType('_task037_frozen_initial_judgment_store');module.__file__=str(STORE_PATH)
    exec(compile(raw,str(STORE_PATH),'exec'),module.__dict__)
    return module,raw

def _store_call(store,prefix,function,*args,**kwargs):
    try:return function(*args,**kwargs)
    except store.HumanInitialJudgmentStoreBlocked as exc:
        raise HumanInitialJudgmentHistoryBlocked(prefix+'.'+exc.field if prefix else exc.field,exc.reason) from exc
    except store.HumanInitialJudgmentStoreError as exc:
        error=HumanInitialJudgmentHistoryError(exc.stage,exc.reason)
        if hasattr(exc,'secondary_errors'):error.secondary_errors=copy.deepcopy(exc.secondary_errors)
        raise error from exc

def _members(store,target,expected):
    names=_store_call(store,'namespace_dir',store._layout,target)
    for name in names:
        p=target/name;_store_call(store,'namespace_dir',store._reject_chain,p,name)
        info=p.lstat()
        if not stat.S_ISDIR(info.st_mode):_block('namespace_dir.'+name,'成员必须为正常直接记录叶目录')
    ordered=sorted(names,key=lambda s:s.encode('utf-8'))
    if ordered!=[x['relative'] for x in expected]:_block('expectations.expected_entries','与实际域成员集合不完整相等')
    return ordered

def _leaf_layout(store,leaf,field):
    names=_store_call(store,field,store._layout,leaf)
    if 'failure.json' in names:_block(field+'.failure.json','失败现场优先拒绝，不消费manifest或跳过该叶')
    if names!=list(store.FILES):_block(field+'.files','必须恰六文件，无子树/缺失/未知项')
    for name in store.FILES:_store_call(store,field,store._normal_file,leaf/name)

def _capture_leaf(store,leaf,field):
    _leaf_layout(store,leaf,field);buffers={};objects={}
    for name in store.FILES:
        raw=_store_call(store,field,store._read_bytes,leaf/name)
        buffers[name]=raw;objects[name]=_store_call(store,field,store._parse,raw,name)
    return buffers,objects

def _bind_verification(store,result,buffers,objects,components,field):
    _keys(result,VERIFICATION_KEYS,field+'.verification')
    file_entries=[{'relative':n,'byte_size':len(buffers[n]),'file_sha256':_sha(buffers[n]),'object_fingerprint':_fp(objects[n])} for n in store.FILES]
    _store_call(store,field,store._equal,result['manifest_file_sha256'],_sha(buffers['manifest.json']),'verification.manifest_file_sha256')
    _store_call(store,field,store._equal,result['files'],file_entries,'verification.files')
    snapshots={k:objects[k+'.json'] for k in ('submission','materials','expectations','prior_history')}
    _store_call(store,field,store._equal,result['snapshots'],snapshots,'verification.snapshots')
    _store_call(store,field,store._equal,result['judgment_result'],objects['judgment_result.json'],'verification.judgment_result')
    manifest=objects['manifest.json'];_store_call(store,field,store._validate_manifest,manifest)
    _equal(manifest['component_bindings'],components,field+'.manifest.component_bindings')
    expected={'status':store.VERIFIED,'scope':store.SCOPE,'identity':manifest['identity'],
        'record_fingerprint':manifest['fingerprints']['record_fingerprint'],'manifest_file_sha256':_sha(buffers['manifest.json']),
        'technical_registration':manifest['technical_registration'],'component_bindings':components,'files':file_entries,
        'boundaries':manifest['boundaries'],'snapshots':snapshots,'judgment_result':objects['judgment_result.json']}
    _store_call(store,field,store._equal,result,expected,'verification')
    record=_store_call(store,field,store._validate_result,result['judgment_result'])
    _keys(record['history_binding'],('declared_scope','prior_history_fingerprint'),field+'.record.history_binding')
    _keys(snapshots['prior_history'],('declared_complete','declared_scope','records'),field+'.prior_history')
    return record,snapshots['prior_history']

def _build_return(namespace,scope,entries,components,verified,index):
    prior={'declared_complete':True,'declared_scope':scope,'records':index}
    inventory={'namespace_relative':namespace,'declared_scope':scope,'entries':entries}
    return copy.deepcopy({'history_version':HISTORY_VERSION,'status':STATUS,'scope':SCOPE,'namespace_relative':namespace,
        'prior_history':prior,'prior_history_fingerprint':_fp(prior),'inventory':inventory,'inventory_fingerprint':_fp(inventory),
        'component_bindings':components,'verified_snapshots':verified,'boundaries':{k:False for k in BOUNDARIES},'note':NOTE})

def _terminal_confirm(store,raw_namespace,target,expected,starting,captures,history_bytes):
    _store_call(store,'',store._confirm_components,captures)
    _store_call(store,'',store._normal_file,HISTORY_PATH)
    if _store_call(store,'',store._read_bytes,HISTORY_PATH,'final_read')!=history_bytes:_block('component_bindings.history_file_sha256','history源码较开始变化')
    actual=_store_call(store,'namespace_dir',store._resolve_leaf,raw_namespace,True)
    if actual!=target:_block('namespace_dir','原路径解析目标变化')
    _members(store,target,expected)
    for i,item in enumerate(expected):
        leaf=target/item['relative'];field=f'entries[{i}]';_leaf_layout(store,leaf,field)
        for name,raw in starting[item['relative']].items():
            if _store_call(store,field,store._read_bytes,leaf/name,'final_read')!=raw:_block(field+'.'+name,'末次字节与本次起始缓冲不符')
        _leaf_layout(store,leaf,field)
    _members(store,target,expected)

def inspect_human_initial_judgment_history(namespace_dir, *, expectations:dict)->dict:
    stage='expectations'
    try:
        _expectations(expectations);before=copy.deepcopy(expectations)
        stage='load_store';store,store_bytes=_load_store()
        stage='components';captures=_store_call(store,'',store._capture_components)
        if captures['store_file_sha256']['bytes']!=store_bytes:_block('component_bindings.store_file_sha256','store较加载缓冲变化')
        _store_call(store,'',store._normal_file,HISTORY_PATH)
        history_bytes=_store_call(store,'',store._read_bytes,HISTORY_PATH,'bindings')
        components={k:_sha(v['bytes']) for k,v in captures.items()}
        stage='namespace';target=_store_call(store,'namespace_dir',store._resolve_leaf,namespace_dir,True)
        namespace=target.relative_to(ROOT).as_posix()
        _equal(namespace,before['expected_namespace_relative'],'expectations.expected_namespace_relative')
        names=_members(store,target,before['expected_entries'])
        verified=[];starting={};entries=[];index=[];histories=[];events=set();batches=set()
        for i,(name,declared) in enumerate(zip(names,before['expected_entries'])):
            field=f'entries[{i}]';stage=field;leaf=target/name
            buffers,objects=_capture_leaf(store,leaf,field);starting[name]=buffers
            manifest_sha=_sha(buffers['manifest.json'])
            _equal(manifest_sha,declared['manifest_file_sha256'],field+'.manifest_file_sha256')
            # After all initial capture consumption, before the one nested call.
            _store_call(store,'',store._confirm_components,captures)
            if _store_call(store,'',store._read_bytes,HISTORY_PATH,'bindings')!=history_bytes:_block('component_bindings.history_file_sha256','history较操作开始变化')
            result=_store_call(store,field,store.verify_human_initial_judgment_snapshots,leaf)
            record,prior=_bind_verification(store,result,buffers,objects,components,field)
            item={'event_id':record['human_initial_judgment']['event_id'],'batch_id':record['binding']['batch_id'],
                  'record_fingerprint':_fp(record),'binding_fingerprint':_fp(record['binding'])}
            for key in INDEX_KEYS:
                (_hex if key.endswith('fingerprint') else _text)(item[key],field+'.record.'+key)
            _equal(item['record_fingerprint'],result['record_fingerprint'],field+'.record_fingerprint')
            if item['event_id'] in events:_block(field+'.record.human_initial_judgment.event_id','域内事件重复')
            if item['batch_id'] in batches:_block(field+'.record.binding.batch_id','域内同批第二份初判')
            events.add(item['event_id']);batches.add(item['batch_id'])
            _equal(prior['declared_scope'],before['expected_declared_scope'],field+'.prior_history.declared_scope')
            _equal(record['history_binding']['declared_scope'],before['expected_declared_scope'],field+'.record.history_binding.declared_scope')
            histories.append(prior);index.append(item);entries.append({'relative':name,'manifest_file_sha256':manifest_sha})
            verified.append({'relative':name,'verification':copy.deepcopy(result)})
        stage='references';index.sort(key=lambda x:x['event_id'].encode('utf-8'));by_event={x['event_id']:x for x in index}
        for i,prior in enumerate(histories):
            for j,reference in enumerate(prior['records']):
                field=f'entries[{i}].prior_history.records[{j}]';_keys(reference,INDEX_KEYS,field)
                for key in INDEX_KEYS:(_hex if key.endswith('fingerprint') else _text)(reference[key],field+'.'+key)
                if reference['event_id'] not in by_event:_block(field+'.event_id','已声明引用不在当前完整域索引')
                for key in INDEX_KEYS[1:]:_equal(reference[key],by_event[reference['event_id']][key],field+'.'+key)
        returned=_build_return(namespace,before['expected_declared_scope'],entries,
            dict(components,history_file_sha256=_sha(history_bytes)),verified,index)
        _equal(expectations,before,'expectations')
        stage='final_confirmation';_terminal_confirm(store,namespace_dir,target,before['expected_entries'],starting,captures,history_bytes)
        return returned
    except (HumanInitialJudgmentHistoryBlocked,HumanInitialJudgmentHistoryError):raise
    except Exception as cause:raise HumanInitialJudgmentHistoryError(stage,f'{type(cause).__name__}: {cause}') from cause
